"""
Трекер результатів live-сигналів.

Кожен сигнал, який бот надсилає в Telegram, тут записується з рівнями
entry/SL/TP. На кожному наступному циклі бот перевіряє свіжі свічки:
чи дійшла ціна до Take Profit (перемога) чи до Stop Loss (програш).

Це дає реальну статистику по вашим фактичним сигналам, без потреби
вручну стежити за кожним чи вкладати гроші.

Сигнал, що "висить" (жодне з двох не спрацювало) довше MAX_PENDING_HOURS
позначається як "expired" - вважаємо, що сетап себе вичерпав, і не
рахуємо його ні в плюс, ні в мінус.
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd

SIGNALS_FILE = "signals_log.json"
MAX_PENDING_HOURS = 168  # 7 днів - довше вважаємо сетап "застарілим"


def load_signals() -> list[dict]:
    if not os.path.exists(SIGNALS_FILE):
        return []
    with open(SIGNALS_FILE, "r") as f:
        return json.load(f)


def save_signals(signals: list[dict]):
    with open(SIGNALS_FILE, "w") as f:
        json.dump(signals, f, indent=2, default=str)


def log_new_signal(symbol: str, setup: dict):
    """Викликається одразу після надсилання сигналу в Telegram."""
    signals = load_signals()
    signals.append({
        "symbol": symbol,
        "direction": setup["direction"],
        "entry_price": setup["entry_price"],
        "stop_loss": setup["stop_loss"],
        "take_profit": setup["take_profit"],
        "risk_reward": setup["risk_reward"],
        "zone_top": setup["zone_top"],
        "zone_bottom": setup["zone_bottom"],
        "choch_time": str(setup["choch_time"]),
        "signal_time": datetime.now(timezone.utc).isoformat(),
        "status": "pending",       # pending -> triggered -> win / loss / expired
        "entry_time": None,        # коли ціна фактично зайшла в зону (None = ще не зайшла)
        "outcome": None,
        "exit_time": None,
        "r_multiple": None,
    })
    save_signals(signals)


def check_pending_signals(exchange, fetch_candles_fn) -> list[dict]:
    """
    Проходить по всіх сигналах зі статусом 'pending' і перевіряє свіжі
    свічки у ДВА етапи:

    1. Чи ціна взагалі ЗАЙШЛА в зону входу (Order Block / FVG) після CHoCH?
       Якщо ще ні - угода технічно "не відкрилась", сигнал лишається pending.
    2. Тільки ПІСЛЯ входу в зону - перевіряємо, що станеться раніше: SL чи TP.

    Без цього першого кроку можна помилково "закрити" сигнал, який
    насправді ніколи не спрацював (ціна пролетіла повз зону, зачепивши
    рівень SL/TP за збігом, без реального відкриття угоди).

    Повертає список сигналів, які ЩОЙНО закрились у цьому виклику.
    """
    signals = load_signals()
    just_closed = []

    for s in signals:
        if s["status"] != "pending":
            continue

        try:
            df = fetch_candles_fn(exchange, symbol=s["symbol"], limit=300)
        except Exception:
            continue  # тимчасова помилка мережі - спробуємо наступного циклу

        choch_time = pd.Timestamp(s["choch_time"])

        # --- Етап 1: чи зайшла ціна в зону входу? ---
        if s["entry_time"] is None:
            after_choch = df[df.index > choch_time]
            for idx, row in after_choch.iterrows():
                touched_zone = row["low"] <= s["zone_top"] and row["high"] >= s["zone_bottom"]
                if touched_zone:
                    s["entry_time"] = str(idx)
                    break

            if s["entry_time"] is None:
                continue  # ціна ще не зайшла в зону - чекаємо далі, сигнал лишається pending

        # --- Етап 2: перевіряємо SL/TP тільки з моменту фактичного входу ---
        entry_time = pd.Timestamp(s["entry_time"])
        after_entry = df[df.index > entry_time]

        for idx, row in after_entry.iterrows():
            if s["direction"] == "LONG":
                hit_sl = row["low"] <= s["stop_loss"]
                hit_tp = row["high"] >= s["take_profit"]
            else:
                hit_sl = row["high"] >= s["stop_loss"]
                hit_tp = row["low"] <= s["take_profit"]

            if hit_sl:
                s["status"] = "loss"
                s["outcome"] = "loss"
                s["r_multiple"] = -1.0
                s["exit_time"] = str(idx)
                just_closed.append(s)
                break
            if hit_tp:
                s["status"] = "win"
                s["outcome"] = "win"
                s["r_multiple"] = s["risk_reward"]
                s["exit_time"] = str(idx)
                just_closed.append(s)
                break

        # якщо все ще pending - перевіряємо, чи не "застарів" сигнал
        if s["status"] == "pending":
            signal_age = datetime.now(timezone.utc) - datetime.fromisoformat(s["signal_time"])
            if signal_age.total_seconds() / 3600 > MAX_PENDING_HOURS:
                s["status"] = "expired"

    save_signals(signals)
    return just_closed


def compute_stats(signals: list[dict] = None) -> dict:
    """Рахує статистику по всіх ЗАКРИТИХ сигналах (win/loss, без pending/expired)."""
    if signals is None:
        signals = load_signals()

    closed = [s for s in signals if s["status"] in ("win", "loss")]

    if not closed:
        return {
            "total_closed": 0, "pending": len([s for s in signals if s["status"] == "pending"]),
            "wins": 0, "losses": 0, "win_rate": 0.0,
            "total_r": 0.0, "avg_r": 0.0, "profit_factor": 0.0,
        }

    wins = [s for s in closed if s["outcome"] == "win"]
    losses = [s for s in closed if s["outcome"] == "loss"]

    total_r = sum(s["r_multiple"] for s in closed)
    avg_r = total_r / len(closed)
    win_rate = len(wins) / len(closed) * 100

    gross_win = sum(s["r_multiple"] for s in wins)
    gross_loss = abs(sum(s["r_multiple"] for s in losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float("inf")

    return {
        "total_closed": len(closed),
        "pending": len([s for s in signals if s["status"] == "pending"]),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "total_r": round(total_r, 2),
        "avg_r": round(avg_r, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
    }


def format_stats_message(stats: dict) -> str:
    return (
        f"📊 <b>Статистика live-сигналів</b>\n\n"
        f"Закрито: {stats['total_closed']} | В очікуванні: {stats['pending']}\n"
        f"Перемог: {stats['wins']} | Програшів: {stats['losses']}\n"
        f"Win rate: {stats['win_rate']}%\n"
        f"Сумарний R: {stats['total_r']}\n"
        f"Profit factor: {stats['profit_factor']}"
    )
