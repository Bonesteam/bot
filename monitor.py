"""
Крок 4: безперервний моніторинг ринку по КІЛЬКОХ монетах.

Це і є той "бот, що сам дивиться графіки" — працює в циклі, регулярно
перевіряє свіжі свічки по кожній монеті зі списку WATCHLIST, і як тільки
знаходить новий SMC-сетап на будь-якій з них — надсилає повідомлення
в Telegram. Кожен сетап (монета + момент CHoCH) надсилається лише ОДИН
раз (зберігаємо історію вже надісланих у файл).

Список монет задається в .env через WATCHLIST, наприклад:
    WATCHLIST=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT

Запуск (залишити працювати у терміналі або на сервері):
    python monitor.py

Зупинка: Ctrl+C
"""
import json
import os
import time
from datetime import datetime, timezone

from config import Config
from binance_client import get_exchange, fetch_candles
from smc_setup import get_active_setup
from telegram_notifier import send_telegram_message, format_setup_message
from signal_tracker import log_new_signal, check_pending_signals, compute_stats, format_stats_message

CHECK_INTERVAL_SECONDS = 5 * 60  # перевіряти кожні 5 хвилин
NOTIFIED_FILE = "notified_setups.json"
STATS_REPORT_EVERY_N_CYCLES = 12  # ~раз на годину при інтервалі 5 хв


def load_notified() -> set:
    """Завантажує список вже надісланих сетапів (за монета+CHoCH), щоб не дублювати."""
    if not os.path.exists(NOTIFIED_FILE):
        return set()
    with open(NOTIFIED_FILE, "r") as f:
        return set(json.load(f))


def save_notified(notified: set):
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(list(notified), f)


def check_symbol(exchange, symbol: str, notified: set) -> set:
    """Перевіряє одну монету: завантажує свічки, шукає сетап, надсилає якщо новий."""
    df = fetch_candles(exchange, symbol=symbol, limit=300)
    current_price = df["close"].iloc[-1]

    setup = get_active_setup(df, current_price)
    if setup is None:
        return notified

    # ключ включає монету, щоб однаковий CHoCH-час на різних парах не збігався
    setup_key = f"{symbol}:{setup['choch_time']}"

    if setup_key in notified:
        return notified

    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"[{timestamp}] 🎯 Новий сетап: {symbol} {setup['direction']} — надсилаю в Telegram...")

    message = format_setup_message(setup, symbol, Config.TIMEFRAME)
    sent = send_telegram_message(message)
    if sent:
        print("✅ Повідомлення надіслано.")

    log_new_signal(symbol, setup)  # записуємо сигнал для подальшого трекінгу результату

    notified.add(setup_key)
    save_notified(notified)
    return notified


def format_closed_signal_message(signal: dict) -> str:
    emoji = "✅" if signal["outcome"] == "win" else "❌"
    result_word = "ПЕРЕМОГА" if signal["outcome"] == "win" else "ПРОГРАШ"
    return (
        f"{emoji} <b>Сигнал закрито: {result_word}</b>\n"
        f"{signal['symbol']} {signal['direction']}\n"
        f"R: {signal['r_multiple']:+.1f}\n"
        f"Entry: {signal['entry_price']} → Exit: {signal['exit_time']}"
    )


def main():
    Config.validate()
    exchange = get_exchange()
    notified = load_notified()
    cycle_count = 0

    print(f"=== Моніторинг {len(Config.WATCHLIST)} монет ({Config.TIMEFRAME}) запущено ===")
    print(f"Список: {', '.join(Config.WATCHLIST)}")
    print(f"Перевірка кожні {CHECK_INTERVAL_SECONDS // 60} хв. Ctrl+C для зупинки.\n")

    while True:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        active_setups_found = 0

        # 1. Шукаємо нові сетапи по всіх монетах
        for symbol in Config.WATCHLIST:
            try:
                before = len(notified)
                notified = check_symbol(exchange, symbol, notified)
                if len(notified) > before:
                    active_setups_found += 1
            except Exception as e:
                print(f"⚠️  Помилка при перевірці {symbol}: {e}")

        if active_setups_found == 0:
            print(f"[{timestamp}] Перевірено {len(Config.WATCHLIST)} монет — нових сетапів немає.")

        # 2. Перевіряємо, чи закрились раніше надіслані сигнали (SL/TP)
        try:
            just_closed = check_pending_signals(exchange, fetch_candles)
            for signal in just_closed:
                print(f"[{timestamp}] Сигнал закрито: {signal['symbol']} {signal['outcome']} ({signal['r_multiple']:+.1f}R)")
                send_telegram_message(format_closed_signal_message(signal))
        except Exception as e:
            print(f"⚠️  Помилка при перевірці закритих сигналів: {e}")

        # 3. Раз на годину (приблизно) надсилаємо зведену статистику
        cycle_count += 1
        if cycle_count % STATS_REPORT_EVERY_N_CYCLES == 0:
            stats = compute_stats()
            if stats["total_closed"] > 0:
                print(f"[{timestamp}] 📊 Звіт статистики: {stats}")
                send_telegram_message(format_stats_message(stats))

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

