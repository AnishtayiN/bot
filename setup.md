# راهنمای کامل نصب و اجرای ربات موزیک‌یاب تلگرام روی سرور خام کالی

> بدون `sudo` — فرض بر لاگین با کاربر `root` است.

---

## مرحله ۱ — پیش‌نیازهای سیستمی

```bash
apt update
apt install -y python3 python3-pip python3-venv git curl unzip ffmpeg build-essential python3-dev pkg-config libasound2-dev
ffmpeg -version
python3 --version
```

---

## مرحله ۲ — نصب Deno (برای دانلود یوتیوب واجب است)

```bash
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
deno --version
```

---

## مرحله ۳ — نصب Node 20 (برای PO-Token واجب است؛ نود پیش‌فرض دبیان کافی نیست)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
node --version
npm --version
```

---

## مرحله ۴ — کلون ریپوی پرایوت

```bash
mkdir -p /root/bot && cd /root/bot
git clone https://<GITHUB_TOKEN>@github.com/AnishtayiN/bot.git .
ls -la
```

- به‌جای `<GITHUB_TOKEN>` توکن گیت‌هاب را بگذار.
- ⚠️ توکن را بعد از کار از گیت‌هاب **Revoke** کن.

---

## مرحله ۵ — نصب پایتون ۳.۱۲ با `uv` (مهم!)

پایتون پیش‌فرض کالی (۳.۱۴) با `shazamio` سازگار نیست و **Segmentation fault** می‌دهد.
راه‌حل: پایتون ۳.۱۲ جداگانه با `uv` نصب می‌شود (به `apt` کاری ندارد):

```bash
curl -fsSL https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
uv python install 3.12
uv python list
```

ساخت `venv` تمیز با ۳.۱۲:

```bash
cd /root/bot
rm -rf .venv
uv venv --python 3.12 .venv
```

> نکته: `uv venv` ابزار `pip` داخل `venv` نمی‌گذارد، پس نصب پکیج‌ها با `uv pip` است:

```bash
uv pip install --python .venv/bin/python --upgrade pip
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python -U "yt-dlp>=2026.8.19" yt-dlp-ejs "bgutil-ytdlp-pot-provider>=1.3,<2"
```

تست نصب:

```bash
./.venv/bin/python -c "import telegram, yt_dlp, shazamio; print('ok')"
./.venv/bin/python -c "from bot import js_runtime_status; import json; print(json.dumps(js_runtime_status(), indent=2))"
```

- باید `ok` بدهد و `deno_ok` برابر `true` باشد.
- هشدارهای `SyntaxWarning` مربوط به `pydub` مهم نیستند.

---

## مرحله ۶ — ساخت فایل تنظیمات

```bash
cd /root/bot
cat > .env <<'EOF'
BOT_TOKEN=123456789:AAxxxx
ADMIN_IDS=123456789
EOF
```

- `BOT_TOKEN` را از [@BotFather](https://t.me/BotFather) بگیر.
- `ADMIN_IDS` (آیدی عددی خودت) را از [@userinfobot](https://t.me/userinfobot) بگیر.

---

## مرحله ۷ — تست اجرا

```bash
cd /root/bot
./.venv/bin/python bot.py
```

- اگر بالا آمد و در تلگرام جواب داد، با `Ctrl+C` بیرون بیا.
- اگر از `BOT_TOKEN` ایراد گرفت، فایل `.env` را چک کن.

---

## مرحله ۸ — اجرای دائمی با `tmux` (چون `systemd` در کانتینر نیست)

```bash
apt install -y tmux
cat > /root/bot/run.sh <<'EOF'
#!/bin/bash
cd /root/bot
export PATH="$HOME/.deno/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
while true; do
  /root/bot/.venv/bin/python /root/bot/bot.py >> /root/bot/bot.log 2>&1
  echo "[run.sh] crashed at $(date), restarting in 5s..." >> /root/bot/bot.log
  sleep 5
done
EOF
chmod +x /root/bot/run.sh
tmux new -d -s bot /root/bot/run.sh
sleep 3
tmux ls
tail -n 30 /root/bot/bot.log
```

باید پیام `Bot @... started successfully` را ببینی.

---

## دستورات نگهداری

```bash
tail -f /root/bot/bot.log                 # دیدن لاگ زنده (خروج با Ctrl+C؛ بات روشن می‌ماند)
tmux attach -t bot                        # رفتن داخل سشن (خروج بدون کشتن بات: Ctrl+B بعد D)
tmux ls                                   # دیدن سشن‌ها
ps aux | grep "[b]ot.py" | grep -v grep   # باید فقط یک خط بات ببینی؛ دو خط یعنی دو نمونه درگیرند
```

### ری‌استارت تمیز

وقتی دو نمونه همزمان بالا هستند یا ارور `Address already in use` دیدی:

```bash
pkill -f run.sh
pkill -f "bot.py"
sleep 3
ps aux | grep "[b]ot" | grep -v grep
tmux kill-server
sleep 2
tmux new -d -s bot /root/bot/run.sh
sleep 4
tail -n 8 /root/bot/bot.log
```

---

## کوکی یوتیوب

اگر بات گفت یوتیوب نیازمند ورود است:

1. در کروم سیستم خودت به `youtube.com` برو و لاگین کن.
2. افزونه **Get cookies.txt LOCALLY** را باز کن و دکمه **Export** (فقط همین سایت، نه Export all) را بزن.
3. متن فایل را کامل در سرور جایگزین کن:

```bash
cd /root/bot
cat > cookies.txt
# (پیست متن، Enter، بعد Ctrl+D)
```

4. چک کن کوکی لاگین واقعی باشد (باید بالای ۲۰ خط یوتیوب و خط‌های `SID` و `LOGIN_INFO` باشند):

```bash
grep -c "youtube.com" cookies.txt
grep -E "SID|LOGIN_INFO" cookies.txt | head -n 5
```

5. ری‌استارت بات:

```bash
pkill -f "bot.py"
sleep 8
grep -i "cookies" /root/bot/bot.log | tail -n 2
# (باید cookies found بنویسد)
```

> ⚠️ **هشدار امنیتی:** کوکی‌ها معادل پسورد گوگل هستند؛ در چت یا جای ناامن پخش نکن.
> اگر لو رفت، از گوگل همه سشن‌ها را Sign out کن تا بی‌اعتبار شوند.

---

## عیب‌یابی سریع

| مشکل | راه‌حل |
|---|---|
| لینکر `cc` پیدا نشد (نصب `shazamio`) | `apt install -y build-essential python3-dev pkg-config libasound2-dev` |
| ارور `audioop` / `pyaudioop` | یعنی پایتون ۳.۱۴ داری؛ برو مرحله ۵ و با `uv` پایتون ۳.۱۲ بساز |
| `Segmentation fault` موقع اجرا | یعنی پایتون ۳.۱۴ داری؛ برو مرحله ۵ |
| `Unable to locate package python3.12` | طبیعی است؛ کالی رولینگ ۳.۱۲ ندارد — با `uv` نصب کن (مرحله ۵) |
| داکر بالا نمی‌آید (`permission denied` روی `iptables`) | داخل کانتینر غیرprivileged هستی؛ بیخیال داکر شو و همین روش بدون داکر را برو |
| `Address already in use` | دو نمونه بات همزمان بالاست؛ ری‌استارت تمیز را بزن |
| بات جواب نمی‌دهد ولی لاگ سالم است | `ps` را چک کن که فقط یک نمونه باشد؛ توکن را در `.env` چک کن |
| یوتیوب Sign in می‌خواهد | بخش کوکی یوتیوب را انجام بده |
| `nano` پیدا نشد | `apt install -y nano` یا با `cat >` فایل بساز |
