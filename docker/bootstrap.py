#!/usr/bin/env python3
"""نصب ffmpeg/ffprobe (استاتیک) + Deno + سرویس PO-Token — بدون apt/curl/unzip/xz.

چرا این فایل وجود دارد؟
------------------------
کانتینرِ build در Railway فضای دیسک خیلی کمی دارد — در همان لاگ، apt حتی برای
۱۶٫۶MB هم جا نداشت. نسخه‌ی قبلیِ Dockerfile در همان لایه‌ی دوم این کارها را
می‌کرد (اعداد از روی assetهای واقعیِ GitHub):

    apt-get install curl unzip xz-utils   ->  ۵٫۷MB دانلود / ۱۶٫۶MB روی دیسک
    curl  ffmpeg-...tar.xz  (۱۴۹٫۴MB)     ->  روی دیسک
    tar -xJf  (کل آرشیو: سه باینری استاتیک بزرگ + doc/lib/models) -> روی دیسک
    curl  deno-...zip       (۴۱٫۶MB)      ->  روی دیسک
    unzip                   (باینری deno) ->  روی دیسک

یعنی چند صد مگابایت نوشتنِ موقت، فقط برای رسیدن به سه فایل. نتیجه همان خطایی
است که در لاگ دیپلوی دیده می‌شود:

    E: You don't have enough free space in /var/cache/apt/archives/

این اسکریپت همان کار را فقط با کتابخانه‌ی استاندارد پایتون انجام می‌دهد:

  * هیچ بسته‌ی apt نصب نمی‌شود؛ پس apt دیگر نمی‌تواند جلوی build را بگیرد
    (curl/unzip/xz هم لازم نیستند — urllib و tarfile و zipfile کافی‌اند).
  * آرشیو tar.xz هرگز روی دیسک نوشته نمی‌شود: مستقیم از شبکه stream می‌شود و
    فقط ffmpeg و ffprobe استخراج می‌شوند. به‌محض پیدا شدن هر دو، خواندنِ
    آرشیو متوقف می‌شود؛ بقیه‌ی آن (ffplay/doc/lib/models) اصلاً دانلود نمی‌شود.
  * zip مربوط به Deno در حافظه باز می‌شود، نه روی دیسک.
  * مصرف دیسک قبل و بعد از هر مرحله چاپ می‌شود تا اگر باز هم فضا کم آمد،
    عددش در لاگ دیپلوی دیده شود.
"""

from __future__ import annotations

import argparse
import errno
import io
import os
import posixpath
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

USER_AGENT = "anishtayin-bot-image-builder/2.0"
CHUNK = 1 << 20          # 1MB
TIMEOUT = 240            # ثانیه برای هر اتصال
ATTEMPTS = 4             # تعداد تلاش برای هر دانلود


# --------------------------------------------------------------------------- #
# ابزارهای کوچک
# --------------------------------------------------------------------------- #
def log(message: str = "") -> None:
    print(message, flush=True)


def free_mb(path: str = "/") -> float:
    """فضای آزاد (مگابایت) روی فایل‌سیستمی که `path` رویش است."""
    try:
        return shutil.disk_usage(path).free / 1e6
    except OSError:
        return float("nan")


def disk_report(stage: str) -> None:
    log(f"[bootstrap] free disk after {stage}: {free_mb():.0f} MB")


def die(message: str, code: int = 1) -> None:
    log(f"[bootstrap] ❌ {message}")
    disk_report("failure")
    raise SystemExit(code)


def open_url(url: str):
    """یک پاسخ HTTP باز می‌کند؛ با چند بار تلاش مجدد و User-Agent مناسب."""
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            return urllib.request.urlopen(request, timeout=TIMEOUT)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in (400, 401, 403, 404, 410):   # تلاش مجدد فایده ندارد
                break
        except Exception as exc:                        # شبکه/SSL/timeout
            last_error = exc
        if attempt < ATTEMPTS:
            wait = 5 * attempt
            log(f"[bootstrap] تلاش {attempt}/{ATTEMPTS} ناموفق بود ({last_error}) — "
                f"{wait} ثانیه صبر می‌کنم")
            time.sleep(wait)
    die(f"دانلود ناموفق بود:\n           {url}\n           آخرین خطا: {last_error}")


def read_all(response) -> bytes:
    buffer = bytearray()
    while True:
        chunk = response.read(CHUNK)
        if not chunk:
            break
        buffer.extend(chunk)
    return bytes(buffer)


def extract_all(tar: tarfile.TarFile, path: str) -> None:
    """extractall با فیلتر امن؛ روی پایتونِ خیلی قدیمی بدون فیلتر."""
    try:
        tar.extractall(path, filter="data")
    except TypeError:      # پایتون < 3.11.4
        tar.extractall(path)


def run(cmd: list[str], cwd: str | None = None, echo: bool = True) -> int:
    """یک دستور را اجرا می‌کند و خروجی‌اش را در لاگ build چاپ می‌کند."""
    if echo:
        log(f"[bootstrap] $ {' '.join(cmd)}" + (f"   (cwd={cwd})" if cwd else ""))
    try:
        proc = subprocess.run(
            cmd, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace",
        )
    except OSError as exc:
        log(f"[bootstrap] اجرای دستور ممکن نشد: {exc}")
        return 127
    output = (proc.stdout or "").strip()
    if output:
        log(output)
    return proc.returncode


# --------------------------------------------------------------------------- #
# ffmpeg / ffprobe
# --------------------------------------------------------------------------- #
def _wanted_name(member_name: str, wanted: set[str]) -> str | None:
    """اگر این member همان باینریِ داخل پوشه‌ی bin است، نامش را برمی‌گرداند."""
    parts = [p for p in member_name.split("/") if p not in ("", ".")]
    if len(parts) < 2 or parts[-1] not in wanted:
        return None
    return parts[-1] if parts[-2] == "bin" else None


def install_static_binaries(url: str, dest_dir: str, wanted: tuple[str, ...]) -> dict[str, int]:
    """آرشیو tar.xz را stream می‌کند و فقط باینری‌های `wanted` را بیرون می‌کشد.

    هیچ فایل موقتی روی دیسک نوشته نمی‌شود و به‌محض پیدا شدن همه‌ی باینری‌ها
    خواندنِ آرشیو قطع می‌شود (بقیه‌ی آرشیو دانلود نمی‌شود).
    """
    os.makedirs(dest_dir, exist_ok=True)
    pending = set(wanted)
    link_alias: dict[str, str] = {}      # نام فایل واقعی -> نامی که باید نصب شود
    found: dict[str, int] = {}

    log(f"[bootstrap] شروع دانلود (stream): {url}")
    with open_url(url) as response, tarfile.open(fileobj=response, mode="r|xz") as tar:
        for member in tar:
            name = member.name.rstrip("/")

            # بعضی buildها باینری را symlink می‌گذارند؛ لینک را دنبال می‌کنیم.
            if member.issym() or member.islnk():
                base = posixpath.basename(name)
                if base in pending:
                    target = posixpath.basename(member.linkname.rstrip("/"))
                    link_alias[target] = base
                    log(f"[bootstrap] {base} یک لینک به {member.linkname} است — دنبال می‌کنم")
                continue

            if not member.isfile():
                continue

            install_as = _wanted_name(name, pending)
            if install_as is None:
                base = posixpath.basename(name)
                install_as = link_alias.get(base)
            if install_as is None:
                continue

            source = tar.extractfile(member)
            if source is None:
                continue
            target = os.path.join(dest_dir, install_as)
            with source, open(target, "wb") as out:
                shutil.copyfileobj(source, out, CHUNK)
            os.chmod(target, 0o755)
            found[install_as] = os.path.getsize(target)
            pending.discard(install_as)
            log(f"[bootstrap] ✅ {install_as} -> {target} "
                f"({found[install_as] / 1e6:.1f} MB)")
            if not pending:
                break          # بقیه‌ی آرشیو لازم نیست

    if pending:
        die(f"در آرشیو پیدا نشد: {', '.join(sorted(pending))}\n"
            f"           URL: {url}\n"
            f"           اگر آدرس build عوض شده، FFMPEG_URL را در Dockerfile به‌روز کنید.")
    return found


# --------------------------------------------------------------------------- #
# Deno
# --------------------------------------------------------------------------- #
def install_zip_binary(url: str, dest_dir: str, entry: str) -> str:
    """zip را در حافظه باز می‌کند و فقط باینری `entry` را روی دیسک می‌نویسد."""
    os.makedirs(dest_dir, exist_ok=True)
    log(f"[bootstrap] شروع دانلود (حافظه): {url}")
    with open_url(url) as response:
        data = read_all(response)
    log(f"[bootstrap] {len(data) / 1e6:.1f} MB در حافظه خوانده شد")

    target = os.path.join(dest_dir, entry)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist()
                 if posixpath.basename(n) == entry and not n.endswith("/")]
        if not names:
            die(f"داخل zip اثری از «{entry}» نبود: {url}")
        with archive.open(names[0]) as source, open(target, "wb") as out:
            shutil.copyfileobj(source, out, CHUNK)
    del data                       # حافظه زودتر آزاد شود
    os.chmod(target, 0o755)
    log(f"[bootstrap] ✅ {entry} -> {target} ({os.path.getsize(target) / 1e6:.1f} MB)")
    return target


# --------------------------------------------------------------------------- #
# سرویس PO-Token (bgutil)
# --------------------------------------------------------------------------- #
def install_pot_source(url: str, dest_dir: str) -> str:
    """tar.gz سورسِ provider را دانلود و در dest_dir (بدون پوشه‌ی والد) می‌ریزد."""
    staging = dest_dir.rstrip("/") + "-src"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging, exist_ok=True)

    log(f"[bootstrap] شروع دانلود (stream): {url}")
    with open_url(url) as response, tarfile.open(fileobj=response, mode="r|gz") as tar:
        extract_all(tar, staging)

    entries = [e for e in os.listdir(staging) if not e.startswith(".")]
    if len(entries) != 1 or not os.path.isdir(os.path.join(staging, entries[0])):
        die(f"ساختار غیرمنتظره در آرشیو provider: {entries}")

    shutil.rmtree(dest_dir, ignore_errors=True)
    os.makedirs(os.path.dirname(dest_dir) or "/", exist_ok=True)
    shutil.move(os.path.join(staging, entries[0]), dest_dir)
    shutil.rmtree(staging, ignore_errors=True)
    log(f"[bootstrap] ✅ سورس provider -> {dest_dir}")
    return dest_dir


def prepare_pot_runtime(dest_dir: str) -> bool:
    """npm dependencyها و کش ماژول‌ها را با Deno آماده می‌کند.

    اگر هر مرحله شکست خورد، build را نمی‌خوابانیم: start.sh بدون provider هم
    ربات را بالا می‌آورد (yt-dlp در حالت graceful).
    """
    server = os.path.join(dest_dir, "server")
    main_ts = os.path.join("src", "main.ts")
    if not os.path.isfile(os.path.join(server, main_ts)):
        log(f"[bootstrap] ⚠️  {server}/src/main.ts وجود ندارد — provider نصب نشد")
        return False

    # --prod: devDependencyها (eslint/typescript/prettier) نصب نشوند تا
    # node_modules و در نتیجه مصرف دیسک و حجم ایمیج کوچک بماند.
    install_commands = [
        ["deno", "install", "--prod", "--allow-scripts=npm:canvas"],
        ["deno", "install", "--allow-scripts=npm:canvas"],
        ["deno", "install"],
    ]
    installed = False
    for cmd in install_commands:
        if run(cmd, cwd=server) == 0:
            installed = True
            break
        log("[bootstrap] این حالت جواب نداد؛ حالت بعدی را امتحان می‌کنم")

    if not installed:
        log("[bootstrap] ⚠️  deno install ناموفق بود — provider بدون node_modules است")
        return False

    # کش کردن گراف ماژول‌ها تا اجرای اول در runtime سریع و آفلاین باشد.
    if run(["deno", "cache", main_ts], cwd=server) != 0:
        log("[bootstrap] ⚠️  deno cache ناموفق بود")
        return False

    log("[bootstrap] ✅ سرویس PO-Token آماده است")
    return True


# --------------------------------------------------------------------------- #
# ورودی‌ها
# --------------------------------------------------------------------------- #
def cmd_tools(args: argparse.Namespace) -> int:
    disk_report("start")
    try:
        import lzma  # noqa: F401  — برای tar.xz لازم است
    except ImportError:
        die("ماژول lzma در این پایتون نیست؛ tar.xz باز نمی‌شود. "
            "بیس‌ایمیج باید python:*-slim رسمی باشد.")

    install_static_binaries(args.ffmpeg_url, args.bin_dir, ("ffmpeg", "ffprobe"))

    # بررسی واقعی: باینری باید اجرا شود، نه فقط روی دیسک باشد.
    for name in ("ffmpeg", "ffprobe"):
        path = os.path.join(args.bin_dir, name)
        proc = subprocess.run([path, "-version"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors="replace")
        first_line = (proc.stdout or "").strip().splitlines()
        log(f"[bootstrap] {name}: {first_line[0] if first_line else '<بدون خروجی>'}")
        if proc.returncode != 0:
            die(f"{name} اجرا نشد (کد {proc.returncode}):\n{proc.stdout}")

    # Deno برای yt-dlp-ejs و سرویس PO-Token لازم است؛ اگر اجرا نشد ایمیج را
    # خراب نمی‌کنیم — فقط باینریِ معیوب را پاک می‌کنیم تا bot.py درست گزارش دهد.
    deno_path = install_zip_binary(args.deno_url, args.bin_dir, "deno")
    proc = subprocess.run([deno_path, "--version"], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors="replace")
    output = (proc.stdout or "").strip()
    if proc.returncode == 0:
        log(f"[bootstrap] deno: {output.splitlines()[0]}")
    else:
        log(f"[bootstrap] ⚠️  deno --version ناموفق بود (کد {proc.returncode}):\n{output}")
        log("[bootstrap] ⚠️  باینری deno پاک می‌شود؛ دانلود یوتیوب بدون آن محدود می‌شود")
        os.remove(deno_path)

    disk_report("tools")
    return 0


def cmd_pot(args: argparse.Namespace) -> int:
    disk_report("start")
    url = args.url or (
        "https://github.com/Brainicism/bgutil-ytdlp-pot-provider/archive/refs/tags/"
        f"{args.version}.tar.gz"
    )
    dest = install_pot_source(url, args.dest)

    if shutil.which("deno") is None:
        log("[bootstrap] ⚠️  deno در PATH نیست — آماده‌سازی runtime انجام نشد")
    elif not prepare_pot_runtime(dest):
        log("[bootstrap] ⚠️  ربات بدون PO-Token provider هم کار می‌کند "
            "(start.sh آن را skip می‌کند)")

    disk_report("pot")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    tools = sub.add_parser("tools", help="نصب ffmpeg/ffprobe/deno")
    tools.add_argument("--bin-dir", default="/usr/local/bin")
    tools.add_argument("--ffmpeg-url", required=True)
    tools.add_argument("--deno-url", required=True)
    tools.set_defaults(func=cmd_tools)

    pot = sub.add_parser("pot", help="نصب سرویس bgutil PO-Token")
    pot.add_argument("--dest", default="/opt/pot")
    pot.add_argument("--version", default="1.3.2")
    pot.add_argument("--url", default="")
    pot.set_defaults(func=cmd_pot)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log(f"[bootstrap] python {sys.version.split()[0]} | command={args.command}")
    try:
        return args.func(args)
    except SystemExit:
        raise
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            die("دیسک کانتینر build پر شد (ENOSPC). "
                "ایمیج سبک‌تر از این نمی‌شود؛ کش build در Railway را پاک کنید "
                "یا سرویس را در یک environment جدید دیپلوی کنید.")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
