# -*- coding: utf-8 -*-
"""
Auto Trend Lines Multi-Timeframe Scanner (4H & 1D)
يقوم بفحص أزواج بينانس سبوت على فريم الأربع ساعات (4H) والفريم اليومي (1D)
لرصد ملامسة السعر لخط الترند الأخضر (الدعم) وإرسال إشعار فوري عبر تليجرام.
"""

import sys
import time
import datetime
import argparse
import requests
import pandas as pd
import numpy as np

# ضبط ترميز النصوص
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==========================================
# ⚙️ الإعدادات العامة (Configuration)
# ==========================================
TELEGRAM_BOT_TOKEN = "8913224513:AAHSWPospHVspn49uTG_ifcAdmxBle-iMjg"
TELEGRAM_CHAT_ID = "7760401819"

# الفريمات المطلوبة: 4 ساعات + اليومي
TIMEFRAMES = ["4h", "1d"]

# قائمة أشهر أزواج السبوت على بينانس
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT",
    "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT", "NEARUSDT", "SUIUSDT",
    "APTUSDT", "FETUSDT", "RENDERUSDT", "INJUSDT", "OPUSDT", "ARBUSDT",
    "TIAUSDT", "SEIUSDT", "RUNEUSDT", "AAVEUSDT", "UNIUSDT", "LTCUSDT",
    "GALAUSDT", "SANDUSDT", "MANAUSDT", "AXSUSDT", "FTMUSDT", "ATOMUSDT",
    "ICPUSDT", "KASUSDT", "PEPEUSDT", "SHIBUSDT", "WLDUSDT", "ENAUSDT",
    "PENDLEUSDT", "TONUSDT", "PYTHUSDT", "JUPUSDT", "ONDOUSDT", "BONKUSDT"
]

BINANCE_ENDPOINTS = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
    "https://api1.binance.com/api/v3/klines"
]

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


# ==========================================
# 📡 جلب بيانات الشموع من بينانس
# ==========================================
def fetch_klines(symbol: str, interval: str = "4h", limit: int = 120):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    for endpoint in BINANCE_ENDPOINTS:
        try:
            resp = session.get(endpoint, params=params, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, list) and len(data) >= 50:
                    df = pd.DataFrame(data, columns=[
                        "open_time", "open", "high", "low", "close", "volume",
                        "close_time", "q_vol", "trades", "tb_vol", "tq_vol", "ignore"
                    ])
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = df[col].astype(float)
                    return df
        except Exception:
            continue
    return None


# ==========================================
# 📐 خوارزمية Auto Trend Lines (خط الدعم الأخضر)
# ==========================================
def detect_auto_trendline_touch(df: pd.DataFrame, timeframe: str = "4h", left_bars: int = 7, right_bars: int = 3):
    n = len(df)
    if n < 50:
        return None

    lows = df['low'].values
    highs = df['high'].values
    closes = df['close'].values
    opens = df['open'].values

    # 1. استخراج نقاط القيعان (Pivot Lows)
    pivot_indices = []
    pivot_values = []

    for i in range(left_bars, n - right_bars - 1):
        is_pivot = True
        val = lows[i]
        for j in range(i - left_bars, i + right_bars + 1):
            if j != i and lows[j] < val:
                is_pivot = False
                break
        if is_pivot:
            pivot_indices.append(i)
            pivot_values.append(val)

    if len(pivot_indices) < 2:
        return None

    # نأخذ آخر قاعين رئيسيين لتحديد خط الترند الأخضر
    idx1, idx2 = pivot_indices[-2], pivot_indices[-1]
    low1, low2 = pivot_values[-2], pivot_values[-1]

    dx = idx2 - idx1
    if dx <= 0:
        return None
    slope = (low2 - low1) / dx

    if slope < -0.003 * low2:
        return None

    # التأكد من عدم كسر الخط سابقاً
    for k in range(idx1, n - 1):
        line_k = low1 + slope * (k - idx1)
        if closes[k] < line_k * 0.988:
            return None

    # قيمة خط الترند الأخضر عند الشمعة الأخيرة
    curr_idx = n - 1
    green_line_value = low1 + slope * (curr_idx - idx1)

    curr_open = opens[-1]
    curr_close = closes[-1]
    curr_high = highs[-1]
    curr_low = lows[-1]

    # شروط ملامسة واحترام الخط الأخضر
    touched_line = curr_low <= (green_line_value * 1.008)
    held_support = (curr_low >= green_line_value * 0.985) and (curr_close >= green_line_value * 0.995)
    
    is_green = curr_close >= curr_open
    lower_wick = min(curr_open, curr_close) - curr_low
    has_wick_rejection = lower_wick >= (0.35 * (curr_high - curr_low)) if (curr_high - curr_low) > 0 else False
    is_bounce = is_green or has_wick_rejection

    if touched_line and held_support and is_bounce:
        stop_loss = green_line_value * 0.985
        risk = curr_close - stop_loss
        if risk <= 0:
            return None

        tp1 = curr_close + (1.5 * risk)
        tp2 = curr_close + (2.5 * risk)

        sl_pct = ((curr_close - stop_loss) / curr_close) * 100
        tp1_pct = ((tp1 - curr_close) / curr_close) * 100
        tp2_pct = ((tp2 - curr_close) / curr_close) * 100

        # أقصى وقف خسارة مسموح به (6.5% للـ 4H و 9.5% لليومي)
        max_sl = 9.5 if timeframe == "1d" else 6.5
        if sl_pct > max_sl or sl_pct < 0.6:
            return None

        return {
            "timeframe": timeframe,
            "green_line_value": green_line_value,
            "entry_price": curr_close,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "sl_pct": sl_pct,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "slope_type": "صاعد 📈" if slope > 0 else "قناة تجميعية 📊"
        }

    return None


# ==========================================
# 💬 إرسال إشعار تليجرام
# ==========================================
def send_telegram_alert(symbol: str, signal_data: dict, bot_token: str, chat_id: str):
    if not bot_token or not chat_id:
        return

    clean_symbol = symbol.replace("USDT", "")
    tf = signal_data.get("timeframe", "4h")
    tf_text = "يومي (1D) 💎 [سوينج رئيسي]" if tf == "1d" else "4 ساعات (4H) ⚡ [سوينج سريع]"

    message = f"""🟢 *تنبيه تريند لاين: ملامسة الخط الأخضر* 🟢
━━━━━━━━━━━━━━━━━━━━
🎯 *العملة:* `#{clean_symbol}` ({symbol})
⏰ *الفريم:* {tf_text}
📈 *نوع الترند:* {signal_data['slope_type']}
━━━━━━━━━━━━━━━━━━━━
💵 *سعر الدخول:* `{signal_data['entry_price']:.4f}`
🟩 *قيمة الترند الأخضر:* `{signal_data['green_line_value']:.4f}`
🛑 *وقف الخسارة (SL):* `{signal_data['stop_loss']:.4f}` (-{signal_data['sl_pct']:.2f}%)
🎯 *الهدف الأول (TP1):* `{signal_data['tp1']:.4f}` (+{signal_data['tp1_pct']:.2f}%)
🏆 *الهدف الثاني (TP2):* `{signal_data['tp2']:.4f}` (+{signal_data['tp2_pct']:.2f}%)
━━━━━━━━━━━━━━━━━━━━
💡 *السبب:* ملامسة دقيقة لخط الدعم الأخضر مع ارتداد شرائي مؤكد.
🔗 [فتح الشارت على TradingView](https://www.tradingview.com/chart/?symbol=BINANCE:{symbol})
"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        session.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"⚠️ خطأ أثناء الإرسال لـ {symbol}: {e}")


# ==========================================
# 🔍 دورة الفحص الكاملة
# ==========================================
def run_scan(bot_token="", chat_id="", notify=False):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now_str}] 🚀 بدء فحص ملامسة الخط الأخضر لـ {len(WATCHLIST)} عملة على فريمات {TIMEFRAMES}...")
    
    hits = 0
    for tf in TIMEFRAMES:
        tf_title = "4 ساعات (4H)" if tf == "4h" else "اليومي (1D)"
        print(f"\n⏳ جاري فحص فريم: {tf_title}...")
        for symbol in WATCHLIST:
            df = fetch_klines(symbol, interval=tf, limit=120)
            if df is None:
                continue

            result = detect_auto_trendline_touch(df, timeframe=tf)
            if result:
                hits += 1
                print(f"  🔥 تم رصد إشارة [{tf}] على {symbol} | سعر: {result['entry_price']:.4f} | ترند أخضر: {result['green_line_value']:.4f}")
                if notify and bot_token and chat_id:
                    send_telegram_alert(symbol, result, bot_token, chat_id)
            time.sleep(0.08)

    print(f"\n✅ انتهى الفحص الشامل: تم رصد {hits} فرصة ملامسة للخط الأخضر (4H + 1D).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="تشغيل مرة واحدة")
    parser.add_argument("--loop", action="store_true", help="تشغيل مستمر كل 4 ساعات")
    parser.add_argument("--notify", action="store_true", help="إرسال لتليجرام")
    parser.add_argument("--token", type=str, default="")
    parser.add_argument("--chat", type=str, default="")
    args = parser.parse_args()

    token = args.token or TELEGRAM_BOT_TOKEN
    chat = args.chat or TELEGRAM_CHAT_ID

    if args.loop:
        print("🔄 تم تفعيل وضع المراقبة الدورية (الفحص سيعمل كل 4 ساعات على الفريمين)...")
        while True:
            run_scan(bot_token=token, chat_id=chat, notify=args.notify)
            time.sleep(4 * 60 * 60)
    else:
        run_scan(bot_token=token, chat_id=chat, notify=args.notify)
