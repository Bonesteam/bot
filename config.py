"""
Конфігурація бота.
Всі чутливі дані (ключі API) беруться з файлу .env, який НЕ потрапляє в git.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # завантажує змінні з файлу .env у поточній папці


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default))
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Binance API ---
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
    BINANCE_TESTNET = _get_bool("BINANCE_TESTNET", True)

    # --- Торгові параметри ---
    SYMBOL = os.getenv("SYMBOL", "BTC/USDT")  # використовується в run_backtest.py, find_setup.py тощо
    TIMEFRAME = os.getenv("TIMEFRAME", "1h")

    # Список пар для моніторингу (monitor.py перевіряє кожну по черзі).
    # Якщо WATCHLIST не задано в .env - моніторимо лише SYMBOL.
    _watchlist_raw = os.getenv("WATCHLIST", "")
    if _watchlist_raw.strip():
        WATCHLIST = [s.strip() for s in _watchlist_raw.split(",") if s.strip()]
    else:
        WATCHLIST = [SYMBOL]

    # --- Telegram (підключимо пізніше) ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Автоторгівля та ризик-менеджмент ---
    # За замовчуванням автоторгівля ВИМКНЕНА - бот тільки надсилає сигнали.
    # Потрібно свідомо увімкнути, навіть на testnet.
    AUTO_TRADE_ENABLED = _get_bool("AUTO_TRADE_ENABLED", False)

    # Скільки % балансу ризикувати на одну угоду (0.01 = 1%)
    RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.01"))

    # Плече для ф'ючерсів. Низьке плече = менший ризик ліквідації.
    LEVERAGE = int(os.getenv("LEVERAGE", "3"))

    # Захисні ліміти
    MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))

    # Додатковий запобіжник: щоб увімкнути автоторгівлю на РЕАЛЬНОМУ акаунті
    # (не testnet), потрібно ЯВНО встановити цей прапорець в .env.
    # Це навмисне тертя, щоб реальні гроші не могли увімкнутись випадково.
    LIVE_TRADING_CONFIRMED = _get_bool("LIVE_TRADING_CONFIRMED", False)

    @classmethod
    def validate(cls):
        """Перевіряє, що обов'язкові ключі задані, перш ніж бот почне працювати."""
        missing = []
        if not cls.BINANCE_API_KEY:
            missing.append("BINANCE_API_KEY")
        if not cls.BINANCE_API_SECRET:
            missing.append("BINANCE_API_SECRET")
        if missing:
            raise RuntimeError(
                f"Відсутні змінні у .env: {', '.join(missing)}. "
                f"Скопіюйте .env.example у .env та впишіть свої ключі testnet."
            )

        # Запобіжник: автоторгівля на реальному акаунті без явного підтвердження
        if cls.AUTO_TRADE_ENABLED and not cls.BINANCE_TESTNET and not cls.LIVE_TRADING_CONFIRMED:
            raise RuntimeError(
                "Ви намагаєтесь увімкнути автоторгівлю на РЕАЛЬНОМУ акаунті "
                "(BINANCE_TESTNET=false). Для захисту від випадкового запуску "
                "з реальними грошима потрібно додатково встановити "
                "LIVE_TRADING_CONFIRMED=true у .env. Переконайтесь, що ви "
                "усвідомлюєте ризики, перш ніж це робити."
            )
