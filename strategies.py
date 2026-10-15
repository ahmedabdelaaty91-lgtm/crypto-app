# strategies.py
"""
Spot Technical Analysis Engine for 12 Crypto Strategies
Includes:
1. Aroon Zero Bounce
2. Aroon Deep Dip Sniper
3. Supertrend + EMA 200
4. Stochastic RSI (Trend Pullback)
5. EMA 20 / EMA 50 Golden Cross
6. Bollinger + MACD
7. MFI Whale Accumulation
8. RSI Bullish Divergence
9. Ichimoku Kumo Breakout
10. Donchian Breakout + Volume
11. Whale Accumulation Pre-Pump
12. Ichimoku Tenkan / Kijun Bullish Cross (TK Cross)
"""

import numpy as np
import pandas as pd


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def calculate_stoch_rsi(series: pd.Series, rsi_period: int = 14, stoch_period: int = 14, k_period: int = 3, d_period: int = 3):
    rsi = calculate_rsi(series, rsi_period)
    rsi_low = rsi.rolling(window=stoch_period).min()
    rsi_high = rsi.rolling(window=stoch_period).max()
    stoch = (rsi - rsi_low) / (rsi_high - rsi_low + 1e-10) * 100
    fast_k = stoch.rolling(window=k_period).mean()
    fast_d = fast_k.rolling(window=d_period).mean()
    return fast_k, fast_d


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    atr = calculate_atr(df, period)
    hl2 = (df['high'] + df['low']) / 2.0
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    upper_band = basic_upper.copy()
    lower_band = basic_lower.copy()
    trend = pd.Series(1, index=df.index)  # 1 = Bullish (Green), -1 = Bearish (Red)

    for i in range(1, len(df)):
        # Upper band trailing
        if basic_upper.iloc[i] < upper_band.iloc[i-1] or df['close'].iloc[i-1] > upper_band.iloc[i-1]:
            upper_band.iloc[i] = basic_upper.iloc[i]
        else:
            upper_band.iloc[i] = upper_band.iloc[i-1]

        # Lower band trailing
        if basic_lower.iloc[i] > lower_band.iloc[i-1] or df['close'].iloc[i-1] < lower_band.iloc[i-1]:
            lower_band.iloc[i] = basic_lower.iloc[i]
        else:
            lower_band.iloc[i] = lower_band.iloc[i-1]

        # Direction change
        if df['close'].iloc[i] > upper_band.iloc[i-1]:
            trend.iloc[i] = 1
        elif df['close'].iloc[i] < lower_band.iloc[i-1]:
            trend.iloc[i] = -1
        else:
            trend.iloc[i] = trend.iloc[i-1]

    return trend, upper_band, lower_band


def calculate_aroon(df: pd.DataFrame, period: int = 25):
    rolling_high = df['high'].rolling(period + 1)
    rolling_low = df['low'].rolling(period + 1)

    aroon_up = rolling_high.apply(lambda x: float(np.argmax(x)) / period * 100, raw=True)
    aroon_down = rolling_low.apply(lambda x: float(np.argmin(x)) / period * 100, raw=True)
    aroon_osc = aroon_up - aroon_down
    return aroon_up, aroon_down, aroon_osc


def calculate_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tp = (df['high'] + df['low'] + df['close']) / 3.0
    raw_money_flow = tp * df['volume']
    pos_flow = raw_money_flow.where(tp > tp.shift(1), 0.0)
    neg_flow = raw_money_flow.where(tp < tp.shift(1), 0.0)

    pos_mf = pos_flow.rolling(window=period).sum()
    neg_mf = neg_flow.rolling(window=period).sum()
    mfr = pos_mf / (neg_mf + 1e-10)
    mfi = 100.0 - (100.0 / (1.0 + mfr))
    return mfi


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    bandwidth = (upper - lower) / (middle + 1e-10)
    return upper, middle, lower, bandwidth


def calculate_ichimoku(df: pd.DataFrame):
    tenkan = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2.0
    kijun = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2.0
    # Senkou Span A calculated 26 periods ago
    span_a = ((tenkan + kijun) / 2.0).shift(26)
    # Senkou Span B calculated 26 periods ago
    span_b = ((df['high'].rolling(52).max() + df['low'].rolling(52).min()) / 2.0).shift(26)
    return tenkan, kijun, span_a, span_b


def calculate_donchian(df: pd.DataFrame, period: int = 20):
    upper = df['high'].shift(1).rolling(window=period).max()
    lower = df['low'].shift(1).rolling(window=period).min()
    return upper, lower


def find_structural_support(df: pd.DataFrame, current_price: float, lookback: int = 30) -> float:
    """
    Calculates the true technical structural support level below current price.
    Finds swing/pivot lows and base consolidation bottoms.
    """
    if len(df) < lookback:
        lookback = len(df)
        
    recent = df.iloc[-lookback:]
    lows = recent['low'].values
    
    # 1. Detect Pivot Lows (local troughs where price bounced)
    pivot_lows = []
    for i in range(2, len(lows) - 1):
        if lows[i] <= lows[i-1] and lows[i] <= lows[i-2] and lows[i] <= lows[i+1]:
            if lows[i] < current_price:
                pivot_lows.append(lows[i])
                
    if pivot_lows:
        # Filter for valid support below current price with at least 0.4% clearance
        valid_supports = [p for p in pivot_lows if p <= current_price * 0.996]
        if valid_supports:
            # The most relevant structural support is the highest pivot low below price
            return float(max(valid_supports))
            
    # 2. Fallback: Lowest low of the entry base / recent 5-10 bars
    recent_min = float(recent['low'].iloc[-10:].min())
    if recent_min < current_price:
        return recent_min
        
    return float(current_price * 0.97)  # standard 3% technical default if no history


def check_rsi_divergence(df: pd.DataFrame, rsi: pd.Series, lookback: int = 20) -> bool:
    """Detects Bullish RSI divergence: Price lower low, RSI higher low"""
    if len(df) < lookback + 5:
        return False

    prices = df['close'].iloc[-lookback:].values
    rsis = rsi.iloc[-lookback:].values

    # Find swing lows in price
    price_lows = []
    for i in range(2, len(prices) - 2):
        if prices[i] <= prices[i-1] and prices[i] <= prices[i-2] and prices[i] <= prices[i+1] and prices[i] <= prices[i+2]:
            price_lows.append(i)

    if len(price_lows) < 2:
        return False

    # Check the last two price swing lows
    prev_idx, last_idx = price_lows[-2], price_lows[-1]
    price_prev, price_last = prices[prev_idx], prices[last_idx]
    rsi_prev, rsi_last = rsis[prev_idx], rsis[last_idx]

    # Lower low in price, higher low in RSI
    if price_last < price_prev and rsi_last > rsi_prev and rsi_last < 45:
        # Currently bouncing
        if prices[-1] > prices[last_idx]:
            return True
    return False


def evaluate_strategies(df: pd.DataFrame) -> list:
    """
    Evaluates all 10 spot trading strategies on the latest market candles.
    Returns a list of triggered strategies with details.
    """
    signals = []
    if len(df) < 60:
        return signals

    # Precalculate indicators
    close = df['close']
    current_close = close.iloc[-1]
    prev_close = close.iloc[-2]
    current_open = df['open'].iloc[-1]
    current_vol = df['volume'].iloc[-1]
    vol_sma20 = calculate_sma(df['volume'], 20).iloc[-1]

    ema20 = calculate_ema(close, 20)
    ema50 = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)

    rsi = calculate_rsi(close, 14)
    fast_k, fast_d = calculate_stoch_rsi(close)
    aroon_up, aroon_down, aroon_osc = calculate_aroon(df, 25)
    trend, st_upper, st_lower = calculate_supertrend(df, 10, 3.0)
    macd, macd_sig, macd_hist = calculate_macd(close)
    bb_upper, bb_mid, bb_lower, bb_bw = calculate_bollinger_bands(close)
    mfi = calculate_mfi(df, 14)
    tenkan, kijun, span_a, span_b = calculate_ichimoku(df)
    donchian_up, donchian_down = calculate_donchian(df, 20)

    # 1. Aroon Zero Bounce: Aroon Osc bounces from <= 0 to > 0, Price > EMA 50
    if (aroon_osc.iloc[-2] <= 0 and aroon_osc.iloc[-1] > 0) and (current_close > ema50.iloc[-1]):
        signals.append({
            "strategy": "Aroon Zero Bounce",
            "reason": f"Aroon Osc crossed above 0 ({aroon_osc.iloc[-1]:.1f}) with Price > EMA50",
            "strength": "High"
        })

    # 2. Aroon Deep Dip Sniper: Oversold bounce with structural hold and volume
    recent_min_osc = aroon_osc.iloc[-4:-1].min()
    dip_trend_ok = (current_close >= ema20.iloc[-1]) or (current_close >= ema50.iloc[-1])
    dip_vol_ok = current_vol >= 1.15 * vol_sma20
    if (recent_min_osc <= -85) and (current_close > current_open) and (current_close > prev_close) and dip_trend_ok and dip_vol_ok:
        signals.append({
            "strategy": "Aroon Deep Dip Sniper",
            "reason": f"Aroon Osc was deep oversold ({recent_min_osc:.1f}) + Confirmed volume bounce above EMA support",
            "strength": "High"
        })

    # 3. Supertrend + EMA 200: Supertrend is Bullish and Price > EMA 200
    st_bullish_now = trend.iloc[-1] == 1
    st_just_flipped = trend.iloc[-2] == -1 and st_bullish_now
    if st_bullish_now and (current_close > ema200.iloc[-1]):
        if st_just_flipped or (current_close <= st_lower.iloc[-1] * 1.03):
            signals.append({
                "strategy": "Supertrend + EMA 200",
                "reason": "Supertrend Bullish (Green) in safe uptrend above EMA 200",
                "strength": "High"
            })

    # 4. Stochastic RSI: Stoch RSI K crosses D in oversold zone ONLY in a healthy trend
    stoch_cross = (fast_k.iloc[-2] <= fast_d.iloc[-2] and fast_k.iloc[-1] > fast_d.iloc[-1])
    stoch_trend_safe = (current_close >= ema50.iloc[-1]) or (current_close >= ema20.iloc[-1] and ema20.iloc[-1] >= ema20.iloc[-2])
    if stoch_cross and (fast_k.iloc[-1] < 28 or fast_d.iloc[-1] < 28) and stoch_trend_safe:
        signals.append({
            "strategy": "Stochastic RSI Oversold Bounce",
            "reason": f"Stoch RSI K/D crossed upward in oversold zone (K:{fast_k.iloc[-1]:.1f}, D:{fast_d.iloc[-1]:.1f}) with Bullish Trend support",
            "strength": "Medium"
        })

    # 5. EMA 20 / EMA 50: Golden Cross
    ema_cross = (ema20.iloc[-2] <= ema50.iloc[-2] and ema20.iloc[-1] > ema50.iloc[-1])
    if ema_cross:
        signals.append({
            "strategy": "EMA 20 / EMA 50 Golden Cross",
            "reason": "EMA 20 crossed above EMA 50 (Fast Bullish Trend Ignition)",
            "strength": "High"
        })

    # 6. Bollinger + MACD: Squeeze & Expansion with MACD Bullish Cross
    macd_bullish = (macd_hist.iloc[-2] <= 0 and macd_hist.iloc[-1] > 0) or (macd.iloc[-2] <= macd_sig.iloc[-2] and macd.iloc[-1] > macd_sig.iloc[-1])
    bb_expanding = bb_bw.iloc[-1] > bb_bw.iloc[-2]
    if macd_bullish and bb_expanding:
        signals.append({
            "strategy": "Bollinger Squeeze + MACD",
            "reason": "Volatility expansion after squeeze confirmed with MACD Bullish cross",
            "strength": "Medium"
        })

    # 7. MFI Whale Accumulation: MFI was < 22 and now curling up with Whale Volume & Structure
    mfi_deep = (mfi.iloc[-4:-1].min() < 22)
    mfi_rising = (mfi.iloc[-1] > mfi.iloc[-2]) and (current_close > current_open)
    mfi_vol_ok = current_vol >= 1.2 * vol_sma20
    mfi_structure_ok = (current_close >= ema20.iloc[-1]) or (current_close >= ema50.iloc[-1])
    if mfi_deep and mfi_rising and mfi_vol_ok and mfi_structure_ok:
        signals.append({
            "strategy": "MFI Whale Accumulation",
            "reason": f"Smart money accumulation detected: MFI dipped to {mfi.iloc[-4:-1].min():.1f} and curling up with volume {current_vol/vol_sma20:.1f}x",
            "strength": "High"
        })

    # 8. RSI Bullish Divergence: Price Lower Low, RSI Higher Low
    if check_rsi_divergence(df, rsi, lookback=25):
        signals.append({
            "strategy": "RSI Bullish Divergence",
            "reason": f"Confirmed Bullish Divergence between Price action and RSI ({rsi.iloc[-1]:.1f})",
            "strength": "High"
        })

    # 9. Ichimoku Kumo Breakout: Price closes above cloud, Tenkan > Kijun
    cloud_top = np.maximum(span_a.iloc[-1], span_b.iloc[-1])
    prev_cloud_top = np.maximum(span_a.iloc[-2], span_b.iloc[-2])
    if not np.isnan(cloud_top):
        kumo_breakout = (prev_close <= prev_cloud_top and current_close > cloud_top)
        if kumo_breakout and (tenkan.iloc[-1] >= kijun.iloc[-1]):
            signals.append({
                "strategy": "Ichimoku Kumo Breakout",
                "reason": "Price broke out above Ichimoku Cloud (Kumo) with Tenkan >= Kijun",
                "strength": "High"
            })

    # 10. Donchian Breakout + Volume
    donch_high = donchian_up.iloc[-1]
    if not np.isnan(donch_high):
        donch_break = (current_close > donch_high)
        vol_confirmed = (current_vol > 1.25 * vol_sma20)
        if donch_break and vol_confirmed:
            signals.append({
                "strategy": "Donchian Breakout + Volume",
                "reason": f"Breakout above 20-period High with heavy Volume ({current_vol/vol_sma20:.1f}x avg)",
                "strength": "High"
            })

    # 11. Whale Accumulation Pre-Pump: Volatility Squeeze + 2.5x - 10x Volume Absorption Surge
    # Pattern reverse-engineered from explosive breakouts in AVA (+58%), AXL (+36%), and PYTH (+29%)
    vol_baseline = df['volume'].iloc[-16:-1].median() if len(df) >= 16 else vol_sma20
    vol_ratio = current_vol / (vol_baseline + 1e-10)

    recent_bw = bb_bw.iloc[-10:-1]
    min_bw = recent_bw.min() if len(recent_bw) > 0 else 0.2
    mean_bw = recent_bw.mean() if len(recent_bw) > 0 else 0.2
    is_squeezed = (min_bw < 0.16) or (mean_bw < 0.18) or (bb_bw.iloc[-1] < 0.14)

    candle_gain_pct = ((current_close - current_open) / current_open) * 100
    lower_wick = current_close - df['low'].iloc[-1] if current_close >= current_open else current_open - df['low'].iloc[-1]
    upper_wick = df['high'].iloc[-1] - current_close if current_close >= current_open else df['high'].iloc[-1] - current_open
    is_bullish_action = (current_close > current_open) or (lower_wick >= 1.2 * upper_wick)

    if (vol_ratio >= 2.5) and is_squeezed and is_bullish_action and (-1.5 <= candle_gain_pct <= 8.5) and (rsi.iloc[-1] <= 66):
        signals.append({
            "strategy": "Whale Accumulation Pre-Pump",
            "reason": f"🔥 رصد تجميع حيتان استباقي: انفجار فوليوم {vol_ratio:.1f}x بعد انكماش وضغط بولنجر ({min_bw:.2f})",
            "strength": "High"
        })

    # 12. Ichimoku Tenkan / Kijun Bullish Cross (TK Cross)
    tk_cross_now = (tenkan.iloc[-2] <= kijun.iloc[-2] and tenkan.iloc[-1] > kijun.iloc[-1])
    tk_cross_recent = (tenkan.iloc[-3] <= kijun.iloc[-3] and tenkan.iloc[-2] > kijun.iloc[-2]) and (tenkan.iloc[-1] >= kijun.iloc[-1])
    if (tk_cross_now or tk_cross_recent) and (current_close >= kijun.iloc[-1]):
        signals.append({
            "strategy": "Ichimoku Tenkan/Kijun Bullish Cross",
            "reason": f"قوة اتجاهية: تقاطع ذهبي لخط التنكن ({tenkan.iloc[-1]:.4f}) فوق الكيجون ({kijun.iloc[-1]:.4f}) مع ثبات السعر أعلاهما",
            "strength": "High"
        })

    return signals
