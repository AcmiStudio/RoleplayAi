"""
debug_main.py – Запуск main.py с принудительным выводом ошибок
"""
import sys
import traceback
import os

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("="*60)
print("DEBUG ЗАПУСК".center(60))
print("="*60)

# 1. Проверим наличие всех файлов
required_files = [
    "main.py", "server.py", "client.py", "config.py", "utils.py",
    "data/settings.json"
]
print("\nПроверка файлов:")
for f in required_files:
    exists = os.path.exists(f)
    print(f"  {'✓' if exists else '✗'} {f}")
    if not exists and f == "data/settings.json":
        print("    Создаю директорию и файл настроек...")
        os.makedirs("data", exist_ok=True)
        import json
        default = {
            "ollama": {"model": "gemma4:31b-cloud", "temperature": 0.7, "narrator_prompt": "You are a creative RPG narrator..."},
            "player_character": "",
            "player_color": "WHITE",
            "network": {"host": "localhost", "port": 8765}
        }
        with open(f, 'w', encoding='utf-8') as ff:
            json.dump(default, ff, indent=2)
        print("    settings.json создан автоматически")

# 2. Проверка модулей Python
print("\nПроверка импортов:")
modules_to_check = [
    "json", "asyncio", "os", "sys", "pathlib", "platform",
    "colorama", "websockets", "aiohttp", "config", "utils", "main"
]
for mod_name in modules_to_check:
    try:
        __import__(mod_name)
        print(f"  ✓ {mod_name}")
    except ImportError as e:
        print(f"  ✗ {mod_name}: {e}")
        if mod_name in ["colorama", "websockets", "aiohttp"]:
            print(f"    Установите: pip install {mod_name}")

print("\nПопытка запуска main.py...\n")
try:
    from main import MainMenu
    menu = MainMenu()
    menu.run()
except KeyboardInterrupt:
    print("\nПрограмма остановлена пользователем")
except Exception as e:
    print("\n" + "="*60)
    print("КРИТИЧЕСКАЯ ОШИБКА".center(60))
    print("="*60)
    traceback.print_exc()
    # Сохраняем в файл
    with open("error_log.txt", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    print("\nОшибка также записана в error_log.txt")
    input("Нажмите Enter для выхода...")