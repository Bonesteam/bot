"""
Крок 1: перевірка підключення до Binance Futures Testnet.

Що робить цей скрипт:
1. Перевіряє, що ключі API задані у .env
2. Підключається до Binance Futures Testnet
3. Показує баланс тестового акаунту
4. Завантажує останні 1H свічки по BTC/USDT і виводить у консоль

Ніяких угод бот на цьому етапі НЕ відкриває - тільки читає дані.
"""
from config import Config
from binance_client import get_exchange, fetch_candles, get_account_balance


def main():
    print("=== Перевірка конфігурації ===")
    Config.validate()
    mode = "TESTNET (віртуальні кошти)" if Config.BINANCE_TESTNET else "LIVE (реальні кошти!)"
    print(f"Режим: {mode}")
    print(f"Пара: {Config.SYMBOL}, таймфрейм: {Config.TIMEFRAME}\n")

    exchange = get_exchange()

    print("=== Баланс акаунту ===")
    balance = get_account_balance(exchange)
    print(balance, "\n")

    print(f"=== Останні свічки {Config.SYMBOL} ({Config.TIMEFRAME}) ===")
    df = fetch_candles(exchange, limit=10)
    print(df)


if __name__ == "__main__":
    main()
