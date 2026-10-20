"""
Interactive Console Menu for H3H SteamGridDB Harvester
"""

import sys
import os
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str((ROOT_DIR / "studio").resolve()))
sys.path.insert(0, str((ROOT_DIR / "scripts").resolve()))

from auto_harvest_pipeline import run_harvest_batch, CATALOG_PATH, LOG_PATH
from sync_drive_to_catalog import main as sync_catalog_only


def get_catalog_stats():
    total_games = 0
    total_variants = 0
    total_logged = 0
    last_updated = "Неизвестно"
    if CATALOG_PATH.exists():
        try:
            cat = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
            total_games = cat.get("totalGames", len(cat.get("games", [])))
            total_variants = cat.get("totalVariants", sum(len(g.get("variants", [])) for g in cat.get("games", [])))
            last_updated = cat.get("lastUpdated", "")[:19].replace("T", " ")
        except Exception:
            pass
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text(encoding='utf-8'))
            total_logged = len(log.get("items", {}))
        except Exception:
            pass
    return total_games, total_variants, total_logged, last_updated


def print_menu():
    g, v, l, upd = get_catalog_stats()
    print("\n" + "=" * 68)
    print("        H3H-Backgrounds: Автоматический сборщик видеофонов")
    print("          (SteamGridDB -> 4IFIR 720p -> Google Drive -> GitHub)")
    print("=" * 68)
    print(f"  📊 В КАТАЛОГЕ: {g} игр | {v} вариантов фонов | Проверено: {l}")
    if upd:
        print(f"  🕒 Последнее обновление: {upd} UTC")
    print("=" * 68)
    print()
    print("  [1] Скачать 1 пачку (50 игр), сконвертировать и залить на Drive/GitHub")
    print("  [2] Запустить непрерывный цикл (по 50 игр за цикл, до остановки)")
    print("  [3] Задать свой размер пачки (например, 20 или 100 игр)")
    print("  [4] Синхронизировать текущий catalog.json и harvest_log с GitHub")
    print("  [5] Показать список последних добавленных игр")
    print("  [6] Выход")
    print()


def show_recent_games():
    if not CATALOG_PATH.exists():
        print("Каталог не найден.")
        return

    try:
        cat = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
        games = cat.get("games", [])
        total_g = len(games)
        total_v = sum(len(g.get("variants", [])) for g in games)

        print("\n" + "=" * 68)
        print(f"  🎬 ПОЛНАЯ СТАТИСТИКА КАТАЛОГА:")
        print(f"  • Всего игр в каталоге: {total_g}")
        print(f"  • Всего вариантов видеофонов: {total_v}")
        print(f"  • Ссылка на GitHub: https://github.com/Holy3holy-dev/H3H-Backgrounds")
        print("=" * 68)
        print("  Последние добавленные игры (последние 20):\n")

        recent = games[-20:]
        for idx, g in enumerate(reversed(recent), 1):
            tid = g.get("titleId", "Unknown TID")
            title = g.get("title", "Без названия")
            v_count = len(g.get("variants", []))
            v_name = g.get("variants", [{}])[0].get("name", "")
            print(f"  {idx:2d}. [{tid}] {title[:36]:<36} ({v_name})")
        print("=" * 68)
    except Exception as e:
        print(f"[-] Ошибка чтения каталога: {e}")


def main():
    while True:
        try:
            print_menu()
            choice = input("Выберите действие [1-6]: ").strip()

            if choice == "1":
                print("\n[*] Запуск сбора 1 пачки из 50 игр...")
                run_harvest_batch(batch_size=50, continuous=False)
                input("\nПачка завершена. Нажмите Enter для возврата в меню...")

            elif choice == "2":
                print("\n[*] Запуск непрерывного цикла сбора (по 50 игр за раз)...")
                print("Для остановки нажмите Ctrl + C в любой момент.\n")
                try:
                    run_harvest_batch(batch_size=50, continuous=True)
                except KeyboardInterrupt:
                    print("\n[!] Непрерывный цикл остановлен пользователем.")
                input("\nНажмите Enter для возврата в меню...")

            elif choice == "3":
                custom_str = input("\nВведите количество игр в пачке: ").strip()
                try:
                    custom_count = int(custom_str)
                    if custom_count <= 0:
                        custom_count = 50
                except ValueError:
                    custom_count = 50
                print(f"\n[*] Запуск сбора {custom_count} игр...")
                run_harvest_batch(batch_size=custom_count, continuous=False)
                input(f"\nСбор {custom_count} игр завершен. Нажмите Enter для возврата в меню...")

            elif choice == "4":
                print("\n[*] Синхронизация каталога и лога с GitHub...")
                sync_catalog_only()
                input("\nСинхронизация завершена. Нажмите Enter для возврата в меню...")

            elif choice == "5":
                show_recent_games()
                input("\nНажмите Enter для возврата в меню...")

            elif choice == "6" or choice.lower() in ("exit", "quit", "q"):
                print("\nДо свидания!")
                break
            else:
                print("\n[!] Неверный выбор. Пожалуйста, введите цифру от 1 до 6.")

        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            break
        except Exception as e:
            print(f"\n[!] Произошла непредвиденная ошибка: {e}")
            try:
                input("Нажмите Enter для продолжения...")
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    main()
