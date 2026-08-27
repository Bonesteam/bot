"""
Крок 5: бектест стратегії на історичних даних Binance.

Запуск:
    python run_backtest.py

Що робить:
1. Завантажує максимально доступну історію 1H свічок (до 1500 свічок ≈ 2 місяці)
2. Прогонює всі SMC-сетапи, які знайшла б стратегія за цей час
3. Симулює результат кожної угоди (SL чи TP спрацював першим)
4. Виводить статистику: win rate, середній R, просадка, profit factor
5. Зберігає деталі кожної угоди в trades_history.csv для ручного перегляду

Пам'ятайте: минулі результати НЕ гарантують майбутніх. Це інструмент
оцінки логіки, а не обіцянка прибутку. Дивіться не лише на win rate,
а й на profit factor і максимальну просадку.
"""
import csv

from config import Config
from binance_client import get_exchange, fetch_candles
from backtest import run_backtest, compute_stats


def save_trades_csv(trades: list[dict], filename: str = "trades_history.csv"):
    if not trades:
        return
    fieldnames = [
        "direction", "entry_time", "entry_price", "stop_loss", "take_profit",
        "zone_type", "outcome", "r_multiple", "exit_time",
    ]
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for t in trades:
            writer.writerow(t)


def main():
    Config.validate()
    exchange = get_exchange()

    print(f"Завантажую історію {Config.SYMBOL} ({Config.TIMEFRAME})...")
    # 1500 годинних свічок ≈ 62 дні. Binance зазвичай віддає максимум ~1000-1500 за раз.
    df = fetch_candles(exchange, limit=1500)
    print(f"Отримано {len(df)} свічок: з {df.index[0]} по {df.index[-1]}\n")

    trades = run_backtest(df)
    stats = compute_stats(trades)

    print("=== Результати бектесту ===")
    print(f"Всього угод: {stats['total_trades']}")
    print(f"Прибуткових: {stats['wins']} | Збиткових: {stats['losses']}")
    print(f"Win rate: {stats['win_rate']}%")
    print(f"Сумарний R: {stats['total_r']}")
    print(f"Середній R на угоду: {stats['avg_r']}")
    print(f"Profit factor: {stats['profit_factor']}")
    print(f"Максимальна просадка: {stats['max_drawdown_r']}R")

    if trades:
        save_trades_csv(trades)
        print(f"\nДеталі всіх угод збережено у trades_history.csv")

    print("\n--- Як читати результати ---")
    print("Profit factor > 1.5 і win rate достатній для обраного R:R —")
    print("стратегія показує потенціал. Але перед реальними грошима")
    print("варто прогнати на довшій історії (кілька місяців-рік) та")
    print("протестувати на testnet у реальному часі (крок 6).")


if __name__ == "__main__":
    main()
