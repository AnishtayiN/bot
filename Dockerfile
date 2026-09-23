# ============================================================
#  ربات دانلود ویدیو/موزیک — ایمیج سبک برای Railway / هر سرور داکری
#
#  ⚠️ درباره‌ی خطای «E: You don't have enough free space in
#     /var/cache/apt/archives/»:
#     کانتینر build در Railway دیسک خیلی محدودی دارد (در لاگ دیپلوی، apt برای
#     ۱۶٫۶MB هم جا نداشت). نسخه‌ی قبلی این فایل در همان لایه اول apt نصب
#     می‌کرد و بعد آرشیو ۱۴۹٫۴ مگابایتی ffmpeg را روی دیسک می‌ریخت و کامل
#     extract می‌کرد (سه باینری استاتیک بزرگ + doc/lib/models) و بعد هم zip
#     مربوط به Deno (۴۱٫۶MB) را دانلود و unzip می‌کرد؛ یعنی چند صد مگابایت
#     نوشتنِ موقت، فقط برای رسیدن به سه فایل.
#
#     حالا هیچ بسته‌ی apt نصب نمی‌شود (curl/unzip/xz لازم نیست) و هیچ
#     آرشیوی روی دیسک نوشته نمی‌شود: docker/bootstrap.py با کتابخانه‌ی
#     استاندارد پایتون آرشیوها را stream می‌کند و فقط ffmpeg و ffprobe و
#     deno را بیرون می‌کشد. مصرف دیسک هم قبل و بعد از هر مرحله در لاگ
#     build چاپ می‌شود.
#
#  نکته: عمداً ARG CACHEBUST اینجا نیست. اگر هر دیپلوی مقدارش عوض شود،
#     همه‌ی لایه‌ها از اول ساخته می‌شوند و کش build بی‌دلیل پر می‌شود.
# ============================================================
FROM python:3.12-slim

ARG POT_VERSION=1.3.2
ARG FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz
ARG DENO_URL=https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip

# DENO_DIR روی مسیر ثابتی می‌ماند تا کش ماژول‌ها هم در build و هم در runtime
# یک‌جا باشد و به /root وابسته نباشد.
# MALLOC_ARENA_MAX تورم حافظه‌ی glibc را روی کانتینرهای کم‌RAM کم می‌کند
# (پلن‌های رایگان پلتفرم‌ها معمولاً ۲۵۶MB رم دارند).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DENO_NO_PROMPT=1 \
    DENO_NO_UPDATE_CHECK=1 \
    DENO_DIR=/opt/deno \
    MALLOC_ARENA_MAX=2

# ffmpeg/ffprobe از build استاتیک BtbN می‌آیند (بسته‌ی Debianِ ffmpeg روی
# python:slim حدود ۵۷۶MB dependency می‌کشد). Deno هم برای yt-dlp-ejs و
# سرویس PO-Token لازم است. هر دو بدون apt نصب می‌شوند.
COPY docker/bootstrap.py /tmp/bootstrap.py
RUN python /tmp/bootstrap.py tools \
        --bin-dir /usr/local/bin \
        --ffmpeg-url "$FFMPEG_URL" \
        --deno-url "$DENO_URL"

# سرور PO-Token (bgutil) با Deno — نسخه را با requirements.txt هماهنگ نگه
# دارید. Deno خودش dependencyهای npm را نصب می‌کند؛ بنابراین Node/npm و git
# وارد ایمیج نمی‌شوند. اگر این مرحله شکست خورد، build نمی‌خوابد: start.sh
# بدون provider هم ربات را بالا می‌آورد (yt-dlp در حالت graceful).
RUN python /tmp/bootstrap.py pot --dest /opt/pot --version "$POT_VERSION" \
    && rm -f /tmp/bootstrap.py

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot.py .env.example README.md start.sh ./
RUN chmod +x start.sh

# مسیر داده‌ها: اگر Volume روی /data مونت کنی، دیتابیس (bot.db) بعد از
# ری‌دیپلوی می‌ماند. اگر قابل نوشتن نباشد، bot.py خودش به ./data برمی‌گردد.
ENV DB_PATH=/data/bot.db \
    DOWNLOAD_DIR=/data/downloads
RUN mkdir -p /data/downloads

# نکته‌ی مهم برای پلتفرم‌های PaaS (Railway / VibeNest / Render / Fly …):
#   • پلتفرم متغیر PORT را ست می‌کند؛ bot.py همیشه اول از همه یک وب‌سرور
#     وضعیت روی 0.0.0.0:PORT بالا می‌آورد و مسیرهای / و /health و /healthz
#     را ۲۰۰ می‌کند (در غیر این صورت Healthcheck شکست می‌خورد و دامنه 404 می‌دهد).
#   • متغیرهای لازم: BOT_TOKEN و ADMIN_IDS (و اختیاری: FORCE_CHANNELS، LOG_CHANNEL،
#     COOKIES_B64، WEBHOOK_URL، PROXY_URL …) — با جزئیات در README/VIBENEST.md.
CMD ["/bin/sh", "/app/start.sh"]
