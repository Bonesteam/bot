"""
Ризик-менеджмент: захисні ліміти, які зупиняють бота, якщо щось пішло не так.

Без цього автоторгівля - це не автоторгівля, а спосіб швидко злити депозит
через баг, аномалію ринку чи серію збиткових угод підряд.

Ліміти:
- MAX_TRADES_PER_DAY - не більше N угод на день (захист від "овертрейдингу")
- MAX_DAILY_LOSS_PCT - якщо денний збиток перевищив X% балансу - бот
  зупиняє відкриття нових угод до наступного дня
"""
import json
import os
from datetime import datetime, timezone

from config import Config

STATE_FILE = "risk_state.json"


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


class RiskManager:
    def __init__(self):
        self.state = _load_state()
        self._reset_if_new_day()

    def _reset_if_new_day(self):
        """Якщо настав новий день - скидаємо лічильники."""
        today = _today_str()
        if self.state.get("date") != today:
            self.state = {
                "date": today,
                "trades_opened": 0,
                "starting_balance": None,  # заповниться при першій перевірці
            }
            _save_state(self.state)

    def can_open_trade(self, current_balance: float) -> tuple[bool, str]:
        """
        Перевіряє, чи можна відкрити нову угоду прямо зараз.
        Повертає (можна_чи_ні, причина_якщо_ні).
        """
        self._reset_if_new_day()

        # фіксуємо баланс на початок дня при першій перевірці
        if self.state["starting_balance"] is None:
            self.state["starting_balance"] = current_balance
            _save_state(self.state)

        if self.state["trades_opened"] >= Config.MAX_TRADES_PER_DAY:
            return False, (
                f"Досягнуто денний ліміт угод ({Config.MAX_TRADES_PER_DAY}). "
                f"Нові угоди - завтра."
            )

        starting_balance = self.state["starting_balance"]
        if starting_balance > 0:
            daily_pnl_pct = (current_balance - starting_balance) / starting_balance * 100
            if daily_pnl_pct <= -Config.MAX_DAILY_LOSS_PCT:
                return False, (
                    f"Досягнуто денний ліміт збитку ({daily_pnl_pct:.2f}% ≤ "
                    f"-{Config.MAX_DAILY_LOSS_PCT}%). Бот зупинено до завтра."
                )

        return True, ""

    def record_trade_opened(self):
        """Викликається одразу після успішного відкриття угоди."""
        self._reset_if_new_day()
        self.state["trades_opened"] += 1
        _save_state(self.state)
