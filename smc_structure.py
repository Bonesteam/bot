"""
Визначення структури ринку для Smart Money Concept (SMC).

Що робить цей модуль:
1. Знаходить swing high / swing low точки на графіку (локальні екстремуми)
2. На основі свінгів визначає:
   - BOS (Break of Structure) — пробиття попереднього свінгу ЗА трендом
     (підтверджує продовження тренду)
   - CHoCH (Change of Character) — пробиття свінгу ПРОТИ тренду
     (перший сигнал можливого розвороту)

ВАЖЛИВО: це спрощена, але робоча реалізація класичної SMC-логіки.
Досвідчені трейдери додають контекст старшого таймфрейму, обʼєми,
зони ліквідності тощо. Тут — базовий, тестований "скелет", який можна
покроково вдосконалювати після бектесту.
"""
import pandas as pd


def find_swings(df: pd.DataFrame, window: int = 3) -> pd.DataFrame:
    """
    Позначає swing high / swing low точки.

    Swing high — свічка, high якої вищий за high всіх свічок
    у радіусі `window` зліва і справа (локальний максимум).
    Swing low — аналогічно, локальний мінімум.

    window=3 означає, що дивимось по 3 свічки в кожен бік.
    Більше window -> менше свінгів, але вони "значиміші".
    """
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"] = False

    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    for i in range(window, n - window):
        window_highs = highs[i - window: i + window + 1]
        window_lows = lows[i - window: i + window + 1]

        if highs[i] == window_highs.max():
            df.iloc[i, df.columns.get_loc("swing_high")] = True

        if lows[i] == window_lows.min():
            df.iloc[i, df.columns.get_loc("swing_low")] = True

    return df


def detect_structure_events(df: pd.DataFrame) -> list[dict]:
    """
    Проходить по свічках і визначає події BOS / CHoCH.

    Логіка:
    - Тримаємо "останній непробитий swing high" і "останній непробитий swing low"
    - Якщо close пробиває swing high вгору:
        - якщо був низхідний тренд -> це CHoCH (bullish) — можливий розворот
        - якщо був висхідний тренд -> це BOS (bullish) — продовження тренду
    - Дзеркально для пробиття swing low вниз

    Повертає список подій:
    {"timestamp", "type": "BOS"/"CHoCH", "direction": "bullish"/"bearish", "price"}
    """
    if "swing_high" not in df.columns or "swing_low" not in df.columns:
        df = find_swings(df)

    events = []
    trend = None  # None -> ще не визначено, "up" або "down"
    last_high = None  # {"price": ..., "broken": bool}
    last_low = None

    for idx, row in df.iterrows():
        close = row["close"]

        # --- перевірка пробиття зверху (bullish) ---
        if last_high is not None and not last_high["broken"] and close > last_high["price"]:
            if trend == "down":
                events.append({
                    "timestamp": idx, "type": "CHoCH", "direction": "bullish",
                    "price": close, "broken_level": last_high["price"],
                })
                trend = "up"
            elif trend == "up":
                events.append({
                    "timestamp": idx, "type": "BOS", "direction": "bullish",
                    "price": close, "broken_level": last_high["price"],
                })
            else:
                trend = "up"
            last_high["broken"] = True

        # --- перевірка пробиття знизу (bearish) ---
        if last_low is not None and not last_low["broken"] and close < last_low["price"]:
            if trend == "up":
                events.append({
                    "timestamp": idx, "type": "CHoCH", "direction": "bearish",
                    "price": close, "broken_level": last_low["price"],
                })
                trend = "down"
            elif trend == "down":
                events.append({
                    "timestamp": idx, "type": "BOS", "direction": "bearish",
                    "price": close, "broken_level": last_low["price"],
                })
            else:
                trend = "down"
            last_low["broken"] = True

        # --- оновлюємо останній непробитий свінг ---
        if row["swing_high"]:
            last_high = {"price": row["high"], "broken": False}
        if row["swing_low"]:
            last_low = {"price": row["low"], "broken": False}

    return events


def get_current_trend(events: list[dict]) -> str | None:
    """Повертає поточний тренд ('up'/'down') на основі останньої BOS/CHoCH події."""
    if not events:
        return None
    last_event = events[-1]
    return "up" if last_event["direction"] == "bullish" else "down"
