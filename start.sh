#!/bin/sh
# راه‌اندازی کانتینر: اول سرور PO-Token (bgutil) در پس‌زمینه، بعد خودِ ربات.
# اگر سرور توکن به هر دلیلی بالا نیاید، ربات بدون آن هم کار می‌کند (گرس‌مود yt-dlp).

POT_DIR=/opt/pot/server
if [ -f "$POT_DIR/src/main.ts" ] && [ -d "$POT_DIR/node_modules" ]; then
    deno run \
        --allow-env \
        --allow-net \
        --allow-ffi="$POT_DIR/node_modules" \
        --allow-read="$POT_DIR" \
        "$POT_DIR/src/main.ts" >/tmp/pot.log 2>&1 &
    echo "[start.sh] bgutil PO-token provider started (deno, port 4416)"
else
    echo "[start.sh] WARNING: pot provider server missing — continuing without it"
fi

exec python bot.py
