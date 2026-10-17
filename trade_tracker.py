# trade_tracker.py
"""
Trade Tracker & Daily Performance Reporter
Tracks all spot signals, monitors whether they hit TP1, TP2, or SL,
and generates daily performance reports sent directly to Telegram.
"""

from datetime import datetime
import json
import os
import requests
from config import BINANCE_API_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from telegram_notifier import send_telegram_alert, format_price

DATA_FILE = os.path.join(os.path.dirname(__file__), "trades_data.json")
PWA_DATA_FILE = os.path.join(os.path.dirname(__file__), "pwa", "trades_data.json")


def load_trades():
    if not os.path.exists(DATA_FILE):
        return {"active": [], "closed": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active": [], "closed": []}


def save_trades(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    pwa_dir = os.path.dirname(PWA_DATA_FILE)
    if os.path.exists(pwa_dir):
        try:
            with open(PWA_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def record_new_trade(signal_data: dict):
    """Saves a new active trade when an alert is fired."""
    data = load_trades()
    symbol = signal_data['symbol']
    tf = signal_data['timeframe']
    
    # Check if symbol is already actively tracked on this timeframe
    for t in data["active"]:
        if t["symbol"] == symbol and t["timeframe"] == tf:
            return  # Already tracking
            
    trade = {
        "id": f"{symbol}_{tf}_{int(datetime.utcnow().timestamp())}",
        "symbol": symbol,
        "base": symbol.replace("USDT", ""),
        "timeframe": tf,
        "strategy": signal_data.get("strategy", ""),
        "entry_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "entry_price": float(signal_data["entry_price"]),
        "support_level": float(signal_data.get("support_level", signal_data["entry_price"] * 0.97)),
        "stop_loss": float(signal_data["stop_loss"]),
        "tp1": float(signal_data["tp1"]),
        "tp2": float(signal_data["tp2"]),
        "sl_pct": float(signal_data.get("sl_pct", 3.0)),
        "tp1_pct": float(signal_data.get("tp1_pct", 5.0)),
        "tp2_pct": float(signal_data.get("tp2_pct", 10.0)),
        "status": "ACTIVE",  # ACTIVE, HIT_TP1, HIT_TP2, STOPPED_OUT
        "highest_price": float(signal_data["entry_price"]),
        "lowest_price": float(signal_data["entry_price"]),
        "current_price": float(signal_data["entry_price"]),
        "pnl_pct": 0.0,
        "closed_date": None,
        "result_reason": None,
        "testnet_order_id": signal_data.get("testnet_order_id"),
        "testnet_qty": signal_data.get("testnet_qty", 0.0),
        "testnet_cost": signal_data.get("testnet_cost", 0.0),
        "testnet_avg_price": signal_data.get("testnet_avg_price", 0.0),
        "testnet_sell_order_id": None,
        "testnet_realized_usdt": None
    }
    data["active"].append(trade)
    save_trades(data)


def update_all_trades():
    """Fetches current live ticker prices from Binance and evaluates active trades."""
    data = load_trades()
    if not data["active"]:
        return data

    try:
        resp = requests.get(f"{BINANCE_API_URL}/ticker/price", timeout=10)
        if resp.status_code != 200:
            return data
        all_tickers = {item["symbol"]: float(item["price"]) for item in resp.json()}
    except Exception as e:
        print(f"[Tracker Error] Could not fetch tickers: {e}")
        return data

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    still_active = []
    
    for t in data["active"]:
        sym = t["symbol"]
        if sym not in all_tickers:
            still_active.append(t)
            continue
            
        cur_price = all_tickers[sym]
        t["current_price"] = cur_price
        if cur_price > t["highest_price"]:
            t["highest_price"] = cur_price
        if cur_price < t["lowest_price"]:
            t["lowest_price"] = cur_price
            
        t["pnl_pct"] = ((cur_price - t["entry_price"]) / t["entry_price"]) * 100
        
        # Check Exit Conditions
        is_closing = False
        if cur_price >= t["tp2"]:
            t["status"] = "HIT_TP2"
            t["closed_date"] = now_str
            t["result_reason"] = f"حقق الهدف الثاني بالكامل (+{t['tp2_pct']:.1f}%) 🚀🎯"
            is_closing = True
        elif cur_price <= t["stop_loss"]:
            t["status"] = "STOPPED_OUT"
            t["closed_date"] = now_str
            t["result_reason"] = f"ضرب وقف الخسارة (-{t['sl_pct']:.1f}%) 🛑"
            is_closing = True
        elif cur_price >= t["tp1"]:
            # Hits TP1: Alert once, move SL to breakeven, keep aiming for TP2
            if not t.get("tp1_alerted", False):
                t["tp1_alerted"] = True
                t["stop_loss"] = float(t["entry_price"])  # Breakeven stop
                t["result_reason"] = f"حقق الهدف الأول (+{t['tp1_pct']:.1f}%) ✅"
                tp1_msg = f"""🎯 *تحديث صفقة: تم تحقيق الهدف الأول (TP1) بنجاح!* 🚀

🪙 *العملة:* `#{t['base']}/USDT`
⏰ *الفريم:* `{t.get('timeframe', '4H').upper()}`
💵 *سعر الدخول:* `${format_price(t['entry_price'])}`
🎯 *سعر الهدف الأول:* `${format_price(t['tp1'])}`
📈 *السعر الحالي:* `${format_price(cur_price)}` (+{t['tp1_pct']:.2f}%)
━━━━━━━━━━━━━━━━━━━━
🛡️ *إدارة الأمان:* تم تأمين الصفقة ورفع الوقف إلى سعر الدخول لحجز الأرباح وتصفير المخاطرة!
⏳ *الهدف القادم (TP2):* `${format_price(t['tp2'])}` (+{t['tp2_pct']:.2f}%)
━━━━━━━━━━━━━━━━━━━━"""
                send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, tp1_msg)
            still_active.append(t)
        else:
            still_active.append(t)

        if is_closing:
            data["closed"].append(t)
            testnet_sell_id = None
            ret_usdt = 0.0
            pnl_dollars = 0.0

            # 1. Execute on Testnet if trade had testnet order
            if t.get("testnet_order_id") and t.get("testnet_qty", 0) > 0:
                try:
                    from testnet_trader import execute_testnet_sell
                    print(f"  [Testnet Sell] 🧪 إغلاق صفقة {sym} تلقائياً على باينانس التجريبي...", flush=True)
                    s_res = execute_testnet_sell(sym, t["testnet_qty"])
                    if s_res.get("success"):
                        ret_usdt = s_res.get("return_usdt", 0.0)
                        cost = t.get("testnet_cost", 10.0)
                        pnl_dollars = ret_usdt - cost
                        testnet_sell_id = s_res.get("order_id")
                        t["testnet_sell_order_id"] = testnet_sell_id
                        t["testnet_realized_usdt"] = pnl_dollars
                except Exception as ex:
                    print(f"  [Testnet Sell Error]: {ex}", flush=True)

            # Fallback calculation if not on testnet
            if pnl_dollars == 0.0:
                cost = float(t.get("testnet_cost") or 10.0)
                if t["status"] == "HIT_TP2":
                    pnl_dollars = cost * (t["tp2_pct"] / 100.0)
                else:
                    pnl_dollars = - (cost * (t["sl_pct"] / 100.0))

            # 2. Send instant Telegram Notification for TP2 or SL
            if t["status"] == "HIT_TP2":
                tp2_msg = f"""🏆 *مبروك! تحقيق الهدف الثاني بالكامل وإغلاق الصفقة (TP2)!* 🚀🎯

🪙 *العملة:* `#{t['base']}/USDT`
⏰ *الفريم:* `{t.get('timeframe', '4H').upper()}`
💵 *سعر الدخول:* `${format_price(t['entry_price'])}`
🎯 *سعر الإغلاق:* `${format_price(cur_price)}`
💰 *إجمالي الربح المحقق:* `+{t['tp2_pct']:.2f}%` (+{abs(pnl_dollars):.2f} USDT)
━━━━━━━━━━━━━━━━━━━━
✅ تم إغلاق الصفقة بنجاح وحصد كامل الأرباح!
{f'🆔 رقم أمر البيع على Binance Testnet: `#{testnet_sell_id}`' if testnet_sell_id else '🧪 تم إضافة الأرباح إلى المحفظة الافتراضية.'}
━━━━━━━━━━━━━━━━━━━━"""
                send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, tp2_msg)

            elif t["status"] == "STOPPED_OUT":
                sl_msg = f"""🛑 *تنبيه خروج: تم ضرب وقف الخسارة (Stop Loss)*

🪙 *العملة:* `#{t['base']}/USDT`
⏰ *الفريم:* `{t.get('timeframe', '4H').upper()}`
💵 *سعر الدخول:* `${format_price(t['entry_price'])}`
🛑 *سعر الخروج:* `${format_price(cur_price)}`
📉 *نسبة الخسارة:* `-{t['sl_pct']:.2f}%` (-{abs(pnl_dollars):.2f} USDT)
━━━━━━━━━━━━━━━━━━━━
🛡️ تم الإغلاق التلقائي لحماية رأس المال من النزيف وتصفية المركز.
{f'🆔 رقم أمر الإغلاق على Binance Testnet: `#{testnet_sell_id}`' if testnet_sell_id else '🧪 تم تسجيل الخسارة وتحديث رصيد المحفظة الافتراضية.'}
━━━━━━━━━━━━━━━━━━━━"""
                send_telegram_alert(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, sl_msg)

    data["active"] = still_active
    save_trades(data)
    return data


def generate_daily_report():
    """Generates an Arabic daily summary report for Telegram."""
    data = update_all_trades()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    active_trades = data["active"]
    closed_trades = data["closed"]
    
    # Filter closed trades for today / recent
    today_closed = [t for t in closed_trades if (t.get("closed_date") or "").startswith(today_str)]
    tp_hits = [t for t in closed_trades if "HIT" in t.get("status", "")]
    sl_hits = [t for t in closed_trades if t.get("status") == "STOPPED_OUT"]
    
    total_closed = len(tp_hits) + len(sl_hits)
    win_rate = (len(tp_hits) / total_closed * 100) if total_closed > 0 else 0.0

    lines = [
        f"📊 *تقرير الحصاد اليومي ومتابعة الصفقات* 📈",
        f"🗓 *التاريخ:* `{today_str}`",
        f"━━━━━━━━━━━━━━━━━━━━"
    ]

    # 1. Closed Trades Section
    if today_closed:
        lines.append("\n🏆 *صفقات تم إغلاقها اليوم:*")
        for t in today_closed:
            base = t['base']
            if "HIT" in t['status']:
                lines.append(f"• `#{base}`: {t['result_reason']}")
            else:
                lines.append(f"• `#{base}`: {t['result_reason']}")
    elif tp_hits or sl_hits:
        lines.append(f"\n🏆 *إجمالي الصفقات المنتهية مؤخراً:* {total_closed}")
        for t in closed_trades[-5:]:
            lines.append(f"• `#{t['base']}`: {t.get('result_reason', t['status'])}")
    else:
        lines.append("\nℹ️ *لا توجد صفقات أغلقت اليوم حتى الآن.*")

    # 2. Active Trades Section
    lines.append(f"\n⏳ *الصفقات المستمرة حالياً ({len(active_trades)} صفقة):*")
    if active_trades:
        for t in active_trades[:12]:  # show top 12 active
            base = t['base']
            pnl = t.get('pnl_pct', 0.0)
            sign = "+" if pnl >= 0 else ""
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            entry = t['entry_price']
            cur = t['current_price']
            e_str = format_price(entry)
            c_str = format_price(cur)
            lines.append(f"• `#{base}`: الدخول `${e_str}` | الحالي `${c_str}` ({pnl_emoji} {sign}{pnl:.2f}%)")
    else:
        lines.append("• لا توجد صفقات جارية حالياً.")

    # 3. Overall Statistics Section
    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📌 *الصفقات المفتوحة:* `{len(active_trades)}`")
    lines.append(f"✅ *الصفقات الرابحة:* `{len(tp_hits)}`")
    lines.append(f"❌ *صفقات ضربت الوقف:* `{len(sl_hits)}`")
    if total_closed > 0:
        lines.append(f"🎯 *نسبة النجاح (Win Rate):* `{win_rate:.1f}%`")
    lines.append("━━━━━━━━━━━━━━━━━━━━\n_يتم تحديث ومتابعة جميع الصفقات تلقائياً عبر Binance Spot._")

    return "\n".join(lines)


def send_daily_report_to_telegram(token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID):
    """Sends the formatted daily report to the user."""
    report = generate_daily_report()
    return send_telegram_alert(token, chat_id, report)


if __name__ == "__main__":
    print(generate_daily_report())
