"""
Обгортка над ccxt для роботи з Binance USDT-M Futures.
На цьому етапі бот тільки ЧИТАЄ дані (свічки) - жодних ордерів.
"""
import ccxt
import pandas as pd

from config import Config


def get_exchange() -> ccxt.binance:
    """Створює підключення до Binance Futures (demo/testnet або live залежно від .env)."""
    exchange = ccxt.binance({
        "apiKey": Config.BINANCE_API_KEY,
        "secret": Config.BINANCE_API_SECRET,
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",  # USDT-M Futures
        },
    })

    if Config.BINANCE_TESTNET:
        # ВАЖЛИВО: старий testnet.binancefuture.com і ccxt-шний
        # set_sandbox_mode() для ф'ючерсів більше не підтримуються.
        # Binance замінив testnet на вбудований в основний акаунт режим
        # "Demo Trading". ccxt має для цього офіційний метод -
        # enable_demo_trading(), який сам перемикає всі ендпоінти
        # (fapi/dapi/spot) на demo-домени і сам уникає зайвих
        # spot/margin запитів, які demo-ключ не підтримує.
        exchange.enable_demo_trading(True)

    return exchange


def fetch_candles(exchange: ccxt.binance, symbol: str = None,
                   timeframe: str = None, limit: int = 500) -> pd.DataFrame:
    """
    Завантажує історичні свічки (OHLCV) з Binance Futures.

    Повертає pandas DataFrame з колонками:
    timestamp, open, high, low, close, volume
    """
    symbol = symbol or Config.SYMBOL
    timeframe = timeframe or Config.TIMEFRAME

    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    return df


def get_account_balance(exchange: ccxt.binance) -> dict:
    """Отримує баланс ф'ючерсного акаунту (корисно для перевірки, що ключі працюють)."""
    balance = exchange.fetch_balance()
    return balance.get("USDT", {})
