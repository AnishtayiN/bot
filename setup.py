#!/usr/bin/env python3
"""
=== یک‌مرحله‌ای نصب کامل MusicFinder Bot ===
این فایل را اجرا کن تا همه‌چیز (پکیج‌ها + ffmpeg + Deno + Deno) نصب شود:
    python setup.py
"""
import subprocess
import shutil
import sys
import os
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"


def run(cmd: str, check: bool = True) -> bool:
    print(f"  ▸ {cmd}")
    try:
        r = subprocess.run(cmd, shell=True, check=check,
                           capture_output=True, text=True)
        return r.returncode == 0
    except subprocess.CalledProcessError:
        return False


def find(name: str) -> str | None:
    return shutil.which(name)


# ── 1) pip packages ──────────────────────────────────────
def install_pip():
    print("\n📦 [1/4] نصب پکیج‌های Python ...")
    req = Path(__file__).parent / "requirements.txt"
    if req.exists():
        run(f"{sys.executable} -m pip install -r {req}")
    else:
        run(f"{sys.executable} -m pip install "
            "\"python-telegram-bot[job-queue]>=21.6,<22\" "
            "\"yt-dlp>=2026.8.19\" \"yt-dlp-ejs>=0.8.0\" "
            "\"shazamio>=0.8.1\" \"httpx>=0.27\" \"mutagen>=1.47\"")


# ── 2) ffmpeg ────────────────────────────────────────────
def install_ffmpeg():
    print("\n🎵 [2/4] بررسی ffmpeg ...")
    if find("ffmpeg"):
        print("  ✅ ffmpeg قبلاً نصب شده")
        return
    print("  ⬇️  نصب ffmpeg ...")
    if IS_WINDOWS:
        if find("choco"):
            run("choco install ffmpeg -y")
        elif find("winget"):
            run("winget install --id Gyan.FFmpeg -e --accept-package-agreements")
        else:
            print("  ❌ ffmpeg پیدا نشد! لطفاً از https://www.gyan.dev/ffmpeg/builds/ دانلود کنید")
            return
    elif IS_LINUX:
        if find("apt-get"):
            run("sudo apt-get update && sudo apt-get install -y ffmpeg")
        elif find("yum"):
            run("sudo yum install -y ffmpeg")
        elif find("dnf"):
            run("sudo dnf install -y ffmpeg")
        elif find("apk"):
            run("sudo apk add ffmpeg")
        else:
            print("  ❌ مدیر پکیج پشتیبانی نمی‌شود. لطفاً دستی نصب کنید.")
            return
    elif IS_MAC:
        if find("brew"):
            run("brew install ffmpeg")
        else:
            print("  ❌ brew نصب نیست. از https://ffmpeg.org/download.html دانلود کنید.")
            return

    if find("ffmpeg"):
        print("  ✅ ffmpeg با موفقیت نصب شد")
    else:
        print("  ⚠️  ffmpeg نصب شد ولی در PATH پیدا نمی‌شود")


# ── 3) Deno ──────────────────────────────────────────────
def install_deno():
    print("\n🦕 [3/4] بررسی Deno (JS runtime for yt-dlp) ...")
    if find("deno"):
        print("  ✅ Deno قبلاً نصب شده")
        return
    print("  ⬇️  نصب Deno ...")
    if IS_WINDOWS:
        if find("powershell"):
            run("powershell -Command \"irm https://deno.land/install.ps1 | iex\"")
        else:
            print("  ❌ لطفاً از https://deno.land/manual/getting_started/installation دستی نصب کنید")
            return
    else:
        run("curl -fsSL https://deno.land/install.sh | sh")

    if find("deno"):
        print("  ✅ Deno با موفقیت نصب شد")
    else:
        # ممکن است در مسیر غیراستاندارد باشد
        home = Path.home()
        for candidate in [home / ".deno" / "bin" / "deno",
                          Path("/usr/local/bin/deno")]:
            if candidate.exists():
                print(f"  ℹ️  Deno در {candidate} پیدا شد. مسیر را به PATH اضافه کنید.")
                return
        print("  ⚠️  Deno نصب شد ولی در PATH پیدا نمی‌شود")


# ── 4) چک نهایی ──────────────────────────────────────────
def final_check():
    print("\n🔍 [4/4] چک نهایی ...")
    checks = {
        "python": find("python") or find("python3"),
        "ffmpeg": find("ffmpeg"),
        "deno": find("deno"),
    }
    all_ok = True
    for name, ok in checks.items():
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")
        if not ok:
            all_ok = False

    # چک پکیج‌های پایتون
    try:
        import telegram; print("  ✅ python-telegram-bot")
    except ImportError: print("  ❌ python-telegram-bot"); all_ok = False
    try:
        import yt_dlp; print(f"  ✅ yt-dlp {yt_dlp.version.__version__}")
    except ImportError: print("  ❌ yt-dlp"); all_ok = False
    try:
        import shazamio; print("  ✅ shazamio")
    except ImportError: print("  ❌ shazamio"); all_ok = False

    return all_ok


# ── main ──────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  🎬🎵 MusicFinder Bot — نصب کامل")
    print("=" * 55)

    install_pip()
    install_ffmpeg()
    install_deno()
    ok = final_check()

    print("\n" + "=" * 55)
    if ok:
        print("  ✅ همه‌چیز آماده‌ی اجراست!")
        print("  👉 فایل .env را پر کنید و بزنید: python bot.py")
    else:
        print("  ⚠️  بعضی پیش‌نیازها ناقص ماندند.")
        print("  👉 لاگ بالا را بخوانید و دستی نصب کنید.")
    print("=" * 55)


if __name__ == "__main__":
    main()
