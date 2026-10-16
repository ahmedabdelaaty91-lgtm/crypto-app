# telegram_notifier.py
"""
Telegram Notification Module for Crypto Spot Scanner
Formats and sends signal alerts with entry, stop loss, take profit targets, and charts.
"""

import requests


def send_telegram_alert(token: str, chat_id: str, message: str, retries: int = 3) -> bool:
    """Sends a formatted message to a Telegram chat or channel with auto-retry."""
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    for attempt in range(retries):
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return True
        except Exception as e:
            if attempt == retries - 1:
                print(f"[Telegram Error] Failed to send message after {retries} attempts: {e}", flush=True)
            import time
            time.sleep(1.5)
    return False


def format_price(val: float) -> str:
    """Intelligently formats prices so micro-penny coins (like 1000SATS, PEPE, SHIB) don't display $0.0000."""
    if val is None or val == 0:
        return "0.00"
    abs_v = abs(val)
    if abs_v >= 1000:
        return f"{val:,.2f}"
    elif abs_v >= 1:
        return f"{val:,.4f}"
    elif abs_v >= 0.01:
        return f"{val:,.5f}"
    elif abs_v >= 0.0001:
        return f"{val:,.6f}"
    else:
        # Micro coins with 8 decimal places (e.g. 1000SATS: 0.00001143)
        res = f"{val:.8f}".rstrip('0')
        return res if not res.endswith('.') else res + '0'


def format_signal_message(signal_data: dict) -> str:
    """
    Formats the trading signal into an Arabic/English markdown message.
    """
    symbol = signal_data['symbol']
    base = symbol.replace("USDT", "")
    tf = signal_data['timeframe']
    strategy = signal_data['strategy']
    reason = signal_data['reason']
    price = signal_data['entry_price']
    support = signal_data.get('support_level', price * 0.97)
    sl = signal_data.get('stop_loss', price * 0.97)
    tp1 = signal_data.get('tp1', price * 1.05)
    tp2 = signal_data.get('tp2', price * 1.10)
    sl_pct = signal_data.get('sl_pct', 3.0)
    tp1_pct = signal_data.get('tp1_pct', 5.0)
    tp2_pct = signal_data.get('tp2_pct', 10.0)

    btc_status = signal_data.get('btc_status', '🟢 مستقر')
    btc_warning = signal_data.get('btc_warning', '')
    warning_block = f"\n{btc_warning}\n" if btc_warning else ""

    p_str = format_price(price)
    sup_str = format_price(support)
    sl_str = format_price(sl)
    tp1_str = format_price(tp1)
    tp2_str = format_price(tp2)
    msg = f"""🚨 *إشارة دخول Spot جديدة!* 🚀

🪙 *العملة:* `#{base}/USDT`
⏰ *الفريم:* `{tf.upper()}`
🎯 *الاستراتيجية:* *{strategy}*
📌 *السبب:* {reason}
🌐 *سوق البيتكوين:* {btc_status}{warning_block}
━━━━━━━━━━━━━━━━━━━━
💵 *سعر الدخول:* `${p_str}`
🛡️ *مستوى الدعم الفني:* `${sup_str}`
🛑 *وقف الخسارة (أسفل الدعم):* `${sl_str}` (-{sl_pct:.2f}%)
🎯 *الهدف الأول (TP1):* `${tp1_str}` (+{tp1_pct:.2f}%)
🎯 *الهدف الثاني (TP2):* `${tp2_str}` (+{tp2_pct:.2f}%)
━━━━━━━━━━━━━━━━━━━━"""

    if signal_data.get("testnet_order_id"):
        t_qty = signal_data.get("testnet_qty", 0.0)
        t_id = signal_data.get("testnet_order_id")
        t_cost = signal_data.get("testnet_cost", 10.0)
        msg += f"""
🧪 *تنفيذ تلقائي على باينانس التجريبي (Testnet):*
✅ تم شراء `{t_qty} {base}` بقيمة `${t_cost:.2f} USDT`
🆔 رقم الأمر: `#{t_id}`
━━━━━━━━━━━━━━━━━━━━"""

    msg += f"""
📊 [عرض الشارت على Binance](https://www.binance.com/en/trade/{base}_USDT?type=spot)
📈 [عرض الشارت على TradingView](https://www.tradingview.com/chart/?symbol=BINANCE:{base}USDT)
"""
    return msg

