# ============================================================
#  ربات دانلود ویدیو/موزیک — ایمیج سبک برای Railway / هر سرور داکری
#  ffmpeg به‌صورت static نصب می‌شود تا نصب بسته‌ی Debian صدها مگابایت
#  dependency (و خطای کمبود فضای /var/cache/apt/archives) ایجاد نکند.
# ============================================================
FROM python:3.12-slim

# برای اینکه Railway در صورت نیاز لایه‌ی قبلی را دوباره استفاده نکند.
ARG CACHEBUST=1
ARG POT_VERSION=1.3.2

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DENO_NO_PROMPT=1 \
    DENO_NO_UPDATE_CHECK=1

# ffmpeg/ffprobe از یک build استاتیک می‌آیند؛ بسته‌ی Debianِ ffmpeg روی
# Python slim فعلی حدود ۵۷۶MB dependency می‌کشد و Railway ممکن است قبل از
# نصب، در /var/cache/apt/archives با خطای کمبود فضا متوقف شود.
# Deno برای yt-dlp و provider توکن، و xz/unzip فقط برای باز کردن آرشیوها هستند.
ARG FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        unzip \
        xz-utils \
    && curl -fsSL "$FFMPEG_URL" -o /tmp/ffmpeg.tar.xz \
    && tar -xJf /tmp/ffmpeg.tar.xz -C /tmp \
    && install -m 0755 /tmp/ffmpeg-*/bin/ffmpeg /usr/local/bin/ffmpeg \
    && install -m 0755 /tmp/ffmpeg-*/bin/ffprobe /usr/local/bin/ffprobe \
    && curl -fsSL -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && ffmpeg -version | head -1 \
    && deno --version \
    && rm -rf /tmp/ffmpeg-* /tmp/ffmpeg.tar.xz /tmp/deno.zip \
        /var/lib/apt/lists/* /var/cache/apt/archives/*

# سرور PO-Token (bgutil) با Deno — نسخه را با requirements.txt هماهنگ نگه می‌داریم.
# خود Deno می‌تواند dependencyهای npm را نصب کند؛ بنابراین Node/npm و git
# را وارد image نمی‌کنیم و حجم/فضای build پایین می‌ماند.
# --allow-scripts برای نصب native dependency مربوط به canvas لازم است.
RUN mkdir -p /opt /tmp/pot-src \
    && curl -fsSL \
        "https://github.com/Brainicism/bgutil-ytdlp-pot-provider/archive/refs/tags/${POT_VERSION}.tar.gz" \
        | tar -xz -C /tmp/pot-src \
    && mv "/tmp/pot-src/bgutil-ytdlp-pot-provider-${POT_VERSION}" /opt/pot \
    && cd /opt/pot/server \
    && deno install --allow-scripts=npm:canvas --frozen \
    && deno cache --frozen src/main.ts \
    && rm -rf /tmp/pot-src

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot.py .env.example README.md start.sh ./
RUN chmod +x start.sh

# مسیر داده‌ها: در Railway یک Volume روی همین /data مونت کن
# تا دیتابیس (bot.db) بعد از هر ری‌دیپلوی از دست نرود.
ENV DB_PATH=/data/bot.db \
    DOWNLOAD_DIR=/data/downloads
RUN mkdir -p /data/downloads

CMD ["/bin/sh", "/app/start.sh"]
