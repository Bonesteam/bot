"""
Відправка сповіщень про SMC-сетапи в Telegram.

Щоб це запрацювало, потрібно:
1. Створити бота через @BotFather в Telegram -> отримати TELEGRAM_BOT_TOKEN
2. Дізнатись свій chat_id -> отримати TELEGRAM_CHAT_ID
3. Вписати обидва значення у файл .env

Детальна інструкція - в README.md.
"""
import requests

from config import Config

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(text: str) -> bool:
    """
    Надсилає текстове повідомлення в Telegram.
    Повертає True при успіху, False при помилці (і друкує причину в консоль).
    """
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        print("⚠️  TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID не задані у .env — сповіщення пропущено.")
        return False

    url = TELEGRAM_API_URL.format(token=Config.TELEGRAM_BOT_TOKEN)

    try:
        response = requests.post(url, json={
            "chat_id": Config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
        }, timeout=10)
        if response.ok:
            return True

        # Запобіжник: якщо текст випадково містить символи, які Telegram
        # сприймає за невалідний HTML-тег (напр. "<" чи ">" з тексту помилки
        # біржі) - пробуємо надіслати ще раз як звичайний текст, без HTML.
        if "can't parse entities" in response.text:
            print("⚠️  Проблема з HTML-розміткою повідомлення, надсилаю як звичайний текст...")
            response = requests.post(url, json={
                "chat_id": Config.TELEGRAM_CHAT_ID, "text": text,
            }, timeout=10)
            if response.ok:
                return True

        print(f"⚠️  Telegram API повернув помилку: {response.status_code} {response.text}")
        return False
    except requests.RequestException as e:
        print(f"⚠️  Не вдалось надіслати повідомлення в Telegram: {e}")
        return False


def format_setup_message(setup: dict, symbol: str, timeframe: str) -> str:
    """Формує текст повідомлення про знайдений сетап у зручному для читання вигляді."""
    emoji = "🟢" if setup["direction"] == "LONG" else "🔴"

    return (
        f"{emoji} <b>Новий SMC-сетап: {setup['direction']}</b>\n"
        f"Пара: {symbol} ({timeframe})\n\n"
        f"Зона входу ({setup['zone_type']}): {setup['zone_bottom']} — {setup['zone_top']}\n"
        f"<b>Entry:</b> {setup['entry_price']}\n"
        f"<b>Stop Loss:</b> {setup['stop_loss']}\n"
        f"<b>Take Profit:</b> {setup['take_profit']}\n"
        f"<b>Risk:Reward</b> = 1:{setup['risk_reward']}\n\n"
        f"Sweep: {setup['sweep_time']}\n"
        f"CHoCH: {setup['choch_time']}\n\n"
        f"⚠️ Це сигнал для розгляду, не автоматична угода."
    )
