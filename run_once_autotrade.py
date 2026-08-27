"""
Один цикл ПОВНОЇ автоторгівлі - для запуску через GitHub Actions за розкладом.

На відміну від run_once.py (тільки сповіщення), цей скрипт виконує
повноцінний прогін auto_trade.py: перевіряє ризик-ліміти, розраховує
розмір позиції і РЕАЛЬНО ВІДКРИВАЄ угоди на Binance Futures Testnet.

Використовуйте це замість run_once.py тільки якщо свідомо хочете, щоб
бот сам торгував без вашого нагляду (навіть на testnet варто розуміти,
що це означає). Якщо потрібні лише сповіщення без автовходу - лишайте
AUTO_TRADE_ENABLED=false в Secrets/Variables репозиторію, і цей самий
скрипт поводитиметься як run_once.py (тільки сповіщення), завдяки
тій самій перевірці всередині check_and_trade_symbol.

Локально можна так само запускати вручну:
    python run_once_autotrade.py

(Функції перевикористані з auto_trade.py - жодного дублювання логіки.)
"""
from datetime import datetime, timezone

from config import Config
from binance_client import get_exchange, fetch_candles
from risk_manager import RiskManager
from telegram_notifier import send_telegram_message
from signal_tracker import check_pending_signals
from auto_trade import check_and_trade_symbol
from monitor import load_notified, format_closed_signal_message


def main():
    Config.validate()

    mode = "TESTNET" if Config.BINANCE_TESTNET else "⚠️ LIVE (реальні гроші!)"
    auto = "УВІМКНЕНА" if Config.AUTO_TRADE_ENABLED else "вимкнена (тільки сповіщення)"
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"[{timestamp}] === Режим: {mode} | Автоторгівля: {auto} ===")

    exchange = get_exchange()
    risk_mgr = RiskManager()
    notified = load_notified()

    # 1. Перевіряємо всі монети - шукаємо нові сетапи, за потреби відкриваємо угоди
    for symbol in Config.WATCHLIST:
        try:
            notified = check_and_trade_symbol(exchange, symbol, risk_mgr, notified)
        except Exception as e:
            print(f"⚠️  Помилка при перевірці {symbol}: {e}")

    print(f"[{timestamp}] Перевірено {len(Config.WATCHLIST)} монет.")

    # 2. Перевіряємо, чи закрились раніше відкриті угоди (SL/TP)
    try:
        just_closed = check_pending_signals(exchange, fetch_candles)
        for signal in just_closed:
            print(f"[{timestamp}] Угоду закрито: {signal['symbol']} {signal['outcome']} "
                  f"({signal['r_multiple']:+.1f}R)")
            send_telegram_message(format_closed_signal_message(signal))
    except Exception as e:
        print(f"⚠️  Помилка при перевірці закритих угод: {e}")

    print(f"[{timestamp}] Цикл завершено.")


if __name__ == "__main__":
    main()
