"""
Крок 3: повний пошук SMC-сетапу на реальних 1H свічках Binance.

Запуск:
    python find_setup.py

Що робить:
1. Завантажує свічки з Binance Futures
2. Шукає повні сетапи: liquidity sweep -> CHoCH -> Order Block / FVG
3. Показує ВСІ знайдені сетапи за історію (для розуміння роботи логіки)
4. Окремо виділяє АКТУАЛЬНИЙ сетап (якщо ціна зараз близько до зони входу)

Це вершина того, що вже готово: аналіз без автоторгівлі.
Наступний крок - надсилання цього в Telegram, а вхід в угоди -
вже пізніше, після бектесту.
"""
from config import Config
from binance_client import get_exchange, fetch_candles
from smc_setup import find_setups, get_active_setup


def main():
    Config.validate()
    exchange = get_exchange()

    print(f"Завантажую {Config.SYMBOL} {Config.TIMEFRAME}...")
    df = fetch_candles(exchange, limit=300)
    current_price = df["close"].iloc[-1]

    setups = find_setups(df)
    print(f"\n=== Всі знайдені SMC-сетапи за історію ({Config.SYMBOL}) ===")
    print(f"Поточна ціна: {current_price:.2f}\n")

    if not setups:
        print("Сетапів не знайдено на цій історії свічок.")
    else:
        for s in setups:
            print(
                f"{s['direction']:5s} | entry={s['entry_price']} SL={s['stop_loss']} "
                f"TP={s['take_profit']} | R:R={s['risk_reward']} | zone={s['zone_type']} | "
                f"CHoCH@{s['choch_time']}"
            )

    print("\n=== Актуальний сетап прямо зараз ===")
    active = get_active_setup(df, current_price)
    if active is None:
        print("Наразі активного сетапу немає. Чекаємо наступну можливість.")
    else:
        print(f"Напрямок: {active['direction']}")
        print(f"Зона входу ({active['zone_type']}): {active['zone_bottom']} - {active['zone_top']}")
        print(f"Entry: {active['entry_price']}")
        print(f"Stop Loss: {active['stop_loss']}")
        print(f"Take Profit: {active['take_profit']}")
        print(f"Risk:Reward = 1:{active['risk_reward']}")
        print(f"\nЦе поки що ІНФОРМАЦІЯ, бот ще не відкриває угоду автоматично.")


if __name__ == "__main__":
    main()
