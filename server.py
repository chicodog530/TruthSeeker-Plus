"""
TruthSeeker Plus Web Server
==========================
Run with:  python server.py
Then open: http://localhost:5173
"""
import itertools
import json
import os
import random
import re
import sys
import time
import webbrowser
from datetime import datetime
from threading import Thread
from urllib.parse import urlparse, unquote

import requests as req_lib
from flask import Flask, Response, jsonify, render_template, request, send_file

app = Flask(__name__)

# ── Local Browser Isolation ──────────────────────────────────────────────────
# Store browsers in a local folder next to the EXE to keep it portable
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BROWSER_DIR = os.path.join(BASE_DIR, "browsers")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSER_DIR

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# ── User-Agent pool ───────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 Chrome/118.0.0.0 Safari/537.36",
]

GATE_RE = re.compile(
    r'agree|i agree|verify|accept|confirm|continue|certify|proceed|enter|robot|yes|older|age', re.I)

HTML_CTYPES = ('text/html', 'text/plain', 'text/xml', 'application/xhtml+xml')


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _log(msg: str) -> str:
    return _sse({"type": "log", "msg": msg})


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/parse", methods=["POST"])
def parse():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # Generalized parsing: Find the *last* sequence of digits in the URL
    # Format: (Prefix)(Digits)(Suffix)
    # The suffix can be an extension (.mp4) or a path part (/zip)
    m = re.search(r"^(.*?)(\d+)([^0-9]*)$", url)
    if not m:
        return jsonify({"error": "No numeric sequence found in the URL"}), 400

    prefix      = m.group(1)
    num_str     = m.group(2)
    suffix      = m.group(3)
    num_width   = len(num_str)
    base_num    = int(num_str)

    return jsonify({
        "prefix":    prefix,
        "num_width": num_width,
        "base_num":  base_num,
        "next_num":  base_num + 1,
        "base_url":  "", # We use the full prefix now
        "suffix":    suffix
    })


@app.route("/scan")
def scan():
    base_url  = request.args.get("base_url", "")
    prefix    = request.args.get("prefix", "")
    num_width = int(request.args.get("num_width", 8))
    base_num  = int(request.args.get("base_num", 0))
    start_num = int(request.args.get("start_num", base_num))
    max_n     = int(request.args.get("max_n", 500))
    max_mis   = int(request.args.get("max_mis", 50))
    delay_min = float(request.args.get("delay_min", 1.0))
    delay_max = float(request.args.get("delay_max", 3.0))
    click_mode = request.args.get("click_mode") == "true"
    auto_download = request.args.get("auto_download") == "true"
    exts      = request.args.getlist("exts")
    if not exts:
        exts = [""] # For click mode navigation
    cookie_str = request.args.get("cookie", "").strip()

    def generate():
        session     = req_lib.Session()
        # Ensure the scanner starts with the exact same UA as Playwright
        session.headers.update({
            "User-Agent": USER_AGENTS[0],
            "Referer": base_url,
            "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1"
        })
        agent_cycle = itertools.cycle(USER_AGENTS)

        # ── Authentication ────────────────────────────────────────────────────
        if cookie_str:
            domain = urlparse(base_url).netloc
            count  = 0
            for pair in cookie_str.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    n, _, v = pair.partition("=")
                    session.cookies.set(n.strip(), v.strip(), domain=domain)
                    count += 1
            yield _log(f"✔ {count} browser cookie(s) injected.")
        
        # ── Browser Logic ─────────────────────────────────────────────────────
        def run_playwright_logic():
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
            with sync_playwright() as pw:
                try:
                    # Stealth Launch Arguments
                    args = [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--use-fake-ui-for-media-stream",
                        "--use-fake-device-for-media-stream",
                        "--window-size=1280,720"
                    ]
                    browser = pw.chromium.launch(headless=False, args=args)
                except Exception as e:
                    err_msg = str(e).lower()
                    if "executable doesn't exist" in err_msg or "playwright install" in err_msg or "not found" in err_msg:
                        yield _log(f"🌐 Chromium missing at {BROWSER_DIR}. Attempting install...")
                        try:
                            import subprocess
                            env = os.environ.copy()
                            env["PLAYWRIGHT_BROWSERS_PATH"] = BROWSER_DIR
                            if getattr(sys, 'frozen', False):
                                driver_path = os.path.join(sys._MEIPASS, "playwright", "driver")
                                node = os.path.join(driver_path, "node.exe")
                                cli = os.path.join(driver_path, "package", "cli.js")
                                subprocess.run([node, cli, "install", "chromium"], env=env, check=True, capture_output=True)
                            else:
                                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], env=env, check=True, capture_output=True)
                            yield _log("✔ Chromium installed. Launching...")
                            browser = pw.chromium.launch(headless=False, args=args)
                        except Exception as install_err:
                            yield _log(f"⚠ Browser auto-install failed: {install_err}")
                            raise install_err
                    else:
                        raise e

                ctx = browser.new_context(user_agent=USER_AGENTS[0], viewport={'width': 1280, 'height': 720})
                page = ctx.new_page()
                page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")

                # ── Age Gate Check ────────────────────────────────────────────
                clicked = False
                if not cookie_str and not click_mode:
                    seed_url = (f"{base_url}{prefix}"
                                f"{str(base_num).zfill(num_width)}{exts[0]}")
                    yield _log("🌐 Opening browser to handle age gate…")
                    try:
                        page.goto(seed_url, timeout=25_000)
                        page.wait_for_load_state("domcontentloaded", timeout=15_000)

                        if "justice.gov" in seed_url:
                            yield _log("🔍 Checking for DOJ gate...")
                            try:
                                yield _log("🔍 Checking for DOJ bot-check button...")
                                bot_selectors = [
                                    'input.usa-button[value*="robot" i]',
                                    'button.usa-button:has-text("robot")',
                                    'button:has-text("robot")',
                                    'input[value*="robot" i]'
                                ]
                                bot_btn = None
                                for sel in bot_selectors:
                                    try:
                                        bot_btn = page.wait_for_selector(sel, timeout=7000)
                                        if bot_btn:
                                            bot_btn.click()
                                            yield _log(f"✔ Bot verification clicked (found via {sel}).")
                                            break
                                    except Exception:
                                        continue
                                
                                yield _log("🔍 Checking for DOJ age-gate button...")
                                age_selectors = [
                                    'button#age-button-yes',
                                    'button:has-text("Yes")',
                                    'input[value*="Yes" i]',
                                    'button:has-text("older")',
                                    'button:has-text("18")'
                                ]
                                age_btn = None
                                for sel in age_selectors:
                                    try:
                                        age_btn = page.wait_for_selector(sel, timeout=7000)
                                        if age_btn:
                                            age_btn.click()
                                            yield _log(f"✔ Age confirmation clicked (found via {sel}).")
                                            try:
                                                page.wait_for_load_state("networkidle", timeout=15000)
                                            except Exception:
                                                pass 
                                            clicked = True
                                            break
                                    except Exception:
                                        continue
                            except Exception as e:
                                yield _log(f"⚠ DOJ-specific gate failed: {e}")

                        if not clicked:
                            yield _log("🔍 Searching for generic gate buttons...")
                            for selector in [
                                "button", "input[type=submit]", "input[type=button]",
                                "a.btn", "a[href]", "[role=button]"
                            ]:
                                if clicked:
                                    break
                                try:
                                    for el in page.locator(selector).all():
                                        label = (el.get_attribute("value") or
                                                 el.inner_text(timeout=500) or "").strip()
                                        if GATE_RE.search(label):
                                            yield _log(f"🔘 Clicking candidate button: '{label}'")
                                            el.click(timeout=5000)
                                            page.wait_for_load_state("networkidle",
                                                                     timeout=5000)
                                            clicked = True
                                            break
                                except Exception:
                                    pass

                        yield _log("👀 Browser is visible. Please click the gate manually if it's still showing.")
                        for _ in range(20):
                            if clicked: break
                            try:
                                gate_el = page.locator('button:has-text("Yes"), input[value*="robot" i], button:has-text("robot")').count()
                                if gate_el == 0:
                                    clicked = True
                                    yield _log("✔ Gate cleared (detected manual click).")
                                    break
                            except: pass
                            time.sleep(1)

                        if clicked:
                            yield _log("✔ Age gate passed. Keeping browser open for authenticated scan...")
                        else:
                            yield _log("⚠ Gate detection timed out—proceeding with scan anyway.")
                    except PWTimeout:
                        yield _log("⚠ Age gate check timed out—skipping.")
                    except Exception as e:
                        yield _log(f"⚠ Browser error during gate check: {e}")
                else:
                    if click_mode:
                        yield _log("✔ Click Mode active: Skipping separate age gate check.")

                # ── Range preview ─────────────────────────────────────
                first_url = (f"{base_url}{prefix}"
                             f"{str(start_num).zfill(num_width)}{exts[0]}")
                last_url  = (f"{base_url}{prefix}"
                             f"{str(start_num + max_n - 1).zfill(num_width)}{exts[-1]}")
                yield _sse({"type": "range", "first": first_url, "last": last_url})

                # ── Scan loop (INSIDE Playwright Context) ──────────────
                yield _log(f"🚀 Starting scan of {max_n} batches (using Browser Network Context)")
                found       = 0
                consecutive = 0

                for i in range(max_n):
                    cur_num     = start_num + i
                    num_str_pad = str(cur_num).zfill(num_width)
                    hit_this    = False

                    # In Click Mode, we only need to visit the page ONCE per ID, ignoring the 'exts' loop
                    ext_list_to_scan = [""] if click_mode else exts

                    for ext in ext_list_to_scan:
                        # Construct the display/check URL
                        if click_mode:
                             # Base item page URL
                            url = f"{prefix}{num_str_pad}"
                        else:
                            # Direct file URL
                            url = f"{base_url}{prefix}{num_str_pad}{ext}"

                        yield _sse({
                            "type": "checking",
                            "url":   url,
                            "found": found,
                            "i":     i,
                            "total": max_n,
                        })

                        try:
                            if click_mode:
                                # Human Mode: Navigate to BASE page (no suffix)
                                # Use 'commit' to handle slow redirects/initial responses
                                page.goto(url, timeout=25000, wait_until="commit")
                                
                                # Wait for DOM content to be ready
                                try:
                                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                                except:
                                    pass

                                # Sleep for JS rendering
                                time.sleep(2.5)
                                
                                # Targeted selectors for modern sites (Thingiverse, etc.)
                                selectors = [
                                    'button:has-text("Download all files")',
                                    'a:has-text("Download all files")',
                                    'button[class*="DownloadAll"]',
                                    'div[class*="DownloadAll"] button',
                                    '[data-testid="download-all-files"]',
                                    'button:has-text("Download")',
                                    'a:has-text("Download")',
                                    'button[aria-label*="Download" i]',
                                    'a[aria-label*="Download" i]',
                                ]
                                
                                found_btn = False
                                for sel in selectors:
                                    try:
                                        btn = page.query_selector(sel)
                                        if btn and btn.is_visible():
                                            if i < 3: yield _log(f"🖱 Clicking button: {sel}")
                                            
                                            if auto_download:
                                                # Increase timeout to 60s for slow ZIP generation
                                                with page.expect_download(timeout=60000) as download_info:
                                                    btn.click()
                                                download = download_info.value
                                                save_path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
                                                download.save_as(save_path)
                                                yield _log(f"💾 File saved: {download.suggested_filename}")
                                            else:
                                                btn.click()
                                                
                                            found_btn = True
                                            break
                                    except Exception as btn_err: 
                                        if i < 3: yield _log(f"   ↳ Skip selector {sel}: {btn_err}")
                                        continue
                                
                                if found_btn:
                                    found    += 1
                                    hit_this  = True
                                    yield _sse({"type": "hit", "url": url, "found": found})
                                else:
                                    if i < 3: yield _log(f"   ↳ Skipped: No download button found on '{url}'")
                                    
                            else:
                                # API Mode: Use page.request for perfect session inheritance
                                resp = page.request.get(url, timeout=12000, fail_on_status_code=False)
                                status = resp.status
                                headers = resp.headers
                                ct = headers.get("content-type", "").lower().split(";")[0].strip()
                                cl = headers.get("content-length", None)

                                if i < 3: # Debug first 3
                                    yield _log(f"🔬 {num_str_pad}{ext} -> Status {status} | Type '{ct}' | Size {cl}")

                                if status in (200, 206):
                                    if ct in HTML_CTYPES:
                                        if i < 3: yield _log("   ↳ Skipped: HTML content (Gate re-triggered?)")
                                    elif cl is not None and int(cl) < 10000:
                                        if i < 3: yield _log(f"   ↳ Skipped: File too small ({cl} bytes)")
                                    else:
                                        if auto_download:
                                            fname = f"{prefix}{num_str_pad}{ext}".replace(":", "_").replace("/", "_")
                                            if not "." in fname: fname += ".bin"
                                            save_path = os.path.join(DOWNLOAD_DIR, fname)
                                            with open(save_path, "wb") as f:
                                                f.write(resp.body())
                                            yield _log(f"💾 File saved: {fname}")
                                        
                                        found    += 1
                                        hit_this  = True
                                        yield _sse({"type": "hit", "url": url, "found": found})
                                elif status == 403:
                                    yield _log(f"⛔ Blocked (403) on {num_str_pad}{ext}.")
                                elif status == 429:
                                    yield _log(f"⏳ Rate limited (429).")

                        except Exception as e:
                            if i < 3: yield _log(f"   ↳ Request failure: {e}")

                        time.sleep(random.uniform(delay_min, delay_max))

                    if hit_this:
                        consecutive = 0
                    else:
                        consecutive += 1
                        if consecutive >= max_mis:
                            yield _sse({"type": "stopped", "reason": f"{max_mis} consecutive misses"})
                            break
                
                browser.close()
                yield _log(f"✔ Scan complete. {found} URLs validated. Browser closed.")
                yield _sse({"type": "done", "found": found})

        try:
            yield from run_playwright_logic()
        except ImportError:
            yield _log("⚠ Playwright not installed — scanning without gate bypass.")
        except Exception as ex:
            yield _log(f"⚠ Browser error: {ex} — continuing anyway.")

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/export/pdf", methods=["POST"])
def export_pdf():
    data      = request.json or {}
    urls      = data.get("urls", [])
    base_info = data.get("base", "")

    try:
        from fpdf import FPDF
    except ImportError:
        return jsonify({"error": "fpdf2 not installed"}), 500

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(233, 69, 96)
    pdf.cell(0, 12, "TruthSeeker Plus — Valid Video URLs",
             new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7,
             f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
             f"Base: {base_info}  |  {len(urls)} URL(s) — 404s excluded",
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_draw_color(233, 69, 96)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(0, 80, 180)
    for url in urls:
        pdf.cell(0, 6, url, new_x="LMARGIN", new_y="NEXT", link=url)

    path = os.path.join(os.path.dirname(__file__),
                        f"TruthSeeker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    pdf.output(path)
    return send_file(path, as_attachment=True)


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = 5173
    print(f"\n  TruthSeeker Plus running at  http://localhost:{port}\n")
    Thread(target=lambda: (time.sleep(1.2),
                           webbrowser.open(f"http://localhost:{port}")),
           daemon=True).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
