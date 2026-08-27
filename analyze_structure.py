"""
Крок 2: аналіз структури ринку (BOS / CHoCH) на реальних 1H свічках з Binance.

Запуск:
    python analyze_structure.py

Що робить:
1. Завантажує свічки з Binance Futures (testnet/live — залежно від .env)
2. Знаходить swing points
3. Визначає BOS/CHoCH події
4. Виводить поточний тренд і останні події структури

Це поки що АНАЛІЗ, не торгівля. На наступному кроці додамо
Order Blocks та Fair Value Gap поверх цієї структури.
"""
from config import Config
from binance_client import get_exchange, fetch_candles
from smc_structure import find_swings, detect_structure_events, get_current_trend


def main():
    Config.validate()
    exchange = get_exchange()

    print(f"Завантажую {Config.SYMBOL} {Config.TIMEFRAME}...")
    df = fetch_candles(exchange, limit=300)  # достатньо історії для структури

    df = find_swings(df, window=3)
    events = detect_structure_events(df)
    trend = get_current_trend(events)

    print(f"\n=== Структура ринку {Config.SYMBOL} ({Config.TIMEFRAME}) ===")
    print(f"Знайдено swing points: {df['swing_high'].sum()} high / {df['swing_low'].sum()} low")
    print(f"Всього подій BOS/CHoCH: {len(events)}")
    print(f"Поточний тренд: {trend}\n")

    print("Останні 5 подій структури:")
    for e in events[-5:]:
        print(f"  {e['timestamp']} | {e['type']:5s} | {e['direction']:8s} | price={e['price']:.2f}")

    if events and events[-1]["type"] == "CHoCH":
        print(f"\n⚠️  Остання подія — CHoCH ({events[-1]['direction']})."
              f" Це сигнал можливого розвороту тренду — варте уваги для сетапу.")


if __name__ == "__main__":
    main()
