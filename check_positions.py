"""
Перевірка реально відкритих позицій напряму на Binance (не з локального
трекера, а справжній стан на біржі).

Корисно, коли бот був вимкнений якийсь час, і незрозуміло - позиції ще
реально відкриті, чи вже закрились по SL/TP, а локальний трекер просто
не встиг це побачити.

Запуск:
    python check_positions.py
"""
from config import Config
from binance_client import get_exchange


def main():
    Config.validate()
    exchange = get_exchange()

    print("Запитую реальні позиції напряму з Binance...\n")
    positions = exchange.fetch_positions()

    # фільтруємо тільки реально відкриті (розмір позиції != 0)
    open_positions = [p for p in positions if float(p.get("contracts") or 0) != 0]

    if not open_positions:
        print("=== Немає жодної відкритої позиції на біржі ===")
        print("Всі попередні угоди вже закрились (по SL, TP, або вручну).")
        print("Якщо check_stats.py досі показує їх як 'pending' - трекер просто")
        print("не встиг це побачити. Запустіть monitor.py або auto_trade.py -")
        print("наступна перевірка сама підтягне актуальний результат.")
        return

    print(f"=== Реально відкритих позицій: {len(open_positions)} ===\n")
    for p in open_positions:
        symbol = p.get("symbol")
        side = p.get("side")
        contracts = p.get("contracts")
        entry_price = p.get("entryPrice")
        mark_price = p.get("markPrice")
        unrealized_pnl = p.get("unrealizedPnl")
        percentage = p.get("percentage")

        print(f"{symbol} | {side}")
        print(f"  Розмір: {contracts}")
        print(f"  Entry: {entry_price} | Поточна ціна: {mark_price}")
        print(f"  Floating PnL: {unrealized_pnl:.2f} USDT ({percentage:.2f}%)" if unrealized_pnl is not None else "  PnL: н/д")
        print()


if __name__ == "__main__":
    main()
