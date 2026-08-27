"""
Перегляд поточної статистики по live-сигналах у будь-який момент.

Запуск:
    python check_stats.py

Показує статистику по сигналах, які вже надіслав monitor.py — скільки
закрито (win/loss), win rate, profit factor. Працює незалежно від того,
запущений monitor.py прямо зараз чи ні (просто читає збережені дані).
"""
from signal_tracker import load_signals, compute_stats


def main():
    signals = load_signals()

    if not signals:
        print("Ще жодного сигналу не залоговано. Запустіть monitor.py і зачекайте на перший сетап.")
        return

    stats = compute_stats(signals)

    print("=== Статистика live-сигналів ===")
    print(f"Всього залоговано: {len(signals)}")
    print(f"Закрито: {stats['total_closed']} | В очікуванні: {stats['pending']}")
    print(f"Перемог: {stats['wins']} | Програшів: {stats['losses']}")
    print(f"Win rate: {stats['win_rate']}%")
    print(f"Сумарний R: {stats['total_r']}")
    print(f"Середній R: {stats['avg_r']}")
    print(f"Profit factor: {stats['profit_factor']}")

    if stats["total_closed"] < 30:
        print(f"\n⚠️  Лише {stats['total_closed']} закритих сигналів — це замала вибірка")
        print(f"    для статистичної впевненості. Бажано мати хоча б 30-50.")

    print("\n--- Останні 10 сигналів ---")
    for s in signals[-10:]:
        status_emoji = {"win": "✅", "loss": "❌", "pending": "⏳", "expired": "⌛"}.get(s["status"], "?")
        entry_info = "вхід ще не спрацював" if s.get("entry_time") is None and s["status"] == "pending" else \
                     (f"в угоді з {s['entry_time'][:16]}" if s.get("entry_time") else "")
        print(f"{status_emoji} {s['symbol']:10s} {s['direction']:5s} | status={s['status']:8s} | "
              f"R={s['r_multiple']} | {entry_info}")


if __name__ == "__main__":
    main()
