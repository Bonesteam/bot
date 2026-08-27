"""
Розрахунок розміру позиції та відкриття угод на Binance Futures з SL/TP.

Позиція розраховується так, щоб при спрацюванні Stop Loss втрата
дорівнювала рівно RISK_PER_TRADE_PCT від балансу - незалежно від того,
наскільки далеко стоїть SL. Це і є суть risk-менеджменту: ризик
контролюється розміром позиції, а не "відчуттям".
"""
import ccxt

from config import Config


def calculate_position_size(balance_usdt: float, entry_price: float,
                             stop_loss: float, risk_pct: float = None) -> dict:
    """
    Рахує, скільки монети купити/продати, щоб втрата на SL = risk_pct від балансу.

    Повертає:
      quantity - кількість базового активу (напр. BTC)
      notional - розмір позиції в USDT (quantity * entry_price)
      required_margin - скільки маржі потрібно з урахуванням плеча
      risk_amount - скільки USDT втратимо, якщо спрацює SL
      sufficient_margin - чи вистачає балансу на таку позицію
    """
    risk_pct = risk_pct if risk_pct is not None else Config.RISK_PER_TRADE_PCT

    risk_amount = balance_usdt * risk_pct
    price_risk = abs(entry_price - stop_loss)

    if price_risk == 0:
        raise ValueError("entry_price і stop_loss однакові - неможливо розрахувати розмір позиції")

    quantity = risk_amount / price_risk
    notional = quantity * entry_price
    required_margin = notional / Config.LEVERAGE

    # Якщо SL дуже вузький відносно ціни, потрібна позиція (і маржа) може
    # вийти надто великою для балансу навіть при заданому ризику в %.
    # Використовуємо максимум 90% доступного балансу як маржу - запобіжник.
    max_allowed_margin = balance_usdt * 0.9
    sufficient_margin = required_margin <= max_allowed_margin

    return {
        "quantity": quantity,
        "notional": notional,
        "required_margin": required_margin,
        "risk_amount": risk_amount,
        "sufficient_margin": sufficient_margin,
    }


def open_position_with_sl_tp(exchange: ccxt.binance, symbol: str, direction: str,
                              quantity: float, stop_loss: float, take_profit: float) -> dict:
    """
    Відкриває позицію ринковим ордером і одразу ставить SL та TP
    (reduceOnly-ордери, які автоматично закриють позицію).

    direction: "LONG" або "SHORT"
    """
    side = "buy" if direction == "LONG" else "sell"
    opposite_side = "sell" if direction == "LONG" else "buy"

    # округлюємо кількість до точності, яку вимагає біржа для цієї пари
    qty_precise = exchange.amount_to_precision(symbol, quantity)
    sl_precise = exchange.price_to_precision(symbol, stop_loss)
    tp_precise = exchange.price_to_precision(symbol, take_profit)

    # 1. Вхід ринковим ордером
    entry_order = exchange.create_order(symbol, "market", side, qty_precise)

    # 2. Stop Loss (закриє позицію автоматично, якщо ціна дійде до SL)
    sl_order = exchange.create_order(
        symbol, "STOP_MARKET", opposite_side, qty_precise, None,
        {"stopPrice": sl_precise, "reduceOnly": True},
    )

    # 3. Take Profit
    tp_order = exchange.create_order(
        symbol, "TAKE_PROFIT_MARKET", opposite_side, qty_precise, None,
        {"stopPrice": tp_precise, "reduceOnly": True},
    )

    return {
        "entry_order": entry_order,
        "sl_order": sl_order,
        "tp_order": tp_order,
        "quantity": qty_precise,
    }


def set_leverage(exchange: ccxt.binance, symbol: str, leverage: int = None):
    """Встановлює плече для пари перед відкриттям позиції."""
    leverage = leverage or Config.LEVERAGE
    exchange.set_leverage(leverage, symbol)
