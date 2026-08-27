"""
Крок 6: повна автоторгівля на Binance Futures Testnet.

Це фінальна версія бота: сам дивиться графіки (по всіх монетах з
WATCHLIST), знаходить SMC-сетап, розраховує розмір позиції за
ризик-менеджментом, відкриває угоду з автоматичним SL/TP, і надсилає
звіт в Telegram.

ПЕРШ НІЖ ЗАПУСТИТИ:
1. Переконайтесь, що BINANCE_TESTNET=true в .env (це не testnet за
   замовчуванням - перевірте самі)
2. Встановіть AUTO_TRADE_ENABLED=true в .env (за замовчуванням вимкнено)
3. Прогнали run_backtest.py і результат вас влаштовує
4. Розумієте, що навіть на testnet бот може відкривати позиції, які
   ви не очікували - слідкуйте за першими днями роботи

ВАЖЛИВО: використовує той самий notified_setups.json, що й monitor.py -
якщо сетап вже був надісланий через monitor.py, тут він не відкриється
повторно як угода. Це дозволяє безпечно перемикатись між monitor.py
та auto_trade.py без дублювання.

Запуск:
    python auto_trade.py

Зупинка: Ctrl+C
"""
import time
from datetime import datetime, timezone

from config import Config
from binance_client import get_exchange, fetch_candles, get_account_balance
from smc_setup import get_active_setup
from telegram_notifier import send_telegram_message, format_setup_message
from risk_manager import RiskManager
from trade_executor import calculate_position_size, open_position_with_sl_tp, set_leverage
from monitor import load_notified, save_notified, format_closed_signal_message
from signal_tracker import log_new_signal, check_pending_signals, compute_stats, format_stats_message

CHECK_INTERVAL_SECONDS = 5 * 60
STATS_REPORT_EVERY_N_CYCLES = 12  # ~раз на годину при інтервалі 5 хв


def format_trade_opened_message(setup: dict, sizing: dict, symbol: str) -> str:
    emoji = "🟢" if setup["direction"] == "LONG" else "🔴"
    return (
        f"{emoji} <b>УГОДУ ВІДКРИТО: {setup['direction']}</b>\n"
        f"Пара: {symbol}\n\n"
        f"Entry: {setup['entry_price']}\n"
        f"Stop Loss: {setup['stop_loss']}\n"
        f"Take Profit: {setup['take_profit']}\n\n"
        f"Розмір позиції: {sizing['quantity']:.5f} {symbol.split('/')[0]}\n"
        f"Обсяг угоди (notional): {sizing['notional']:.2f} USDT\n"
        f"Плече: {Config.LEVERAGE}x\n"
        f"Використана маржа: {sizing['required_margin']:.2f} USDT\n"
        f"Ризик (у разі SL): {sizing['risk_amount']:.2f} USDT\n"
        f"R:R = 1:{setup['risk_reward']}"
    )


def format_stats_message_usd(stats: dict, balance: float, risk_pct: float) -> str:
    """
    Розширює звичайний звіт статистики приблизним доларовим результатом.
    Розрахунок НЕ компаундиться (ризик на угоду береться від ПОТОЧНОГО
    балансу на момент звіту) - проста, консервативна оцінка, а не точний
    облік руху балансу угода за угодою.
    """
    risk_amount = balance * risk_pct
    total_usd = stats["total_r"] * risk_amount
    base = format_stats_message(stats)
    return (
        f"{base}\n\n"
        f"💰 Приблизний $ результат: {total_usd:+.2f} USDT\n"
        f"(ризик/угода ≈ {risk_amount:.2f} USDT від поточного балансу {balance:.2f} USDT)"
    )


def check_and_trade_symbol(exchange, symbol: str, risk_mgr: RiskManager, notified: set) -> set:
    """Перевіряє одну монету і за потреби відкриває угоду."""
    df = fetch_candles(exchange, symbol=symbol, limit=300)
    current_price = df["close"].iloc[-1]
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    setup = get_active_setup(df, current_price)
    if setup is None:
        return notified

    setup_key = f"{symbol}:{setup['choch_time']}"
    if setup_key in notified:
        return notified

    print(f"[{timestamp}] 🎯 Новий сетап: {symbol} {setup['direction']}")

    # 1. Перевірка ризик-лімітів
    # ВАЖЛИВО: використовуємо TOTAL баланс (весь капітал), а не FREE.
    # FREE зменшується щоразу, коли частина балансу йде під маржу відкритої
    # позиції - це НЕ є збитком, тому денний ліміт збитку рахуємо від
    # реальної зміни загального капіталу, а не доступного залишку.
    balance_info = get_account_balance(exchange)
    total_balance = float(balance_info.get("total", 0) or 0)

    can_trade, reason = risk_mgr.can_open_trade(total_balance)
    if not can_trade:
        print(f"⛔ Угода НЕ відкрита ({symbol}): {reason}")
        send_telegram_message(
            f"⛔ Знайдено сетап {symbol} {setup['direction']}, але угода НЕ відкрита.\nПричина: {reason}"
        )
        notified.add(setup_key)
        save_notified(notified)
        return notified

    # 2. Розрахунок розміру позиції
    sizing = calculate_position_size(total_balance, setup["entry_price"], setup["stop_loss"])
    if not sizing["sufficient_margin"]:
        print(f"⛔ Угода НЕ відкрита ({symbol}): недостатньо маржі")
        send_telegram_message(
            f"⛔ Знайдено сетап {symbol} {setup['direction']}, але недостатньо маржі "
            f"на балансі для розміру позиції з заданим ризиком."
        )
        notified.add(setup_key)
        save_notified(notified)
        return notified

    # 3. Якщо автоторгівля вимкнена - тільки сповіщення (як у monitor.py)
    if not Config.AUTO_TRADE_ENABLED:
        print(f"ℹ️  AUTO_TRADE_ENABLED=false - надсилаю лише сповіщення по {symbol}")
        send_telegram_message(format_setup_message(setup, symbol, Config.TIMEFRAME))
        log_new_signal(symbol, setup)  # трекаємо так само, як і monitor.py
        notified.add(setup_key)
        save_notified(notified)
        return notified

    # 4. Відкриття угоди
    try:
        set_leverage(exchange, symbol)
        result = open_position_with_sl_tp(
            exchange, symbol, setup["direction"],
            sizing["quantity"], setup["stop_loss"], setup["take_profit"],
        )
        print(f"✅ Угоду відкрито: {result['quantity']} {symbol}")
        risk_mgr.record_trade_opened()
        log_new_signal(symbol, setup)  # логуємо для трекінгу реального результату (SL/TP)
        send_telegram_message(format_trade_opened_message(setup, sizing, symbol))
    except Exception as e:
        print(f"⚠️  Помилка при відкритті угоди ({symbol}): {e}")
        send_telegram_message(f"⚠️ Помилка при спробі відкрити угоду {symbol} {setup['direction']}: {e}")

    notified.add(setup_key)
    save_notified(notified)
    return notified


def main():
    Config.validate()

    mode = "TESTNET" if Config.BINANCE_TESTNET else "⚠️ LIVE (реальні гроші!)"
    auto = "УВІМКНЕНА" if Config.AUTO_TRADE_ENABLED else "вимкнена (тільки сповіщення)"
    print(f"=== Режим: {mode} | Автоторгівля: {auto} ===")
    print(f"Монети: {', '.join(Config.WATCHLIST)}")
    print(f"Ризик на угоду: {Config.RISK_PER_TRADE_PCT*100}% | "
          f"Плече: {Config.LEVERAGE}x | Ліміт угод/день: {Config.MAX_TRADES_PER_DAY}\n")

    exchange = get_exchange()
    risk_mgr = RiskManager()
    notified = load_notified()  # той самий файл, що й monitor.py - без дублювання
    cycle_count = 0

    while True:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        checked_any = False

        for symbol in Config.WATCHLIST:
            try:
                notified = check_and_trade_symbol(exchange, symbol, risk_mgr, notified)
                checked_any = True
            except Exception as e:
                print(f"⚠️  Помилка при перевірці {symbol}: {e}")

        if checked_any:
            print(f"[{timestamp}] Перевірено {len(Config.WATCHLIST)} монет.")

        # Перевіряємо, чи закрились раніше відкриті угоди (SL/TP)
        try:
            just_closed = check_pending_signals(exchange, fetch_candles)
            for signal in just_closed:
                print(f"[{timestamp}] Угоду закрито: {signal['symbol']} {signal['outcome']} "
                      f"({signal['r_multiple']:+.1f}R)")
                send_telegram_message(format_closed_signal_message(signal))
        except Exception as e:
            print(f"⚠️  Помилка при перевірці закритих угод: {e}")

        # Раз на годину (приблизно) надсилаємо зведену статистику з $ результатом
        cycle_count += 1
        if cycle_count % STATS_REPORT_EVERY_N_CYCLES == 0:
            stats = compute_stats()
            if stats["total_closed"] > 0:
                try:
                    balance_info = get_account_balance(exchange)
                    balance = float(balance_info.get("total", 0) or balance_info.get("free", 0) or 0)
                    msg = format_stats_message_usd(stats, balance, Config.RISK_PER_TRADE_PCT)
                except Exception:
                    msg = format_stats_message(stats)  # якщо баланс не вдалось отримати - без $ частини
                print(f"[{timestamp}] 📊 Звіт статистики: {stats}")
                send_telegram_message(msg)

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
