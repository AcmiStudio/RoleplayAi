"""
main.py - Главное меню с редактором персонажей/миров и выбором цвета
"""
import sys
import os
import asyncio
import traceback
from colorama import Fore, Style
from config import Config
from utils import ConsoleUI

class MainMenu:
    def __init__(self):
        self.config = Config()
        self.ui = ConsoleUI()
        # Словарь доступных цветов для игрока
        self.colors = {
            "WHITE": Fore.WHITE,
            "CYAN": Fore.CYAN,
            "YELLOW": Fore.YELLOW,
            "GREEN": Fore.GREEN,
            "MAGENTA": Fore.MAGENTA,
            "RED": Fore.RED,
            "BLUE": Fore.BLUE
        }

    def run(self):
        while True:
            try:
                self.ui.clear_screen()
                self.ui.print_header("СЕТЕВАЯ ТЕКСТОВАЯ RPG С ИИ-РАССКАЗЧИКОМ")
                self.ui.print_menu([
                    "Создать комнату (стать администратором)",
                    "Подключиться к комнате (стать игроком)",
                    "Настройки",
                    "Управление персонажами",
                    "Управление мирами",
                    "Выход"
                ])
                choice = self.ui.get_input("Выберите действие")
                if choice == "1":
                    self.create_room()
                elif choice == "2":
                    self.join_room()
                elif choice == "3":
                    self.settings_menu()
                elif choice == "4":
                    self.character_manager()
                elif choice == "5":
                    self.world_manager()
                elif choice == "6":
                    self.ui.print_info("До новых приключений!")
                    sys.exit(0)
                else:
                    self.ui.print_error("Неверный выбор.")
                    input("Нажмите Enter...")
            except KeyboardInterrupt:
                print("\nВыход из программы...")
                sys.exit(0)
            except Exception as e:
                self.ui.print_error(f"Ошибка: {e}")
                traceback.print_exc()
                input("Нажмите Enter...")

    # =========================================================
    # СОЗДАНИЕ КОМНАТЫ
    # =========================================================
    def create_room(self):
        try:
            from server import RPGGameServer
            server = RPGGameServer()
            self.ui.clear_screen()
            self.ui.print_header("СОЗДАНИЕ КОМНАТЫ")

            room_name = self.ui.get_input("Название комнаты")
            while True:
                try:
                    max_players = int(self.ui.get_input("Максимум игроков (2-4)"))
                    if 2 <= max_players <= 4:
                        break
                    self.ui.print_error("Число от 2 до 4")
                except ValueError:
                    self.ui.print_error("Введите число")

            mode_choice = self.ui.get_input("Режим (1 - свободный, 2 - поочерёдный)")
            turn_mode = "free" if mode_choice == "1" else "turn"

            # Выбор мира
            world_description = self.select_or_create_world()

            asyncio.run(server.start_server(
                host="0.0.0.0", port=8765,
                room_name=room_name, max_players=max_players,
                turn_mode=turn_mode, world_description=world_description
            ))
        except Exception as e:
            self.ui.print_error(f"Ошибка: {e}")
            traceback.print_exc()
        input("Нажмите Enter для возврата...")

    # =========================================================
    # ПОДКЛЮЧЕНИЕ К КОМНАТЕ
    # =========================================================
    def join_room(self):
        try:
            from client import RPGGameClient
            client = RPGGameClient()

            if not self.config.settings.get("player_character"):
                self.ui.print_warning("Персонаж не выбран!")
                self.select_character()

            player_name = self.ui.get_input("Имя вашего персонажа")
            server_address = self.ui.get_input("Адрес сервера (ws://localhost:8765)")

            asyncio.run(client.join_room(
                player_name=player_name,
                server_address=server_address,
                character_desc=self.config.settings["player_character"],
                player_color=self.config.settings.get("player_color", "WHITE")
            ))
        except Exception as e:
            self.ui.print_error(f"Ошибка подключения: {e}")
        input("Нажмите Enter для возврата...")

    # =========================================================
    # НАСТРОЙКИ
    # =========================================================
    def settings_menu(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("НАСТРОЙКИ")
            self.ui.print_menu([
                "Настройки модели Ollama",
                "Выбрать персонажа",
                "Выбрать цвет игрока",
                "Назад"
            ])
            choice = self.ui.get_input("Выберите")
            if choice == "1":
                self.ollama_settings()
            elif choice == "2":
                self.select_character()
            elif choice == "3":
                self.select_player_color()
            elif choice == "4":
                break
            else:
                self.ui.print_error("Неверный выбор")

    def ollama_settings(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("НАСТРОЙКИ OLLAMA")
            cur = self.config.settings["ollama"]
            self.ui.print_info(f"Модель: {cur['model']}, Температура: {cur['temperature']}")
            self.ui.print_menu([
                "Выбрать модель",
                "Изменить температуру",
                "Загрузить промпт рассказчика",
                "Назад"
            ])
            ch = self.ui.get_input(">")
            if ch == "1":
                model = self.ui.get_input("Название модели")
                if model:
                    self.config.update_ollama_settings(model=model)
                    self.ui.print_success("Модель обновлена!")
            elif ch == "2":
                temp = self.ui.get_input("Температура (0.0-1.0)")
                try:
                    temp = float(temp)
                    if 0 <= temp <= 1:
                        self.config.update_ollama_settings(temperature=temp)
                        self.ui.print_success("Температура обновлена!")
                    else:
                        self.ui.print_error("Диапазон 0-1")
                except ValueError:
                    self.ui.print_error("Число!")
            elif ch == "3":
                path = self.ui.get_input("Путь к файлу промпта (Enter - ручной ввод)")
                if path == "":
                    prompt = self.ui.get_multiline_input("Введите промпт (пустая строка — конец):")
                    if prompt:
                        self.config.update_ollama_settings(prompt=prompt)
                        self.ui.print_success("Промпт обновлён!")
                else:
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            prompt = f.read()
                        self.config.update_ollama_settings(prompt=prompt)
                        self.ui.print_success("Промпт загружен!")
                    except FileNotFoundError:
                        self.ui.print_error("Файл не найден")
            elif ch == "4":
                break
            input("Нажмите Enter...")

    # =========================================================
    # ВЫБОР ЦВЕТА ИГРОКА
    # =========================================================
    def select_player_color(self):
        self.ui.clear_screen()
        self.ui.print_header("ВЫБОР ЦВЕТА ИГРОКА")
        color_names = list(self.colors.keys())
        for i, name in enumerate(color_names, 1):
            # Показываем цветом
            self.ui.print_colored(f"{i}. {name}", self.colors[name])
        try:
            idx = int(self.ui.get_input("Номер цвета")) - 1
            if 0 <= idx < len(color_names):
                chosen = color_names[idx]
                self.config.settings["player_color"] = chosen
                self.config.save_settings()
                self.ui.print_success(f"Цвет '{chosen}' выбран!")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")
        input("Нажмите Enter...")

    # =========================================================
    # УПРАВЛЕНИЕ ПЕРСОНАЖАМИ
    # =========================================================
    def character_manager(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("УПРАВЛЕНИЕ ПЕРСОНАЖАМИ")
            chars = self.config.list_characters()
            if chars:
                for i, name in enumerate(chars, 1):
                    self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
            else:
                self.ui.print_info("Нет сохранённых персонажей")
            self.ui.print_menu([
                "Создать персонажа",
                "Редактировать персонажа",
                "Удалить персонажа",
                "Выбрать персонажа для игры",
                "Назад"
            ], title="Действия")
            choice = self.ui.get_input(">")
            if choice == "1":
                self.create_character()
            elif choice == "2":
                self.edit_character()
            elif choice == "3":
                self.delete_character()
            elif choice == "4":
                self.select_character()
            elif choice == "5":
                break
            else:
                self.ui.print_error("Неверный выбор")
            if choice != "5":
                input("Нажмите Enter...")

    def create_character(self):
        self.ui.clear_screen()
        self.ui.print_header("СОЗДАНИЕ ПЕРСОНАЖА")
        name = self.ui.get_input("Имя файла персонажа (без расширения)")
        if not name:
            return
        if name in self.config.list_characters():
            overwrite = self.ui.get_input("Персонаж уже существует. Перезаписать? (y/n)")
            if overwrite.lower() != 'y':
                return
        content = self.ui.get_multiline_input("Введите описание персонажа (пустая строка — конец):")
        if content:
            self.config.save_character(name, content)
            self.ui.print_success(f"Персонаж '{name}' сохранён!")

    def edit_character(self):
        self.ui.clear_screen()
        self.ui.print_header("РЕДАКТИРОВАНИЕ ПЕРСОНАЖА")
        chars = self.config.list_characters()
        if not chars:
            self.ui.print_info("Нет персонажей для редактирования")
            return
        for i, name in enumerate(chars, 1):
            self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
        try:
            idx = int(self.ui.get_input("Номер персонажа")) - 1
            if 0 <= idx < len(chars):
                name = chars[idx]
                content = self.config.load_character(name)
                self.ui.print_colored("Текущее описание:", Fore.BLUE)
                print(content)
                self.ui.print_warning("Введите новый текст (пустая строка — конец, оставить пустым для отмены):")
                new_content = self.ui.get_multiline_input("")
                if new_content.strip() != "":
                    self.config.save_character(name, new_content)
                    self.ui.print_success(f"Персонаж '{name}' обновлён!")
                else:
                    self.ui.print_info("Отменено")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")

    def delete_character(self):
        self.ui.clear_screen()
        self.ui.print_header("УДАЛЕНИЕ ПЕРСОНАЖА")
        chars = self.config.list_characters()
        if not chars:
            self.ui.print_info("Нет персонажей")
            return
        for i, name in enumerate(chars, 1):
            self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
        try:
            idx = int(self.ui.get_input("Номер для удаления")) - 1
            if 0 <= idx < len(chars):
                name = chars[idx]
                confirm = self.ui.get_input(f"Удалить '{name}'? (y/n)")
                if confirm.lower() == 'y':
                    self.config.delete_character(name)
                    self.ui.print_success(f"'{name}' удалён")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")

    def select_character(self):
        """Выбор персонажа для игры"""
        self.ui.clear_screen()
        self.ui.print_header("ВЫБОР ПЕРСОНАЖА")
        chars = self.config.list_characters()
        if chars:
            for i, name in enumerate(chars, 1):
                self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
            self.ui.print_info("0. Ввести описание вручную")
            try:
                idx = int(self.ui.get_input("Номер персонажа (0 - ручной ввод)"))
                if idx == 0:
                    manual = self.ui.get_multiline_input("Введите описание персонажа (пустая строка — конец):")
                    if manual:
                        self.config.settings["player_character"] = manual
                        self.config.save_settings()
                        self.ui.print_success("Персонаж установлен (без сохранения в файл)")
                elif 1 <= idx <= len(chars):
                    name = chars[idx-1]
                    content = self.config.load_character(name)
                    self.config.settings["player_character"] = content
                    self.config.save_settings()
                    self.ui.print_success(f"Выбран персонаж '{name}'")
                else:
                    self.ui.print_error("Неверный номер")
            except ValueError:
                self.ui.print_error("Введите число")
        else:
            self.ui.print_info("Сохранённых персонажей нет")
            manual = self.ui.get_multiline_input("Введите описание персонажа (пустая строка — конец):")
            if manual:
                self.config.settings["player_character"] = manual
                self.config.save_settings()
                self.ui.print_success("Персонаж установлен")
        input("Нажмите Enter...")

    # =========================================================
    # УПРАВЛЕНИЕ МИРАМИ
    # =========================================================
    def world_manager(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("УПРАВЛЕНИЕ МИРАМИ")
            worlds = self.config.list_worlds()
            if worlds:
                for i, name in enumerate(worlds, 1):
                    self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
            else:
                self.ui.print_info("Нет сохранённых миров")
            self.ui.print_menu([
                "Создать мир",
                "Редактировать мир",
                "Удалить мир",
                "Назад"
            ])
            choice = self.ui.get_input(">")
            if choice == "1":
                self.create_world()
            elif choice == "2":
                self.edit_world()
            elif choice == "3":
                self.delete_world()
            elif choice == "4":
                break
            else:
                self.ui.print_error("Неверный выбор")
            if choice != "4":
                input("Нажмите Enter...")

    def create_world(self):
        self.ui.clear_screen()
        self.ui.print_header("СОЗДАНИЕ МИРА")
        name = self.ui.get_input("Название файла мира (без расширения)")
        if not name:
            return
        if name in self.config.list_worlds():
            ow = self.ui.get_input("Мир уже существует. Перезаписать? (y/n)")
            if ow.lower() != 'y':
                return
        content = self.ui.get_multiline_input("Введите описание мира (пустая строка — конец):")
        if content:
            self.config.save_world(name, content)
            self.ui.print_success(f"Мир '{name}' сохранён!")

    def edit_world(self):
        self.ui.clear_screen()
        self.ui.print_header("РЕДАКТИРОВАНИЕ МИРА")
        worlds = self.config.list_worlds()
        if not worlds:
            self.ui.print_info("Нет миров")
            return
        for i, name in enumerate(worlds, 1):
            self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
        try:
            idx = int(self.ui.get_input("Номер мира")) - 1
            if 0 <= idx < len(worlds):
                name = worlds[idx]
                content = self.config.load_world(name)
                self.ui.print_colored("Текущее описание:", Fore.BLUE)
                print(content)
                self.ui.print_warning("Новый текст (пустая строка — конец, пусто — отмена):")
                new_content = self.ui.get_multiline_input("")
                if new_content.strip():
                    self.config.save_world(name, new_content)
                    self.ui.print_success(f"Мир '{name}' обновлён!")
                else:
                    self.ui.print_info("Отменено")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")

    def delete_world(self):
        self.ui.clear_screen()
        self.ui.print_header("УДАЛЕНИЕ МИРА")
        worlds = self.config.list_worlds()
        if not worlds:
            self.ui.print_info("Нет миров")
            return
        for i, name in enumerate(worlds, 1):
            self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
        try:
            idx = int(self.ui.get_input("Номер для удаления")) - 1
            if 0 <= idx < len(worlds):
                name = worlds[idx]
                if self.ui.get_input(f"Удалить '{name}'? (y/n)").lower() == 'y':
                    self.config.delete_world(name)
                    self.ui.print_success(f"Мир '{name}' удалён")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")

    def select_or_create_world(self):
        """Используется при создании комнаты: предлагает выбрать мир, создать новый или ввести вручную"""
        self.ui.clear_screen()
        self.ui.print_header("ВЫБОР МИРА")
        worlds = self.config.list_worlds()
        if worlds:
            for i, name in enumerate(worlds, 1):
                self.ui.print_colored(f"{i}. {name}", Fore.CYAN)
            self.ui.print_info("0. Ввести описание вручную")
            self.ui.print_info("-1. Создать новый мир")
            try:
                choice = int(self.ui.get_input("Номер мира"))
                if choice == -1:
                    self.create_world()
                    # После создания возвращаемся к выбору (можно рекурсивно, но для простоты просто попросим выбрать снова)
                    return self.select_or_create_world()
                elif choice == 0:
                    return self.ui.get_multiline_input("Введите описание мира (пустая строка — конец):")
                elif 1 <= choice <= len(worlds):
                    name = worlds[choice-1]
                    return self.config.load_world(name)
                else:
                    self.ui.print_error("Неверный номер, введите вручную")
                    return self.ui.get_multiline_input("Описание мира:")
            except ValueError:
                self.ui.print_error("Введите число, будет ручной ввод")
                return self.ui.get_multiline_input("Описание мира:")
        else:
            self.ui.print_info("Нет сохранённых миров")
            sub = self.ui.get_input("1 - создать новый мир, 2 - ввести описание вручную")
            if sub == "1":
                self.create_world()
                return self.select_or_create_world()
            else:
                return self.ui.get_multiline_input("Введите описание мира (пустая строка — конец):")

if __name__ == "__main__":
    try:
        menu = MainMenu()
        menu.run()
    except KeyboardInterrupt:
        print("\nВыход из программы...")
        sys.exit(0)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
        input("Нажмите Enter для выхода...")