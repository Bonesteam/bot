"""
Теоретичний доларовий результат сигналів (paper trading).

ВАЖЛИВО: це НЕ реальний прибуток з testnet-балансу - жодна угода
насправді не відкривалась (monitor.py тільки сповіщає). Це розрахунок
"а скільки б це принесло", якби на кожен сигнал ризикували фіксований
% від поточного балансу - так само, як рахує run_backtest.py, але
на основі ваших РЕАЛЬНИХ live-сигналів, а не історичних даних.

Розрахунок НЕ компаундиться (без реінвестування прибутку) - ризик на
кожну угоду береться від ПОТОЧНОГО балансу на момент запуску скрипта,
щоб не ускладнювати непрозорим "що було б, якби баланс ріс". Це дає
консервативнішу, простішу для розуміння оцінку.

Запуск:
    python check_pnl.py
"""
from config import Config
from binance_client import get_exchange, get_account_balance
from signal_tracker import load_signals


def calculate_theoretical_pnl(signals: list[dict], balance: float, risk_pct: float) -> dict:
    """Рахує теоретичний $ результат по закритих сигналах."""
    closed = [s for s in signals if s["status"] in ("win", "loss")]
    risk_amount = balance * risk_pct

    trades = []
    total_usd = 0.0
    for s in closed:
        usd = s["r_multiple"] * risk_amount
        total_usd += usd
        trades.append({**s, "usd_result": usd})

    return {
        "risk_amount_per_trade": risk_amount,
        "total_closed": len(closed),
        "total_usd": total_usd,
        "trades": trades,
    }


def main():
    Config.validate()
    exchange = get_exchange()

    print("Отримую поточний баланс...")
    balance_info = get_account_balance(exchange)
    balance = float(balance_info.get("total", 0) or 0)
    print(f"Поточний баланс testnet: {balance:.2f} USDT\n")

    signals = load_signals()
    if not signals:
        print("Ще жодного сигналу не залоговано.")
        return

    result = calculate_theoretical_pnl(signals, balance, Config.RISK_PER_TRADE_PCT)

    print(f"=== Теоретичний результат (якби торгували реально) ===")
    print(f"Ризик на угоду: {Config.RISK_PER_TRADE_PCT*100}% від балансу = {result['risk_amount_per_trade']:.2f} USDT\n")

    print("--- Деталі закритих угод ---")
    for t in result["trades"]:
        emoji = "✅" if t["outcome"] == "win" else "❌"
        print(f"{emoji} {t['symbol']:10s} {t['direction']:5s} | R={t['r_multiple']:+.1f} | "
              f"~{t['usd_result']:+.2f} USDT")

    print(f"\n=== ПІДСУМОК ===")
    print(f"Закритих угод: {result['total_closed']}")
    print(f"Теоретичний результат: {result['total_usd']:+.2f} USDT")
    print(f"\n⚠️  Це НЕ реальний баланс - жодна угода фактично не відкривалась.")
    print(f"    Реальний testnet-баланс лишається незмінним, поки не увімкнете")
    print(f"    AUTO_TRADE_ENABLED=true в auto_trade.py.")


if __name__ == "__main__":
    main()
