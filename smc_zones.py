"""
Зони Smart Money: Order Blocks, Fair Value Gap (FVG), Liquidity Sweep.

Ці три речі разом зі структурою (BOS/CHoCH з smc_structure.py) formуть
повний SMC-сетап:

  1. Liquidity Sweep — ціна "хантить" стопи за попереднім екстремумом
     (пробиває фітилем, але закривається назад) -> сигнал, що великі
     гравці зібрали ліквідність
  2. CHoCH — після sweep структура ринку змінюється -> підтвердження
     розвороту
  3. Order Block / FVG — ціна повертається в зону, де залишився
     "слід" великого гравця -> тут шукаємо вхід
"""
import pandas as pd

from smc_structure import find_swings


# ============================================================
# ORDER BLOCKS
# ============================================================

def find_order_blocks(df: pd.DataFrame, events: list[dict], lookback: int = 15) -> list[dict]:
    """
    Order Block — остання свічка ПРОТИЛЕЖНОГО напрямку перед імпульсним
    рухом, що призвів до BOS/CHoCH.

    Наприклад: перед сильним зростанням, що пробило структуру (bullish
    BOS/CHoCH), шукаємо останню червону (спадну) свічку — це і є
    bullish Order Block. Коли ціна повертається в цю зону — це
    потенційна точка входу в лонг.

    Параметр `events` — результат smc_structure.detect_structure_events().
    """
    order_blocks = []

    for event in events:
        break_idx = df.index.get_loc(event["timestamp"])
        start = max(0, break_idx - lookback)
        segment = df.iloc[start: break_idx + 1]

        if event["direction"] == "bullish":
            # шукаємо останню спадну (bearish) свічку перед пробиттям вгору
            down_candles = segment[segment["close"] < segment["open"]]
            if len(down_candles) == 0:
                continue
            ob_time = down_candles.index[-1]
            ob_candle = down_candles.iloc[-1]
            ob_type = "bullish_OB"
        else:
            # шукаємо останню зростаючу (bullish) свічку перед пробиттям вниз
            up_candles = segment[segment["close"] > segment["open"]]
            if len(up_candles) == 0:
                continue
            ob_time = up_candles.index[-1]
            ob_candle = up_candles.iloc[-1]
            ob_type = "bearish_OB"

        order_blocks.append({
            "timestamp": ob_time,
            "type": ob_type,
            "top": ob_candle["high"],
            "bottom": ob_candle["low"],
            "related_event": event["type"],       # BOS чи CHoCH
            "related_event_time": event["timestamp"],
        })

    return order_blocks


# ============================================================
# FAIR VALUE GAP (FVG)
# ============================================================

def find_fvgs(df: pd.DataFrame) -> list[dict]:
    """
    Fair Value Gap — імбаланс між трьома свічками: якщо high першої
    свічки нижчий за low третьої (при русі вгору), між ними лишається
    "незаповнений" ціновий проміжок. Ринок часто повертається туди
    "закрити" цей гап перед продовженням руху.

    Bullish FVG: high[i-1] < low[i+1]  (гап знизу вгору)
    Bearish FVG: low[i-1]  > high[i+1] (гап зверху вниз)
    """
    fvgs = []

    for i in range(1, len(df) - 1):
        c1 = df.iloc[i - 1]
        c3 = df.iloc[i + 1]

        if c1["high"] < c3["low"]:
            fvgs.append({
                "timestamp": df.index[i],
                "type": "bullish_FVG",
                "top": c3["low"],
                "bottom": c1["high"],
            })
        elif c1["low"] > c3["high"]:
            fvgs.append({
                "timestamp": df.index[i],
                "type": "bearish_FVG",
                "top": c1["low"],
                "bottom": c3["high"],
            })

    return fvgs


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def find_liquidity_sweeps(df: pd.DataFrame, window: int = 3) -> list[dict]:
    """
    Liquidity Sweep — свічка пробиває фітилем попередній swing high/low
    (там, де стоять стопи трейдерів), але ЗАКРИВАЄТЬСЯ назад всередині
    діапазону. Це класичний "стоп-хант" великих гравців перед
    справжнім рухом у протилежну сторону.

    sell_side_sweep — пробиття swing LOW вниз з закриттям вище нього
                       (ліквідність знята знизу -> часто передує руху ВГОРУ)
    buy_side_sweep  — пробиття swing HIGH вгору з закриттям нижче нього
                       (ліквідність знята зверху -> часто передує руху ВНИЗ)
    """
    if "swing_high" not in df.columns or "swing_low" not in df.columns:
        df = find_swings(df, window=window)

    sweeps = []
    last_swing_high = None
    last_swing_low = None

    for idx, row in df.iterrows():
        if last_swing_high is not None:
            if row["high"] > last_swing_high and row["close"] < last_swing_high:
                sweeps.append({
                    "timestamp": idx,
                    "type": "buy_side_sweep",
                    "swept_level": last_swing_high,
                    "wick_high": row["high"],
                })

        if last_swing_low is not None:
            if row["low"] < last_swing_low and row["close"] > last_swing_low:
                sweeps.append({
                    "timestamp": idx,
                    "type": "sell_side_sweep",
                    "swept_level": last_swing_low,
                    "wick_low": row["low"],
                })

        if row["swing_high"]:
            last_swing_high = row["high"]
        if row["swing_low"]:
            last_swing_low = row["low"]

    return sweeps
