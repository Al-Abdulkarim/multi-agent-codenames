"""
نقطة الدخول الرئيسية
Main entry point - handles Unicode path resolution on Windows
"""

import sys
import os
import ctypes
from pathlib import Path

# Force UTF-8 for Python globally
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Fix console encoding for Arabic and emoji support
if sys.platform == "win32":
    try:
        # Enable UTF-8 Mode for the current process
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_short_path(long_path: str) -> str:
    """Get Windows short path (8.3 format) to avoid Unicode issues"""
    buf = ctypes.create_unicode_buffer(512)
    result = ctypes.windll.kernel32.GetShortPathNameW(long_path, buf, 512)
    if result:
        return buf.value
    return long_path


def setup_path():
    """Setup Python path so modules can be found regardless of directory encoding"""
    project_dir = Path(__file__).resolve().parent

    # Try using the short path on Windows (avoids Arabic character issues)
    short_path = get_short_path(str(project_dir))

    # Add both paths to sys.path
    for p in [short_path, str(project_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    # Change to short path directory
    os.chdir(short_path)

    # Set PYTHONPATH environment variable for child processes (like uvicorn's import)
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = short_path + (os.pathsep + existing if existing else "")

    return short_path


def main():
    short_path = setup_path()

    print(f"[INFO] Project directory: {short_path}")
    print("[INFO] Starting Codenames Arabic Server...")
    print("[INFO] Open http://localhost:8000 in your browser")

    import uvicorn

    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
