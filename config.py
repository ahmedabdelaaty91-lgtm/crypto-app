# config.py
# Configuration for Crypto Spot Scanner (Binance Spot)

# Exchange API (Using Binance Vision public endpoint which is never geo-blocked by US cloud/GitHub Actions)
BINANCE_API_URL = "https://data-api.binance.vision/api/v3"

# Timeframes to monitor
TIMEFRAMES = ["4h", "1d"]

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8913224513:AAHSWPospHVspn49uTG_ifcAdmxBle-iMjg"
TELEGRAM_CHAT_ID = "7760401819"

# The 160 spot coins to monitor (USDT pairs)
COINS_RAW = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT",
    "POL", "NEAR", "SHIB", "LTC", "UNI", "ICP", "BCH", "ATOM", "XLM", "ETC",
    "FIL", "HBAR", "INJ", "IMX", "RENDER", "OP", "ARB", "SUI", "TIA", "SEI",
    "GRT", "AAVE", "ALGO", "THETA", "FLOW", "CHZ", "GALA", "SAND", "MANA", "AXS",
    "KAVA", "CELO", "AR", "PYTH", "MANTA", "JUP", "BONK", "FLOKI", "PEPE", "WIF",
    "NOT", "TAO", "FET", "PIXEL", "XEC", "PENDLE", "STRK", "ALT", "PORTAL", "XAI",
    "NEXO", "GMX", "CRV", "CAKE", "1INCH", "SNX", "COMP", "ZK", "ZRO", "ENA",
    "SAGA", "IOST", "JTO", "QTUM", "MINA", "APT", "BOME", "GAS", "TRUMP", "ZIL",
    "IOTA", "DASH", "ZEC", "RVN", "KSM", "BICO", "HMSTR", "CVC", "BAND", "DUSK",
    "LSK", "SNDKB", "XPL", "VANA", "AVA", "OGN", "OG", "SENT", "PUMP", "ONT",
    "WLD", "HYPE", "SKL", "CATI", "MUUB", "JST", "ONE", "SUPER", "AMP", "OPG",
    "EPIC", "EDEN", "BEAMX", "GPS", "AVNT", "OPEN", "OSMO", "SPK", "TRX", "ADBEB",
    "MBL", "MUBARAK", "QUICK", "CHIP", "AT", "SHELL", "BROCCOLI714", "ERA", "AGLD", "GNS",
    "IOTX", "CETUS", "PENGU", "TUT", "TWT", "HOME", "PEOPLE", "CITY", "RED", "BANANA",
    "VET", "MOVE", "BANK", "1000SATS", "PSG", "ATM", "PORTO", "MEME", "NVDAB", "1000CAT",
    "GTC", "BB", "HOT", "C98", "MANTRA", "KMNO", "SOLV", "FLUX", "HEMI", "VTHO"
]

# Aliases / corrections for Binance Spot pairs:
# E.g. MANTRA is traded as OM on Binance, BROCCOLI/ADBEB/etc.
SYMBOL_ALIASES = {
    "MANTRA": "OM",
    "POL": "POL",      # Formerly MATIC
    "RENDER": "RENDER",# Formerly RNDR
}

# Binance Spot Testnet Configuration (Automated Execution & Testing)
import os
BINANCE_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "rKPp8uQ5VJlBbp64nkszfVevuh56VVTLoM4LCCgVohEbNzyd3SB4mE9OowPsXIZE")
BINANCE_TESTNET_SECRET_KEY = os.getenv("BINANCE_TESTNET_SECRET_KEY", "Xn96v8wGmSDI5XVqjswKtqu50XI6aTDjru2vQ1Id6X8aQlh5JNi1JeOjhZ0gxHoe")
BINANCE_TESTNET_URL = "https://testnet.binance.vision"
ENABLE_TESTNET_TRADING = os.getenv("ENABLE_TESTNET_TRADING", "true").lower() == "true"
TESTNET_TRADE_AMOUNT_USDT = float(os.getenv("TESTNET_TRADE_AMOUNT_USDT", "10.0"))

