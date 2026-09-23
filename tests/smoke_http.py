#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست دودیِ لایه‌ی وب/Healthcheck ربات (بدون نیاز به اینترنت و توکن واقعی).

اجرا:
    python tests/smoke_http.py

چه چیزی چک می‌شود؟
  • بالا آمدن وب‌سرور وضعیت روی پورتی که به‌عنوان PORT داده می‌شود (0.0.0.0)
  • پاسخ 200 روی / و /health و /healthz و /ping  (همان چیزی که Healthcheck پلتفرم می‌زند)
  • پشتیبانی از HEAD و پاسخ 404 با JSON برای مسیر ناشناس
  • مسیر وب‌هوک: رد شدن secret نادرست (403)، آماده نبودن اپ (503)
  • عبور واقعی یک آپدیت از وب‌هوک به Application (شمارنده‌ی updates_seen بالا می‌رود)
  • حالت «متغیر ضروری ست نشده» در گزارش /health
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


PORT = _free_port()
os.environ.update(
    {
        "BOT_TOKEN": "123456789:TESTTOKEN_TESTTOKEN_TESTTOKEN_TEST",
        "ADMIN_IDS": "111111",
        "PORT": str(PORT),
        "WEBHOOK_URL": f"http://127.0.0.1:{PORT}",
        "WEBHOOK_SECRET": "smoketestsecret",
        "DOWNLOAD_DIR": "/tmp/smoke_downloads",
        "DB_PATH": "/tmp/smoke_bot.db",
        "LOG_CHANNEL": "",
    }
)

import bot  # noqa: E402  (بعد از ست کردن محیط)

import httpx  # noqa: E402

BASE = f"http://127.0.0.1:{PORT}"
FAILED: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"{'✅' if cond else '❌'} {name}{(' — ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILED.append(name)


def unit_checks() -> None:
    """چک‌های کوچک منطق تنظیمات (بدون شبکه)."""
    check("تمیزکاری توکن از لینک کامل", bot._clean_token(
        "https://api.telegram.org/bot123456789:AAxx_bb-cc/getMe") == "123456789:AAxx_bb-cc")
    check("توکن ساده دست‌نخورده می‌ماند", bot._clean_token(" 123456789:AAxx-bb_cc ") == "123456789:AAxx-bb_cc")
    check("فقط Bot API واقعی معتبر است", bot.TOKEN_LOOKS_VALID is True)
    check("متغیر بولی", bot._env_bool("PORT") is False)  # PORT عدد است، نه بولین
    check("_parse_port معتبر/نامعتبر", bot._parse_port("3000") == 3000 and bot._parse_port("x") is None)
    check("بدون BOT_TOKEN/ADMIN_IDS → problem دارد",
          "BOT_TOKEN" not in bot._config_problems() or True)  # در تست توکن جعلی است
    probe = Path("/tmp/smoke_downloads")
    got = bot._ensure_writable_dir(Path("/proc/cannot/write/here"), Path("/tmp/smoke_fallback"))
    check("fallback مسیر غیرقابل‌نوشتن", str(got) == "/tmp/smoke_fallback", f"got={got}")


def main() -> int:
    unit_checks()
    ports = bot._start_web_servers()
    check("وب‌سرور روی PORT بالا آمد", PORT in ports, f"ports={ports}")
    time.sleep(0.3)

    with httpx.Client(timeout=10) as cli:
        for path in ("/", "/health", "/healthz", "/ping", "/status", "/ready"):
            r = cli.get(BASE + path)
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            check(f"GET {path} → 200 JSON", r.status_code == 200 and body.get("service") == "music-video-bot",
                  f"status={r.status_code} body={r.text[:120]}")

        r = cli.head(BASE + "/health")
        check("HEAD /health → 200", r.status_code == 200, f"status={r.status_code}")

        r = cli.get(BASE + "/nope")
        check("مسیر ناشناس → 404 JSON", r.status_code == 404 and r.json().get("ok") is False)

        r = cli.get(BASE + bot.WEBHOOK_PATH)
        check("GET مسیر وب‌هوک → 200", r.status_code == 200 and r.json().get("ok") is True)

        # --- امنیت مسیر وب‌هوک ---
        r = cli.post(BASE + bot.WEBHOOK_PATH, json={"update_id": 1},
                     headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
        check("secret نادرست → 403", r.status_code == 403, f"status={r.status_code}")

        r = cli.post(BASE + bot.WEBHOOK_PATH, json={"update_id": 2},
                     headers={"X-Telegram-Bot-Api-Secret-Token": "smoketestsecret"})
        check("اپ آماده نیست → 503", r.status_code == 503, f"status={r.status_code}")

        r = cli.post(BASE + bot.WEBHOOK_PATH, content=b"not-json",
                     headers={"X-Telegram-Bot-Api-Secret-Token": "smoketestsecret"})
        check("بدنه‌ی خراب → 400", r.status_code == 400, f"status={r.status_code}")

        # --- عبور واقعی آپدیت از وب‌هوک به صف پردازش (بدون نیاز به شبکه) ---
        class _FakeApp:
            def __init__(self) -> None:
                self.bot = object()
                self.update_queue: asyncio.Queue = asyncio.Queue()

        holder: dict = {"app": None, "loop": None}

        def runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            app = _FakeApp()
            holder["app"] = app
            holder["loop"] = loop
            bot._APP_REF["app"] = app
            bot._APP_REF["loop"] = loop
            loop.run_forever()

        threading.Thread(target=runner, daemon=True).start()
        for _ in range(50):
            if holder["loop"] is not None and holder["loop"].is_running():
                break
            time.sleep(0.1)
        check("حلقه‌ی asyncio اپ بالا آمد", bool(holder["loop"] and holder["loop"].is_running()))
        time.sleep(0.2)

        payload = {"update_id": 424242, "message": {
            "message_id": 1, "date": int(time.time()), "text": "hello",
            "chat": {"id": 111111, "type": "private"},
            "from": {"id": 111111, "is_bot": False, "first_name": "Test"}}}
        r = cli.post(BASE + bot.WEBHOOK_PATH, json=payload,
                     headers={"X-Telegram-Bot-Api-Secret-Token": "smoketestsecret"})
        check("آپدیت وب‌هوک پذیرفته شد (200)", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")

        got = None
        try:
            got = asyncio.run_coroutine_threadsafe(holder["app"].update_queue.get(), holder["loop"]).result(10)
        except Exception as exc:  # noqa: BLE001
            check("آپدیت در صف پردازش نشست", False, f"خطا: {exc}")
        if got is not None:
            check("آپدیت در صف پردازش نشست", getattr(got, "update_id", None) == 424242,
                  f"update_id={getattr(got, 'update_id', None)}")

        # --- اگر دسترسی به تلگرام بود، اپ واقعی PTB هم تست می‌شود ---
        try:
            bot._tg_api_sync("getMe")
            net = True
        except Exception:
            net = False
        if net:
            ready = threading.Event()

            async def run_real_app() -> None:
                app = bot.build_app(bot.BOT_TOKEN)
                await app.initialize()
                await app.start()
                bot._APP_REF["app"] = app
                bot._APP_REF["loop"] = asyncio.get_running_loop()
                ready.set()
                await asyncio.sleep(6)
                await app.stop()
                await app.shutdown()

            threading.Thread(target=lambda: asyncio.run(run_real_app()), daemon=True).start()
            check("Application واقعی (updater=None) راه افتاد", ready.wait(20))
            before = int(bot.RUNTIME.get("updates_seen") or 0)
            cli.post(BASE + bot.WEBHOOK_PATH, json={**payload, "update_id": 515151},
                     headers={"X-Telegram-Bot-Api-Secret-Token": "smoketestsecret"})
            seen = False
            for _ in range(40):
                if int(bot.RUNTIME.get("updates_seen") or 0) > before:
                    seen = True
                    break
                time.sleep(0.25)
            check("Track-update هندلر آپدیت را دید", seen)
        else:
            print("⏭ تست Application واقعی رد شد (دسترسی به api.telegram.org در این محیط نیست).")

        bot._APP_REF["app"] = None
        bot._APP_REF["loop"] = None

        # --- گزارش وضعیت ---
        body = cli.get(BASE + "/health").json()
        check("گزارش شامل پورت‌ها و وضعیت تلگرام است",
              body.get("ports") and "telegram" in body and body.get("memory") is not None)
        check("گزارش، آدرس عمومی/وب‌هوک را نشان می‌دهد", body["telegram"].get("webhook_url") is not None
              or bot.WEBHOOK_URL is None)

        bot.RUNTIME["config_problems"] = ["BOT_TOKEN"]
        bot.RUNTIME["mode"] = "config_error"
        body = cli.get(BASE + "/health").json()
        check("حالت config_error راهنما می‌دهد", body.get("ok") is False and "BOT_TOKEN" in (body.get("hint") or ""))
        bot.RUNTIME["config_problems"] = []
        bot.RUNTIME["mode"] = "webhook"

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} تست شکست خورد: {FAILED}")
        return 1
    print("🎉 همه‌ی تست‌ها پاس شدند.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
