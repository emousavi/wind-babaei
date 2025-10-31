import os
import requests
import datetime as dt
import jdatetime
from dotenv import load_dotenv

# =========================
# ⚙️ تنظیمات کلی
# =========================
LAT, LON = 34.5858, 50.9066          # قم - سایت پروازی شهید بابایی
FLY_START_HOUR = 15                   # از ساعت 15 تا 18 تهران
FLY_END_HOUR = 18

# ✅ جهت مطلوب: از شرق‌شمال‌شرقی تا جنوب‌شرقی (۷۰° تا ۱۳۰°)
GOOD_DIR_MIN = 70.0
GOOD_DIR_MAX = 130.0

# ✅ محدوده‌ی سرعت باد (متر بر ثانیه)
MIN_OK = 3.0
MAX_OK = 6.0
MAX_CAUTION = 8.0

# بارگذاری متغیرها از فایل .env
load_dotenv()
OWM_API_KEY = os.getenv("OWM_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# 🕒 زمان محلی تهران
# =========================
def tehran_now():
    return dt.datetime.now(dt.UTC) + dt.timedelta(hours=3)

def from_txt_to_tehran(txt: str) -> dt.datetime:
    utc_naive = dt.datetime.strptime(txt, "%Y-%m-%d %H:%M:%S")
    return utc_naive + dt.timedelta(hours=3)

# =========================
# 📐 توابع کمکی
# =========================
def normalize_deg(deg: float) -> float:
    """نرمال‌سازی زاویه باد به بازه [0, 360)"""
    d = float(deg) % 360.0
    return d if d >= 0 else d + 360.0

def deg_to_direction(deg: float) -> str:
    """تبدیل عدد درجه به جهت فارسی"""
    dirs = ["شمال", "شمال‌شرقی", "شرق", "جنوب‌شرقی", "جنوب", "جنوب‌غربی", "غرب", "شمال‌غربی"]
    return dirs[int((deg + 22.5) // 45) % 8]

def in_dir_range(deg: float, dmin: float, dmax: float) -> bool:
    """بررسی قرارگیری زاویه در بازه مشخص"""
    d = normalize_deg(deg)
    if dmin <= dmax:
        return dmin <= d <= dmax
    return d >= dmin or d <= dmax

def to_persian_date(gregorian_date: dt.date) -> str:
    """تبدیل تاریخ میلادی به شمسی"""
    jdate = jdatetime.date.fromgregorian(date=gregorian_date)
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یک‌شنبه"]
    weekday = weekdays[jdate.weekday()]
    return f"{weekday}، {jdate.year}/{jdate.month:02d}/{jdate.day:02d}"

# =========================
# 🌬 دریافت داده‌ها از OpenWeatherMap
# =========================
def fetch_forecast():
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&appid={OWM_API_KEY}&units=metric"
    r = requests.get(url, timeout=25)
    data = r.json()
    if "list" not in data:
        raise RuntimeError(f"⛔ خطا در دریافت داده: {data}")
    return data

# =========================
# 🔍 تحلیل وضعیت پرواز
# =========================
def analyze_flight(speed: float, gust: float, deg: float) -> str:
    d = normalize_deg(deg)
    direction_fa = deg_to_direction(d)
    dir_ok = in_dir_range(d, GOOD_DIR_MIN, GOOD_DIR_MAX)
    gust_diff = gust - speed

    if not dir_ok:
        return f"🚫 باد از سمت {direction_fa} ({int(d)}°) نامناسب برای پرواز است. 🌬 سرعت {speed:.1f}، گاست {gust:.1f}"
    if MIN_OK <= speed <= MAX_OK and gust_diff <= 2:
        return f"✅ باد از سمت {direction_fa} ({int(d)}°) مناسب برای پرواز است. 🌬 سرعت {speed:.1f}، گاست {gust:.1f}"
    if MAX_OK < speed <= MAX_CAUTION and gust_diff <= 3:
        return f"⚠️ باد از سمت {direction_fa} ({int(d)}°) قابل پرواز ولی با احتیاط. 🌬 سرعت {speed:.1f}، گاست {gust:.1f}"
    if gust_diff > 2:
        return f"⚠️ باد از سمت {direction_fa} ({int(d)}°) دارای تلاطم (گاست زیاد) است. 🌬 سرعت {speed:.1f}، گاست {gust:.1f}"
    if speed < MIN_OK:
        return f"❌ باد از سمت {direction_fa} ({int(d)}°) بسیار ضعیف است. 🌬 سرعت {speed:.1f}"
    if speed > MAX_CAUTION:
        return f"🚫 باد از سمت {direction_fa} ({int(d)}°) بسیار شدید و خطرناک است. 🌬 سرعت {speed:.1f}"
    return f"⚠️ باد از سمت {direction_fa} ({int(d)}°) شرایط مرزی دارد. 🌬 سرعت {speed:.1f}، گاست {gust:.1f}"

# =========================
# 🧾 ساخت گزارش سه‌روزه
# =========================
def build_report():
    data = fetch_forecast()
    now_teh = tehran_now()
    today = now_teh.date()

    header = [
        "🪂 گزارش باد سه‌روزه – سایت پروازی شهید بابایی قم",
        "📍 بازه بررسی: ۱۵ تا ۱۸ تهران",
        "🧭 جهت مطلوب: از شرق‌شمال‌شرقی تا جنوب‌شرقی (۷۰° تا ۱۳۰°)\n"
    ]
    lines = ["\n".join(header)]

    for d in range(3):
        target_date = today + dt.timedelta(days=d)
        persian_date = to_persian_date(target_date)
        lines.append(f"\n📅 {persian_date}")
        found = False

        for item in data["list"]:
            t_txt = item["dt_txt"]
            t_teh = from_txt_to_tehran(t_txt)
            if t_teh.date() != target_date:
                continue
            if not (FLY_START_HOUR <= t_teh.hour <= FLY_END_HOUR):
                continue

            wind = item.get("wind", {})
            speed = float(wind.get("speed", 0.0))
            gust = float(wind.get("gust", speed))
            deg = float(wind.get("deg", 0.0))

            status = analyze_flight(speed, gust, deg)
            row = f"🕒 {t_teh.strftime('%H:%M')} → {status}"
            lines.append(row)
            found = True

        if not found:
            lines.append("⚠️ داده‌ای در بازه ۱۵ تا ۱۸ برای این روز موجود نیست.")

    return "\n".join(lines)

# =========================
# 📩 ارسال گزارش به تلگرام
# =========================
def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=20)
        print("📩 Telegram:", r.status_code)
    except Exception as e:
        print("❌ Telegram error:", e)

# =========================
# ⏰ زمان‌بندی و اجرای اصلی
# =========================
def should_send_now():
    now = tehran_now()
    return now.hour == 11 and now.minute < 10

def main(run_anyway=False):
    if run_anyway or should_send_now():
        try:
            report = build_report()
        except Exception as e:
            report = f"⛔ خطا در ساخت گزارش: {e}"
        send_telegram(report)
        print(report)
    else:
        print(f"⏱️ هنوز زمان ارسال نیست ({tehran_now().strftime('%H:%M')} تهران)")

if __name__ == "__main__":
    main()
#main(run_anyway=True)