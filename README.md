# 🔍 TruthSeeker Plus

**TruthSeeker Plus** is a powerful URL discovery and video validation engine designed to find hidden media files on servers with numeric patterns. It features automated browser handling to bypass JavaScript-driven age verification gates (like those on justice.gov) and provides real-time progress streaming.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9+-yellow)
![Framework](https://img.shields.io/badge/framework-Flask-green)

---

## ✨ Features

- **Automated Age-Gate Bypass**: Uses Playwright to automatically handle "I am not a robot" and "18+" prompts on Justice.gov and similar sites.
- **Smart Range Scanning**: Finds files by scanning numeric patterns (e.g., `FILE001.mp4`, `FILE002.mp4`).
- **Real-Time Feed**: Results stream live to your browser using Server-Sent Events (SSE).
- **Soft-404 Detection**: Automatically rejects "File Not Found" HTML pages that return a 200 OK status.
- **Media Validation**: Verifies file headers and sizes to ensure only real video files are saved.
- **Export Options**: Save your findings as high-quality PDF reports or portable HTML galleries.
- **Premium Dark UI**: A sleek, modern interface optimized for desktop use.

---

## 🚀 Quick Start (Portable Version)

1. **Download** the latest `TruthSeeker_Portable.zip` from the Releases page.
2. **Extract** the folder to your desktop.
3. **Double-click** `run_web.bat`.
4. Your browser will open to `http://localhost:5173`.
5. Paste a "Seed URL" (e.g., a known file) and click **Parse**, then **Start Scan**.

---

## 🛠️ Installation (Developers / Source Code)

If you want to run the source code directly:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/truthseeker.git
   cd truthseeker
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Browser Binaries**:
   ```bash
   python -m playwright install chromium
   ```

4. **Run the Server**:
   ```bash
   python server.py
   ```

---

## 📄 Documentation

- [**Step-by-Step Instructions**](INSTRUCTIONS.md) - For non-technical users.
- [**Developer Guide**](DEVELOPER.md) - Technical architecture and contribution guide.

## ⚖️ License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
