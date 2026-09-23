#!/bin/sh
# ============================================================
#  راه‌اندازی کانتینر:
#    ۱) سرور PO-Token (bgutil) در پس‌زمینه — فقط اگر حافظه‌ی کانتینر کافی باشد
#    ۲) خودِ ربات (که اول از همه وب‌سرور Healthcheck را روی PORT بالا می‌آورد)
#
#  POT_SERVER: auto (پیش‌فرض) | 1 (همیشه روشن) | 0 (هرگز)
#    در پلن‌های کم‌حافظه — مثل پلن رایگان ۲۵۶MB بعضی پلتفرم‌ها — سرور Deno
#    (~۶۰-۱۰۰MB) خاموش می‌شود تا کانتینر با OOM کشته نشود و ربات نمیرد.
#    yt-dlp در آن حالت بدون PO-Token کار می‌کند (برای بعضی ویدیوهای یوتیوب
#    کوکی لازم می‌شود؛ COOKIES_B64 را ست کن).
# ============================================================
set -u

POT_SERVER="${POT_SERVER:-auto}"
POT_DIR=/opt/pot/server

if [ "$POT_SERVER" = "auto" ]; then
    LIMIT_BYTES=""
    if [ -r /sys/fs/cgroup/memory.max ]; then
        LIMIT_BYTES=$(cat /sys/fs/cgroup/memory.max 2>/dev/null)
    elif [ -r /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
        LIMIT_BYTES=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null)
    fi
    case "$LIMIT_BYTES" in
        ""|"max") POT_SERVER=1 ;;   # محدودیت مشخصی نداریم → روشن بماند
        *)
            if [ "$LIMIT_BYTES" -ge 600000000 ] 2>/dev/null; then
                POT_SERVER=1
            else
                POT_SERVER=0
            fi
            ;;
    esac
    echo "[start.sh] memory limit=${LIMIT_BYTES:-unknown} → POT_SERVER=$POT_SERVER"
fi

if [ "$POT_SERVER" = "1" ] && [ -f "$POT_DIR/src/main.ts" ] && [ -d "$POT_DIR/node_modules" ]; then
    deno run \
        --allow-env \
        --allow-net \
        --allow-ffi="$POT_DIR/node_modules" \
        --allow-read="$POT_DIR" \
        "$POT_DIR/src/main.ts" >/tmp/pot.log 2>&1 &
    echo "[start.sh] bgutil PO-token provider started (deno, port 4416)"
elif [ "$POT_SERVER" = "0" ]; then
    echo "[start.sh] POT provider disabled on purpose (low-memory container) — yt-dlp fallbacks only"
else
    echo "[start.sh] WARNING: pot provider server missing — continuing without it"
fi

exec python bot.py
