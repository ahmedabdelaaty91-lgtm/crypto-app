import os
import time
import hmac
import hashlib
import requests
import math
from config import (
    BINANCE_TESTNET_API_KEY,
    BINANCE_TESTNET_SECRET_KEY,
    BINANCE_TESTNET_URL,
    ENABLE_TESTNET_TRADING,
    TESTNET_TRADE_AMOUNT_USDT
)

_symbol_filters_cache = {}
_time_offset = None
_last_offset_fetch = 0

def get_synced_timestamp() -> int:
    """Calculates Binance server time using synchronized offset to prevent recvWindow errors."""
    global _time_offset, _last_offset_fetch
    now = time.time()
    if _time_offset is None or (now - _last_offset_fetch > 300):
        try:
            res = requests.get(f"{BINANCE_TESTNET_URL}/api/v3/time", timeout=5)
            if res.status_code == 200:
                srv_time = res.json().get("serverTime")
                local_time = int(now * 1000)
                _time_offset = srv_time - local_time
                _last_offset_fetch = now
        except Exception:
            if _time_offset is None:
                _time_offset = 0
    return int(time.time() * 1000) + _time_offset

def get_symbol_filters(symbol: str) -> dict:
    """Fetches and caches LOT_SIZE stepSize and minQty for a symbol."""
    global _symbol_filters_cache
    if symbol in _symbol_filters_cache:
        return _symbol_filters_cache[symbol]
        
    try:
        url = f"{BINANCE_TESTNET_URL}/api/v3/exchangeInfo?symbol={symbol}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            symbols = data.get("symbols", [])
            if symbols:
                filters = {f["filterType"]: f for f in symbols[0].get("filters", [])}
                lot = filters.get("LOT_SIZE", {})
                step_size = float(lot.get("stepSize", "1.0"))
                min_qty = float(lot.get("minQty", "1.0"))
                info = {
                    "step_size": step_size,
                    "min_qty": min_qty,
                    "base_asset": symbols[0].get("baseAsset"),
                    "quote_asset": symbols[0].get("quoteAsset")
                }
                _symbol_filters_cache[symbol] = info
                return info
    except Exception as e:
        print(f"[Testnet Error] Failed to get exchange info for {symbol}: {e}")
        
    return {"step_size": 0.01, "min_qty": 0.01, "base_asset": "", "quote_asset": "USDT"}

def round_step_size(quantity: float, step_size: float) -> float:
    """Rounds down a quantity to the allowed stepSize."""
    if step_size <= 0:
        return quantity
    precision = int(round(-math.log10(step_size))) if step_size < 1 else 0
    factor = 1.0 / step_size
    rounded = math.floor(quantity * factor) / factor
    if precision > 0:
        return float(f"{rounded:.{precision}f}")
    return float(int(rounded))

def _sign_query(params: dict, secret: str) -> str:
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{query}&signature={sig}"

def get_testnet_balance(asset: str = "USDT") -> float:
    """Returns available free balance of given asset on Testnet."""
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        return 0.0
    try:
        params = {
            "recvWindow": 60000,
            "timestamp": get_synced_timestamp()
        }
        signed_query = _sign_query(params, BINANCE_TESTNET_SECRET_KEY)
        headers = {"X-MBX-APIKEY": BINANCE_TESTNET_API_KEY}
        url = f"{BINANCE_TESTNET_URL}/api/v3/account?{signed_query}"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            for b in res.json().get("balances", []):
                if b["asset"] == asset:
                    return float(b["free"])
        else:
            print(f"[Testnet Error] Account fetch failed: {res.status_code} {res.text}")
    except Exception as e:
        print(f"[Testnet Error] Balance fetch failed: {e}")
    return 0.0

def execute_testnet_buy(symbol: str, quote_amount_usdt: float = 10.0) -> dict:
    """
    Executes a MARKET BUY order on Binance Spot Testnet with quoteOrderQty (USDT amount).
    Returns dict: {'success': bool, 'order_id': int, 'qty': float, 'avg_price': float, 'cost': float, 'error': str}
    """
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        return {"success": False, "error": "No API Keys configured"}

    try:
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": round(float(quote_amount_usdt), 2),
            "recvWindow": 60000,
            "timestamp": get_synced_timestamp()
        }
        signed_query = _sign_query(params, BINANCE_TESTNET_SECRET_KEY)
        headers = {"X-MBX-APIKEY": BINANCE_TESTNET_API_KEY}
        url = f"{BINANCE_TESTNET_URL}/api/v3/order?{signed_query}"
        
        res = requests.post(url, headers=headers, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("status") in ["FILLED", "PARTIALLY_FILLED"]:
            executed_qty = float(data.get("executedQty", 0.0))
            cum_quote = float(data.get("cummulativeQuoteQty", quote_amount_usdt))
            avg_price = cum_quote / executed_qty if executed_qty > 0 else 0.0
            return {
                "success": True,
                "order_id": data.get("orderId"),
                "symbol": symbol,
                "qty": executed_qty,
                "avg_price": avg_price,
                "cost": cum_quote,
                "raw": data
            }
        else:
            err_msg = data.get("msg", str(data))
            return {"success": False, "error": f"{res.status_code}: {err_msg}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def execute_testnet_sell(symbol: str, quantity: float) -> dict:
    """
    Executes a MARKET SELL order on Binance Spot Testnet for given quantity.
    Returns dict: {'success': bool, 'order_id': int, 'qty': float, 'avg_price': float, 'return_usdt': float, 'error': str}
    """
    if not BINANCE_TESTNET_API_KEY or not BINANCE_TESTNET_SECRET_KEY:
        return {"success": False, "error": "No API Keys configured"}

    try:
        filters = get_symbol_filters(symbol)
        step_size = filters.get("step_size", 0.01)
        valid_qty = round_step_size(quantity, step_size)
        
        if valid_qty <= 0:
            return {"success": False, "error": f"Quantity {quantity} rounded to 0 with step {step_size}"}

        prec = int(round(-math.log10(step_size))) if step_size < 1 else 0
        qty_str = f"{valid_qty:.{prec}f}" if prec > 0 else str(int(valid_qty))

        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": qty_str,
            "recvWindow": 60000,
            "timestamp": get_synced_timestamp()
        }
        signed_query = _sign_query(params, BINANCE_TESTNET_SECRET_KEY)
        headers = {"X-MBX-APIKEY": BINANCE_TESTNET_API_KEY}
        url = f"{BINANCE_TESTNET_URL}/api/v3/order?{signed_query}"
        
        res = requests.post(url, headers=headers, timeout=10)
        data = res.json()
        if res.status_code == 200 and data.get("status") in ["FILLED", "PARTIALLY_FILLED"]:
            executed_qty = float(data.get("executedQty", valid_qty))
            cum_quote = float(data.get("cummulativeQuoteQty", 0.0))
            avg_price = cum_quote / executed_qty if executed_qty > 0 else 0.0
            return {
                "success": True,
                "order_id": data.get("orderId"),
                "symbol": symbol,
                "qty": executed_qty,
                "avg_price": avg_price,
                "return_usdt": cum_quote,
                "raw": data
            }
        else:
            err_msg = data.get("msg", str(data))
            return {"success": False, "error": f"{res.status_code}: {err_msg}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
