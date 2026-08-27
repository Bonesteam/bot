"""
Один цикл моніторингу - для запуску через GitHub Actions за розкладом
(замість нескінченного циклу в monitor.py, який потребує постійно
працюючого комп'ютера чи сервера).

GitHub Actions сам запускає цей скрипт кожні 5 хвилин (workflow
.github/workflows/monitor.yml), а стан (які сигнали вже надіслані,
історія для трекінгу) зберігається у файлах, які workflow автоматично
закомічує назад у репозиторій після кожного запуску.

Локально можна так само запускати вручну:
    python run_once.py

(Функції для перевірки монет і форматування повідомлень перевикористані
з monitor.py - жодного дублювання логіки.)
"""
from datetime import datetime, timezone

from config import Config
from binance_client import get_exchange, fetch_candles
from monitor import load_notified, save_notified, check_symbol, format_closed_signal_message
from signal_tracker import check_pending_signals
from telegram_notifier import send_telegram_message


def main():
    Config.validate()
    exchange = get_exchange()
    notified = load_notified()
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    # 1. Шукаємо нові сетапи по всіх монетах зі списку
    new_found = 0
    for symbol in Config.WATCHLIST:
        try:
            before = len(notified)
            notified = check_symbol(exchange, symbol, notified)
            if len(notified) > before:
                new_found += 1
        except Exception as e:
            print(f"⚠️  Помилка при перевірці {symbol}: {e}")

    if new_found == 0:
        print(f"[{timestamp}] Перевірено {len(Config.WATCHLIST)} монет — нових сетапів немає.")

    # 2. Перевіряємо, чи закрились раніше надіслані сигнали (SL/TP)
    try:
        just_closed = check_pending_signals(exchange, fetch_candles)
        for signal in just_closed:
            print(f"[{timestamp}] Сигнал закрито: {signal['symbol']} {signal['outcome']} "
                  f"({signal['r_multiple']:+.1f}R)")
            send_telegram_message(format_closed_signal_message(signal))
    except Exception as e:
        print(f"⚠️  Помилка при перевірці закритих сигналів: {e}")

    print(f"[{timestamp}] Цикл завершено.")


if __name__ == "__main__":
    main()
