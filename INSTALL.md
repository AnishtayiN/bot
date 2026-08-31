# 🚀 راهنمای نصب و اجرای ربات

## پیش‌نیازها

| پیش‌نیاز | نصب |
|----------|------|
| Python 3.10+ | از python.org |
| ffmpeg | `sudo apt install ffmpeg` (Linux) / `choco install ffmpeg` (Windows) |
| Git | `sudo apt install git` / `choco install git` |
| Deno (برای یوتیوب) | `curl -fsSL https://deno.land/install.sh \| sh` |

---

## ۱. نصب کتابخانه‌ها

```bash
git clone https://github.com/AnishtayiN/bot.git
cd bot
pip install -r requirements.txt
```

## ۲. تنظیمات

```bash
cp .env.example .env
```

فایل `.env` را ویرایش کنید:

```env
BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxx    # از @BotFather
ADMIN_IDS=123456789                            # آیدی عددی شما از @userinfobot
FORCE_CHANNELS=@your_channel                   # کانال جوین اجباری (اختیاری)
```

## ۳. کوکی (اختیاری ولی توصیه‌شده)

فایل `cookies.txt` با فرمت **Netscape** کنار `bot.py` بگذارید:

- **Chrome:** افزونه *Get cookies.txt LOCALLY* نصب کنید
- **یوتیوب:** برای رفع خطای "Sign in to confirm"
- **اینستاگرام:** برای اکانت‌های خصوصی
- **تیک‌تاک/ساند‌کلود:** معمولاً بدون کوکی کار می‌کنند

برای Railway (بدون آپلود فایل):

```bash
# لینوکس/Mac:
base64 -w0 cookies.txt

# ویندوز PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard
```

خروجی را در متغیر `COOKIES_B64` در Railway بگذارید.

## ۴. اجرا

```bash
python bot.py
```

---

## 🐳 اجرا با Docker

```bash
docker build -t musicbot .
docker run -d --name musicbot --restart=always \
  -e BOT_TOKEN=YOUR_TOKEN \
  -e ADMIN_IDS=YOUR_ID \
  musicbot
```

## 🚂 دیپلوی روی Railway

1. ریپو را به GitHub push کنید
2. [railway.com](https://railway.com) → New Project → Deploy from GitHub repo
3. در تب **Variables** اینها را اضافه کنید:

```env
BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=123456789
FORCE_CHANNELS=@your_channel
```

4. Railway خودکار دیپلوی می‌کند
5. (اختیاری) برای ماندگاری دیتابیس: Settings → Storage → New Volume → مسیر: `/data`

## 🔄 اجرای دائمی (Linux systemd)

```bash
sudo tee /etc/systemd/system/musicbot.service > /dev/null <<EOF
[Unit]
Description=MusicFinder Telegram Bot
After=network.target

[Service]
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 /path/to/bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now musicbot
journalctl -u musicbot -f    # مشاهده لاگ
```

---

## 📦 پیش‌نیازهای یوتیوب (مهم!)

از `yt-dlp 2026.08.12+` حتماً نیاز به:

1. **Runtime جاوااسکریپت** (Deno ≥ 2.3 یا Node ≥ 22):
   ```bash
   # Deno (توصیه‌شده)
   curl -fsSL https://deno.land/install.sh | sh
   ```

2. **بسته yt-dlp-ejs**:
   ```bash
   pip install -U "yt-dlp>=2026.8.19" yt-dlp-ejs
   ```

3. **PO-Token (اختیاری ولی مفید)**:
   ```bash
   pip install "bgutil-ytdlp-pot-provider>=1.3,<2"
   ```

برای بررسی سلامت:
```bash
python -c "from bot import js_runtime_status; import json; print(json.dumps(js_runtime_status(), indent=2))"
```

---

## 🔧 عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| ربات استارت نمی‌شود | توکن `BOT_TOKEN` و `ADMIN_IDS` را در `.env` چک کنید |
| دانلود یوتیوب fail می‌شود | `cookies.txt` معتبر + Deno نصب باشد |
| "Sign in to confirm" | کوکی جدید یوتیوب با IP سرور export کنید |
| Shazam کار نمی‌کند | `ffmpeg` نصب باشد |
| دکمه‌ها منقضی شد | ویدیو را دوباره بفرستید (۴۵ دقیقه اعتبار) |
| خطای 429 | کمی صبر کنید (محدودیت موقتی یوتیوب) |
