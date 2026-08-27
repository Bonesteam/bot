"""
Одноразовий скрипт-міграція: довантажує в трекер (signal_tracker) ті
сигнали, які вже були надіслані в Telegram ДО того, як зʼявився трекер
результатів. Такі сигнали "застрягли" в notified_setups.json (вже
відправлені), але не потрапили в signals_log.json (для трекінгу).

Запуск (один раз, після цього можна видалити):
    python backfill_tracker.py

Що робить:
1. Читає notified_setups.json - список "symbol:choch_time" вже надісланих
2. Для кожної монети перезапускає пошук сетапів (find_setups) на поточних
   даних, щоб знайти той самий сетап за choch_time і відновити його
   entry/SL/TP
3. Логує знайдені сетапи в signals_log.json зі статусом pending -
   з цього моменту вони почнуть трекатись як звичайні сигнали

Обмеження: якщо потрібна історія свічок вже "виїхала" за межі
завантажуваного вікна (300 свічок), відновити сетап не вдасться -
скрипт про це попередить.
"""
import json
import os

import pandas as pd

from config import Config
from binance_client import get_exchange, fetch_candles
from smc_setup import find_setups
from signal_tracker import load_signals, log_new_signal

NOTIFIED_FILE = "notified_setups.json"


def main():
    if not os.path.exists(NOTIFIED_FILE):
        print("Файл notified_setups.json не знайдено - нічого відновлювати.")
        return

    with open(NOTIFIED_FILE, "r") as f:
        notified_keys = json.load(f)

    # групуємо ключі за монетою: "BTC/USDT:2026-08-24 11:00:00" -> symbol, choch_time
    by_symbol = {}
    for key in notified_keys:
        symbol, choch_time = key.split(":", 1)  # перша двокрапка - бо час має свої (11:00:00)
        by_symbol.setdefault(symbol, []).append(choch_time)

    already_logged = {f"{s['symbol']}:{s['choch_time']}" for s in load_signals()}

    Config.validate()
    exchange = get_exchange()

    recovered = 0
    not_found = 0

    for symbol, choch_times in by_symbol.items():
        print(f"Перевіряю {symbol}...")
        try:
            df = fetch_candles(exchange, symbol=symbol, limit=300)
        except Exception as e:
            print(f"  ⚠️  Не вдалось завантажити свічки: {e}")
            continue

        setups = find_setups(df)
        setups_by_choch = {str(s["choch_time"]): s for s in setups}

        for choch_time in choch_times:
            full_key = f"{symbol}:{choch_time}"
            if full_key in already_logged:
                continue  # вже залоговано раніше

            setup = setups_by_choch.get(choch_time)
            if setup is None:
                print(f"  ⚠️  Сетап на {choch_time} вже поза межами доступної історії - пропускаю")
                not_found += 1
                continue

            log_new_signal(symbol, setup)
            print(f"  ✅ Відновлено: {setup['direction']} @ {choch_time}")
            recovered += 1

    print(f"\n=== Готово: відновлено {recovered}, не знайдено {not_found} ===")
    print("Перевірте результат: python check_stats.py")


if __name__ == "__main__":
    main()
