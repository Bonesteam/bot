"""
Пошук повного SMC-сетапу для входу в угоду.

Класична послідовність Smart Money сетапу:
  1. Liquidity Sweep — ціна хантить стопи за екстремумом (пастка)
  2. CHoCH — одразу після sweep структура ринку змінюється
     (підтверджує, що великі гравці розвернули ринок)
  3. Ціна відкатує назад в Order Block або FVG зону, залишену
     під час імпульсного руху
  4. ВХІД: коли ціна заходить у цю зону
     SL: за межі зони (+ невеликий буфер)
     TP: до найближчої протилежної ліквідності (попередній swing)

Це найбільш "чистий" за класичною SMC-теорією тип сетапу — тому
бот шукає саме його, а не будь-яке окреме BOS/CHoCH чи OB.
"""
import pandas as pd

from smc_structure import find_swings, detect_structure_events
from smc_zones import find_order_blocks, find_fvgs, find_liquidity_sweeps


def find_setups(df: pd.DataFrame, max_bars_between: int = 25) -> list[dict]:
    """
    Шукає послідовності sweep -> CHoCH -> OB/FVG в межах `max_bars_between`
    свічок одна від одної і формує готові торгові сетапи.

    Повертає список сетапів, кожен з:
      direction, entry_zone (top/bottom), stop_loss, take_profit,
      sweep_time, choch_time, zone_type, risk_reward
    """
    df = find_swings(df, window=3)
    events = detect_structure_events(df)
    order_blocks = find_order_blocks(df, events)
    fvgs = find_fvgs(df)
    sweeps = find_liquidity_sweeps(df)

    choch_events = [e for e in events if e["type"] == "CHoCH"]
    setups = []

    for choch in choch_events:
        choch_idx = df.index.get_loc(choch["timestamp"])

        # 1. шукаємо sweep безпосередньо перед цим CHoCH
        matching_sweep = None
        for sweep in sweeps:
            sweep_idx = df.index.get_loc(sweep["timestamp"])
            if 0 <= choch_idx - sweep_idx <= max_bars_between:
                # напрямок sweep має відповідати напрямку CHoCH
                if choch["direction"] == "bullish" and sweep["type"] == "sell_side_sweep":
                    matching_sweep = sweep
                elif choch["direction"] == "bearish" and sweep["type"] == "buy_side_sweep":
                    matching_sweep = sweep

        if matching_sweep is None:
            continue  # без sweep це не повний SMC-сетап

        # 2. шукаємо найближчу OB або FVG зону, повʼязану з цим CHoCH
        zone = None
        zone_type = None
        for ob in order_blocks:
            if ob["related_event_time"] == choch["timestamp"]:
                zone = ob
                zone_type = "Order Block"
                break

        if zone is None:
            # якщо OB нема - шукаємо найближчий FVG того ж напрямку одразу після CHoCH
            wanted_fvg_type = "bullish_FVG" if choch["direction"] == "bullish" else "bearish_FVG"
            candidates = [
                f for f in fvgs
                if f["type"] == wanted_fvg_type
                and df.index.get_loc(f["timestamp"]) >= choch_idx
                and df.index.get_loc(f["timestamp"]) <= choch_idx + max_bars_between
            ]
            if candidates:
                zone = candidates[0]
                zone_type = "FVG"

        if zone is None:
            continue  # немає зони для входу - пропускаємо

        # 3. формуємо рівні входу/стопу/тейку
        entry_top = zone["top"]
        entry_bottom = zone["bottom"]
        buffer = (entry_top - entry_bottom) * 0.15  # невеликий буфер під SL

        if choch["direction"] == "bullish":
            direction = "LONG"
            stop_loss = entry_bottom - buffer
            entry_price = entry_top  # консервативний вхід по верху зони
            risk = entry_price - stop_loss
            take_profit = entry_price + risk * 2  # мінімум 1:2
        else:
            direction = "SHORT"
            stop_loss = entry_top + buffer
            entry_price = entry_bottom
            risk = stop_loss - entry_price
            take_profit = entry_price - risk * 2

        risk_reward = abs(take_profit - entry_price) / abs(entry_price - stop_loss)

        setups.append({
            "direction": direction,
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "risk_reward": round(risk_reward, 2),
            "zone_type": zone_type,
            "zone_top": round(entry_top, 2),
            "zone_bottom": round(entry_bottom, 2),
            "sweep_time": matching_sweep["timestamp"],
            "choch_time": choch["timestamp"],
        })

    return setups


def get_active_setup(df: pd.DataFrame, current_price: float) -> dict | None:
    """
    З усіх знайдених сетапів повертає той, чия зона входу зараз
    найближча до поточної ціни (і ще не відпрацьована) - тобто
    актуальний сетап "прямо зараз".
    """
    setups = find_setups(df)
    if not setups:
        return None

    # беремо тільки найновіші сетапи (останні 20 свічок)
    recent = [s for s in setups if df.index.get_loc(s["choch_time"]) >= len(df) - 20]
    if not recent:
        return None

    # найближчий за ціною до поточної
    recent.sort(key=lambda s: abs(current_price - s["entry_price"]))
    return recent[0]
