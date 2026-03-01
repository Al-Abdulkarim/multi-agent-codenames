"""
نقطة الدخول الرئيسية المتوافقة مع الهيكلة الجديدة
Main entry point for New Project Structure
Handles Unicode and Windows Path issues
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

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
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
    short_path = get_short_path(str(project_dir))

    # Add to sys.path
    if short_path not in sys.path:
        sys.path.insert(0, short_path)

    os.chdir(short_path)

    # Update PYTHONPATH
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = short_path + (os.pathsep + existing if existing else "")

    return short_path


def main():
    setup_path()

    # Import and run the new main
    from main import main as original_main

    # We can pass arguments if needed, or let original_main use sys.argv
    original_main()


if __name__ == "__main__":
    main()
