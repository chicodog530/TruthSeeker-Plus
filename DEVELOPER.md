# Developer Guide: TruthSeeker Architecture

TruthSeeker is a local web application built with Python and Flask. It uses Playwright for browser automation and Server-Sent Events (SSE) for real-time data streaming.

## Technical Stack

- **Backend**: Python 3.9+, Flask
- **Browser Automation**: Playwright (Chromium)
- **Scanning**: `requests` (Session-based)
- **Real-time Updates**: Server-Sent Events (SSE)
- **Export**: `fpdf2` for PDF generation, standard JS/Blob for HTML export.
- **Frontend**: Vanilla HTML5, CSS3, and JavaScript (ES6).

## Core Logic Architecture

### 1. URL Parsing
The server takes a "Seed URL" and uses Regex to extract the prefix, numeric suffix, and padding width. This establishes the "Pattern" for discovery.

### 2. Session Initialization (Playwright)
Before scanning, `server.py` launches a Playwright Chromium instance. It navigates to the seed URL and executes site-specific logic (e.g., clicking Justice.gov's age gate) to establish an authorized session.
The cookies and User-Agent are then mirrored into a `requests.Session` object.

### 3. Verification Scan
The loop generates the next URL in the sequence and performs a `HEAD` request.
- **200/206 Response**: Considered a potential hit.
- **Soft-404 Rejection**: If the `Content-Type` is `text/html`, it is rejected as a 200-OK error page.
- **Size Validation**: Files under 5KB are ignored (likely dummy files or error icons).

### 4. Streaming Results
Results are yielded via SSE. The frontend listens for `onmessage` and updates the live feed and progress bar dynamically without page refreshes.

## Development Workflow

### Installing Dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### Running in Debug Mode
Set `debug=True` in `app.run()` within `server.py` to enable auto-reload.

### Packaging with PyInstaller
To build the portable version:
```bash
pyinstaller --noconfirm --onefile --windowed --add-data "templates;templates" server.py
```
*Note: Playwright browser binaries must be bundled separately or installed via the run script.*
