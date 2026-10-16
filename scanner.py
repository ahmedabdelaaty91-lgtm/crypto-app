# scanner.py
"""
Main Scanner Script for 160 Spot Coins across 10 Strategies.
Fetches Binance Spot candle data concurrently, evaluates strategies on 4H & 1D,
and generates trade signals with SL/TP targets.
"""

import argparse
import concurrent.futures
import os
import sys
import time
import requests
import pandas as pd
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import BINANCE_API_URL, COINS_RAW, SYMBOL_ALIASES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TIMEFRAMES, ENABLE_TESTNET_TRADING, TESTNET_TRADE_AMOUNT_USDT
from strategies import evaluate_strategies, calculate_atr, find_structural_support, calculate_ema, calculate_rsi
from telegram_notifier import send_telegram_alert, format_signal_message, format_price
from trade_tracker import record_new_trade, send_daily_report_to_telegram

# Global session with connection pooling
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount("https://", adapter)
session.mount("http://", adapter)
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})


def fetch_klines(symbol: str, interval: str, limit: int = 100):
    """Fetches kline/candlestick data for a symbol from Binance with multi-endpoint fallback."""
    endpoints = [
        BINANCE_API_URL,
        "https://data-api.binance.vision/api/v3",
        "https://api1.binance.com/api/v3",
        "https://api.binance.com/api/v3",
    ]
    seen = set()
    clean_endpoints = [x for x in endpoints if not (x in seen or seen.add(x))]

    for base_url in clean_endpoints:
        url = f"{base_url}/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            resp = session.get(url, params=params, timeout=5)
            if resp.status_code != 200:
                continue
            raw = resp.json()
            if not raw or not isinstance(raw, list):
                continue

            df = pd.DataFrame(raw, columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"
            ])
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            return df
        except Exception:
            continue
    return None


def check_btc_health():
    """
    Analyzes Bitcoin (BTCUSDT) 4H trend & momentum to assess broad market safety.
    Returns: (status_label, is_crash, warning_text)
    """
    df_btc = fetch_klines("BTCUSDT", "4h", limit=60)
    if df_btc is None or len(df_btc) < 30:
        return "🟢 مستقر (بيانات عامة)", False, ""

    btc_close = df_btc['close'].iloc[-1]
    btc_open = df_btc['open'].iloc[-1]
    btc_ema50 = calculate_ema(df_btc['close'], 50).iloc[-1]
    btc_rsi = calculate_rsi(df_btc['close'], 14).iloc[-1]

    candle_chg = ((btc_close - btc_open) / btc_open) * 100

    # 1. Real Flash Dump / Crash (> 4.0% drop in single 4H candle)
    # هبوط عنيف وحقيقي لا يقل عن 4% في شمعة واحدة يستدعي إيقاف الصفقات فوراً
    if candle_chg <= -4.0:
        return (
            f"🔴 انهيار حاد ({candle_chg:.1f}%) ⚠️",
            True,
            f"⚠️ *تحذير انهيار عاجل:* البيتكوين يهبط بقوة غير معتادة ({candle_chg:.1f}%)! تم إيقاف الدخول لحماية المحفظة حتى يتوقف النزيف."
        )

    # 2. Normal Pullback / Correction (-2.0% to -3.9%)
    # تصحيح طبيعي معتاد في الكريبتو: يستمر البوت في إرسال الصفقات عادي جداً مع تنبيه خفيف
    if -3.9 <= candle_chg <= -2.0 or (btc_close < btc_ema50 and candle_chg < -1.5):
        return (
            f"🟡 تصحيح طبيعي ({candle_chg:.1f}%)",
            False,
            "💡 *ملاحظة:* البيتكوين في حركة تصحيحية هادئة، الصفقات تعمل بشكل طبيعي."
        )

    # 3. Healthy / Bullish / Sideways Market
    return (
        f"🟢 مستقر وصاعد ({candle_chg:+.1f}%)",
        False,
        ""
    )


def scan_pair_timeframe(item):
    """Scans a single pair on a single timeframe."""
    raw_name, symbol, tf = item
    df = fetch_klines(symbol, tf, limit=100)
    if df is None or len(df) < 55:
        return []

    current_close = df['close'].iloc[-1]
    current_open = df['open'].iloc[-1]

    # 🛑 فلتر منع مطاردة القمم (Anti-FOMO Filter):
    # 1. استبعاد العملة إذا كانت الشمعة الحالية صعدت بالفعل بأكثر من 5% (انفجرت خلاص)
    candle_gain = (current_close - current_open) / current_open
    if candle_gain > 0.05:
        return []

    # 2. استبعاد أي عملة فيها تشبع شرائي مبالغ فيه (RSI > 68)
    from strategies import calculate_rsi
    rsi_now = calculate_rsi(df['close'], 14).iloc[-1]
    if rsi_now > 68:
        return []

    # 🛡️ 3. درع حماية الاتجاه والسيولة (Trend & Volume Shield) لمنع السكاكين الهابطة:
    # حظر شراء أي عملة تتداول في مسار هابط تحت EMA 20 و EMA 50 إلا إذا كان هناك انفجار فوليوم حيتان استثنائي (>= 2.5x)
    ema20_now = calculate_ema(df['close'], 20).iloc[-1]
    ema50_now = calculate_ema(df['close'], 50).iloc[-1]
    vol_sma20 = df['volume'].rolling(20).mean().iloc[-1]

    is_downtrend_trap = (current_close < ema50_now) and (ema20_now < ema50_now)
    has_whale_explosion = (df['volume'].iloc[-1] >= 2.5 * vol_sma20)

    if is_downtrend_trap and not has_whale_explosion:
        return []  # حجب فوري للعملات الهابطة

    # منع شراء العملة إذا كانت تسجل قيعاناً جديدة تكسر دعم الـ 10 شمعات السابقة
    recent_min_low = df['low'].iloc[-10:-1].min()
    if df['low'].iloc[-1] < recent_min_low * 0.998 and current_close < ema20_now:
        return []  # استبعاد العملات التي تكسر القيعان

    signals = evaluate_strategies(df)
    if not signals:
        return []

    atr = calculate_atr(df, 14).iloc[-1]
    if np.isnan(atr) or atr <= 0:
        atr = current_close * 0.03  # default fallback 3%

    # حساب مستوى الدعم الفني الحقيقي ووضع وقف الخسارة أسفله (Real Technical Support Level)
    support_level = find_structural_support(df, current_close, lookback=25)
    
    # يوضع وقف الخسارة أسفل الدعم مباشرة مع هامش أمان بسيط لمنع ضرب الذيول الوهمية
    stop_loss = support_level * 0.996
    
    risk = current_close - stop_loss
    sl_pct = ((current_close - stop_loss) / current_close) * 100
    
    # إذا كان الدعم بعيداً جداً (أكثر من 7.5%)، تصبح الصفقة غير مجدية للسبوت فيتم استبعادها
    if sl_pct > 7.5 or sl_pct < 0.6:
        return []

    tp1 = current_close + (1.5 * risk)  # R:R 1:1.5
    tp2 = current_close + (2.5 * risk)  # R:R 1:2.5

    tp1_pct = ((tp1 - current_close) / current_close) * 100
    tp2_pct = ((tp2 - current_close) / current_close) * 100

    results = []
    for sig in signals:
        results.append({
            "raw_name": raw_name,
            "symbol": symbol,
            "timeframe": tf,
            "strategy": sig["strategy"],
            "reason": sig["reason"],
            "strength": sig["strength"],
            "entry_price": current_close,
            "support_level": support_level,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "sl_pct": sl_pct,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct
        })
    return results


def get_cairo_time_str():
    from datetime import datetime, timedelta
    cairo_dt = datetime.utcnow() + timedelta(hours=3)
    period = "م" if cairo_dt.hour >= 12 else "ص"
    hour_12 = cairo_dt.hour - 12 if cairo_dt.hour > 12 else (12 if cairo_dt.hour == 0 else cairo_dt.hour)
    return f"{hour_12}:{cairo_dt.strftime('%M')} {period} (بتوقيت مصر)"


def run_full_scan(bot_token="", chat_id="", notify=False):
    print("=" * 70, flush=True)
    print("🚀 بدء فحص العملات الرقمية للسبوت (Binance Spot 12 Strategies Scanner)", flush=True)
    print(f"⏰ الفريمات: {', '.join(TIMEFRAMES)} | عدد العملات في القائمة: {len(COINS_RAW)}", flush=True)
    print("=" * 70, flush=True)

    print("[1/3] فحص صحة واتجاه البيتكوين (BTC Health Check)...", flush=True)
    btc_status, btc_is_crash, btc_warning = check_btc_health()
    print(f"  -> حالة البيتكوين: {btc_status}", flush=True)
    if btc_warning:
        print(f"  -> {btc_warning}", flush=True)

    if btc_is_crash and notify and bot_token and chat_id:
        crash_msg = f"""🚨 *تحذير سوق طارئ (Bitcoin Crash Alert)* ⚠️

🌐 *حالة البيتكوين:* {btc_status}
━━━━━━━━━━━━━━━━━━━━
{btc_warning}

🛑 *إجراء الحماية التلقائي:* تم تعليق إرسال إشارات الشراء للعملات البديلة مؤقتاً لحماية محفظتك حتى يتوقف النزيف ويستقر السوق!
━━━━━━━━━━━━━━━━━━━━"""
        send_telegram_alert(bot_token, chat_id, crash_msg)
        return []

    tasks = []
    for raw in COINS_RAW:
        c_clean = raw.strip().upper()
        mapped = SYMBOL_ALIASES.get(c_clean, c_clean)
        pair = f"{mapped}USDT"
        for tf in TIMEFRAMES:
            tasks.append((c_clean, pair, tf))

    print(f"🔍 فحص {len(tasks)} مهمة تحليل عبر الـ 12 استراتيجية بالتوازي...", flush=True)
    start_time = time.time()
    all_signals = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        for res in executor.map(scan_pair_timeframe, tasks):
            if res:
                all_signals.extend(res)

    elapsed = time.time() - start_time
    print(f"✅ اكتمل الفحص في {elapsed:.1f} ثانية! إجمالي الإشارات المرصودة: {len(all_signals)}", flush=True)
    print("=" * 70, flush=True)

    for s in all_signals:
        s['btc_status'] = btc_status
        s['btc_warning'] = btc_warning

    if not all_signals:
        print("ℹ️ لا توجد إشارات دخول متطابقة مع الشروط الصارمة في هذه اللحظة.", flush=True)
        if notify and bot_token and chat_id:
            from datetime import datetime
            time_now = datetime.utcnow().strftime("%H:%M UTC")
            no_trades_msg = f"""🔍 *فحص دوري للسوق (160 عملة)* 📊
⏰ *الوقت:* `{time_now}`
━━━━━━━━━━━━━━━━━━━━
ℹ️ *لا توجد صفقات بتوافق استراتيجيتين أو أكثر في هذه الجلسة (إغلاق 4 ساعات).*
🛡️ _تم استبعاد الإشارات الفردية لضمان أعلى نسبة نجاح وحماية المحفظة._
⏳ الصفقات السابقة المفتوحة ما زالت قيد المتابعة.
━━━━━━━━━━━━━━━━━━━━"""
            send_telegram_alert(bot_token, chat_id, no_trades_msg)
        return []

    # Display results
    print("\n🔥 جدول أهم الفرص المرصودة حالياً:")
    print(f"{'العملة':<12} {'الفريم':<6} {'الاستراتيجية':<32} {'السعر':<12} {'الوقف':<8} {'الهدف 1':<8}")
    print("-" * 85)
    for s in all_signals:
        ep_str = format_price(s['entry_price'])
        print(f"{s['symbol']:<12} {s['timeframe'].upper():<6} {s['strategy'][:30]:<32} {ep_str:<12} -{s['sl_pct']:<7.1f}% +{s['tp1_pct']:<7.1f}%")

    # Send alerts if requested
    if notify and bot_token and chat_id:
        print("\n📲 إرسال التنبيهات إلى تيليجرام...", flush=True)
        # Update live prices and load active trades to prevent repeating identical signals
        from trade_tracker import update_all_trades, load_trades
        from datetime import datetime, timedelta

        update_all_trades()
        trades_data = load_trades()
        active_pairs = {(t['symbol'], t['timeframe']) for t in trades_data.get('active', [])}
        
        # تخطي الصفقات المفتوحة والجارية حالياً فقط (لمنع التكرار المزعج وأنت داخل الصفقة)
        # وبمجرد إغلاق الصفقة تصبح العملة متاحة فوراً لأي إشارة جديدة (صفر فرص ضائعة)
        from collections import defaultdict
        coin_groups = defaultdict(list)
        for s in all_signals:
            pair_key = (s['symbol'], s['timeframe'])
            if pair_key in active_pairs:
                continue
            coin_groups[pair_key].append(s)

        # الفلتر الاحترافي الصارم: اشتراط تطابق استراتيجيتين أو أكثر معاً (Confluence >= 2)
        # أو رصد شمعة تجميع حيتان استباقية مؤكدة (Whale Accumulation Pre-Pump)
        confluent_keys = [
            k for k in coin_groups.keys()
            if len(coin_groups[k]) >= 2 or any(x['strategy'] == "Whale Accumulation Pre-Pump" for x in coin_groups[k])
        ]

        def sort_priority(k):
            has_whale = any(x['strategy'] == "Whale Accumulation Pre-Pump" for x in coin_groups[k])
            return (1 if has_whale else 0, len(coin_groups[k]))

        sorted_keys = sorted(confluent_keys, key=sort_priority, reverse=True)

        sent_count = 0
        for sym, tf in sorted_keys:
            sigs = coin_groups[(sym, tf)]
            primary = sigs[0].copy()
            has_whale = any(x['strategy'] == "Whale Accumulation Pre-Pump" for x in sigs)
            combined_names = " + ".join([x['strategy'] for x in sigs])
            if has_whale:
                primary['strategy'] = f"🐋⚡ إشارة حيتان استباقية (Grade S+ VIP): {combined_names}"
            else:
                primary['strategy'] = f"⭐ تطابق {len(sigs)} استراتيجيات: {combined_names}"

            # التنفيذ الفعلي التلقائي على حساب Binance Spot Testnet (إذا كان مفعلاً)
            if ENABLE_TESTNET_TRADING:
                try:
                    from testnet_trader import execute_testnet_buy
                    print(f"  [Testnet] 🧪 جاري تنفيذ شراء تلقائي لـ {sym} بقيمة ${TESTNET_TRADE_AMOUNT_USDT} على باينانس التجريبي...", flush=True)
                    t_res = execute_testnet_buy(sym, TESTNET_TRADE_AMOUNT_USDT)
                    if t_res.get("success"):
                        primary["testnet_order_id"] = t_res["order_id"]
                        primary["testnet_qty"] = t_res["qty"]
                        primary["testnet_cost"] = t_res["cost"]
                        primary["testnet_avg_price"] = t_res["avg_price"]
                        print(f"  [Testnet] ✅ تم تنفيذ الشراء بنجاح! كمية: {t_res['qty']} | أمر رقم #{t_res['order_id']}", flush=True)
                    else:
                        print(f"  [Testnet] ⚠️ تعذر التنفيذ على باينانس التجريبي: {t_res.get('error')}", flush=True)
                except Exception as t_err:
                    print(f"  [Testnet Error]: {t_err}", flush=True)

            try:
                msg = format_signal_message(primary)
                if send_telegram_alert(bot_token, chat_id, msg):
                    sent_count += 1
                    record_new_trade(primary)  # Save trade for tracking
                    time.sleep(0.35)  # Respect Telegram rate limit
            except Exception as e:
                print(f"[Alert Error] {sym}: {e}", flush=True)

        if sent_count > 0:
            print(f"  -> تم إرسال {sent_count} صفقات ذهبية بتوافق استراتيجيتين فأكثر إلى هاتفك!", flush=True)
        else:
            print("  -> لا توجد صفقات بتوافق استراتيجيتين فأكثر في هذه الساعة...", flush=True)
            from datetime import datetime
            time_now = datetime.utcnow().strftime("%H:%M UTC")
            no_trades_msg = f"""🔍 *فحص دوري للسوق (160 عملة)* 📊
⏰ *الوقت:* `{time_now}`
━━━━━━━━━━━━━━━━━━━━
ℹ️ *لا توجد صفقات بتوافق استراتيجيتين أو أكثر في هذه الجلسة (إغلاق 4 ساعات).*
🛡️ _تم استبعاد الإشارات الفردية لضمان أعلى نسبة نجاح وحماية المحفظة._
⏳ الصفقات السابقة المفتوحة ما زالت قيد المتابعة.
━━━━━━━━━━━━━━━━━━━━"""
            send_telegram_alert(bot_token, chat_id, no_trades_msg)

    return all_signals


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run scan once and exit")
    parser.add_argument("--notify", action="store_true", help="Send Telegram notifications")
    parser.add_argument("--loop", action="store_true", help="Run in continuous loop")
    parser.add_argument("--report", action="store_true", help="Send daily performance report")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds (default 300s = 5m)")
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    chat = os.environ.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)

    if args.report:
        print("📊 جاري إرسال تقرير الصفقات اليومي إلى تيليجرام...", flush=True)
        send_daily_report_to_telegram(token=token, chat_id=chat)
        print("  -> تم إرسال تقرير الحصاد اليومي بنجاح!", flush=True)
        sys.exit(0)

    if args.loop:
        print(f"🔁 تشغيل وضع المراقبة المستمرة (تحديث كل {args.interval} ثانية)...", flush=True)
        while True:
            try:
                run_full_scan(bot_token=token, chat_id=chat, notify=args.notify)
            except Exception as e:
                print(f"[Error] {e}", flush=True)
            time.sleep(args.interval)
    else:
        run_full_scan(bot_token=token, chat_id=chat, notify=args.notify)
