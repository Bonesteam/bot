"""
Бектест SMC-стратегії на історичних даних.

ВАЖЛИВО ПРО ОБМЕЖЕННЯ:
- Swing points підтверджуються з невеликою затримкою (window=3 свічки),
  тому є мінімальний lookahead — на реальному живому графіку сетап
  підтвердиться на 1-3 свічки пізніше, ніж тут. Це прийнятне спрощення
  для оцінки якості стратегії, але не ідеальна симуляція "секунда в секунду".
- Бектест НЕ враховує комісії біржі, сліпедж (slippage) та фандинг
  на ф'ючерсах — реальний результат буде трохи гіршим.
- Минулі результати не гарантують майбутніх — це інструмент оцінки
  логіки, а не обіцянка прибутку.

Що робить:
1. Знаходить усі сетапи за історію (find_setups)
2. Для кожного — перевіряє, чи ціна взагалі зайшла в зону входу
3. Якщо зайшла — симулює угоду вперед: що станеться раніше, SL чи TP
4. Рахує статистику: win rate, середній R, просадка, profit factor
"""
import pandas as pd

from smc_setup import find_setups


def find_entry_time(df: pd.DataFrame, setup: dict, max_bars_wait: int = 30):
    """
    Шукає першу свічку ПІСЛЯ CHoCH, де ціна фактично торкнулась зони входу.
    Якщо ціна так і не зайшла в зону за max_bars_wait свічок — сетап
    вважається "не спрацював" (пропускаємо його).
    """
    choch_idx = df.index.get_loc(setup["choch_time"])
    end_idx = min(len(df), choch_idx + max_bars_wait)

    for i in range(choch_idx + 1, end_idx):
        candle = df.iloc[i]
        if candle["low"] <= setup["zone_top"] and candle["high"] >= setup["zone_bottom"]:
            return i  # ціна торкнулась зони на цій свічці

    return None


def simulate_trade(df: pd.DataFrame, entry_idx: int, setup: dict, max_bars_forward: int = 200) -> dict:
    """
    Іде вперед від точки входу і дивиться, що станеться раніше — SL чи TP.
    Якщо на одній свічці зачепило і SL, і TP — консервативно рахуємо, що
    спрацював SL першим (реалістичніше для волатильного ринку).
    """
    direction = setup["direction"]
    sl = setup["stop_loss"]
    tp = setup["take_profit"]
    end_idx = min(len(df), entry_idx + max_bars_forward)

    for i in range(entry_idx, end_idx):
        candle = df.iloc[i]

        if direction == "LONG":
            hit_sl = candle["low"] <= sl
            hit_tp = candle["high"] >= tp
        else:
            hit_sl = candle["high"] >= sl
            hit_tp = candle["low"] <= tp

        if hit_sl:
            return {"outcome": "loss", "r_multiple": -1.0, "exit_time": df.index[i]}
        if hit_tp:
            return {"outcome": "win", "r_multiple": setup["risk_reward"], "exit_time": df.index[i]}

    return {"outcome": "no_hit", "r_multiple": 0.0, "exit_time": None}


def run_backtest(df: pd.DataFrame) -> list[dict]:
    """Прогонює повний бектест і повертає список угод з результатами."""
    setups = find_setups(df)
    trades = []

    for setup in setups:
        entry_idx = find_entry_time(df, setup)
        if entry_idx is None:
            continue  # ціна так і не зайшла в зону - сетап не спрацював

        result = simulate_trade(df, entry_idx, setup)
        if result["outcome"] == "no_hit":
            continue  # угода ще "відкрита" на кінець даних - не рахуємо в статистику

        trades.append({**setup, "entry_time": df.index[entry_idx], **result})

    return trades


def compute_stats(trades: list[dict]) -> dict:
    """Рахує ключову статистику по списку угод."""
    if not trades:
        return {
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "total_r": 0.0, "avg_r": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0,
        }

    wins = [t for t in trades if t["outcome"] == "win"]
    losses = [t for t in trades if t["outcome"] == "loss"]

    total_r = sum(t["r_multiple"] for t in trades)
    avg_r = total_r / len(trades)
    win_rate = len(wins) / len(trades) * 100

    gross_win = sum(t["r_multiple"] for t in wins)
    gross_loss = abs(sum(t["r_multiple"] for t in losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    # максимальна просадка по кривій кумулятивного R
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        cumulative += t["r_multiple"]
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "total_r": round(total_r, 2),
        "avg_r": round(avg_r, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "max_drawdown_r": round(max_dd, 2),
    }
