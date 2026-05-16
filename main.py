"""
main.py – Главное меню с друзьями, отладкой, онлайн-игрой и всеми настройками
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
        self.colors = {
            "WHITE": Fore.WHITE, "CYAN": Fore.CYAN, "YELLOW": Fore.YELLOW,
            "GREEN": Fore.GREEN, "MAGENTA": Fore.MAGENTA, "RED": Fore.RED, "BLUE": Fore.BLUE
        }

    def run(self):
        while True:
            try:
                self.ui.clear_screen()
                self.ui.print_header("СЕТЕВАЯ ТЕКСТОВАЯ RPG С ИИ-РАССКАЗЧИКОМ")
                menu_items = [
                    "Создать комнату (стать администратором)",
                    "Подключиться к комнате (стать игроком)",
                    "Найти локальные сервера",
                    "Онлайн игра",
                    "Настройки",
                    "Управление персонажами",
                    "Управление мирами",
                    "Друзья"
                ]
                if self.config.get_dev_password():
                    menu_items.append("Отладка (режим разработчика)")
                menu_items.append("Выход")
                self.ui.print_menu(menu_items)
                choice = self.ui.get_input("Выберите действие")
                if choice == "1":
                    self.create_room()
                elif choice == "2":
                    self.join_room()
                elif choice == "3":
                    self.find_servers()
                elif choice == "4":
                    self.online_menu()
                elif choice == "5":
                    self.settings_menu()
                elif choice == "6":
                    self.character_manager()
                elif choice == "7":
                    self.world_manager()
                elif choice == "8":
                    self.friends_menu()
                elif choice == "9" and self.config.get_dev_password():
                    self.debug_menu()
                elif choice == str(len(menu_items)):
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

    # ------------------------------------------------------------
    # МЕНЮ ОТЛАДКИ
    # ------------------------------------------------------------
    def debug_menu(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("РЕЖИМ РАЗРАБОТЧИКА")
            self.ui.print_menu([
                "Показать текущий пароль разработчика",
                "Очистить пароль разработчика",
                "Вернуться в главное меню"
            ], title="")
            choice = self.ui.get_input(">")
            if choice == "1":
                pwd = self.config.get_dev_password()
                if pwd:
                    self.ui.print_info(f"Текущий пароль: {pwd}")
                else:
                    self.ui.print_warning("Пароль не задан.")
                input("Нажмите Enter...")
            elif choice == "2":
                if self.ui.get_input("Удалить пароль разработчика? (y/n)").lower() == 'y':
                    self.config.set_dev_password("")
                    self.ui.print_success("Пароль удалён. Режим разработчика отключён.")
                    input("Нажмите Enter...")
                    break
                else:
                    self.ui.print_info("Отмена.")
                    input("Нажмите Enter...")
            elif choice == "3":
                break
            else:
                self.ui.print_error("Неверный выбор")
                input("Нажмите Enter...")

    # ------------------------------------------------------------
    # СОЗДАНИЕ КОМНАТЫ
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # ПОДКЛЮЧЕНИЕ
    # ------------------------------------------------------------
    def join_room(self):
        try:
            from client import RPGGameClient
            client = RPGGameClient()
            character_text = self.config.load_player_character_text()
            if not character_text:
                self.ui.print_warning("Персонаж не выбран!")
                self.select_character()
                character_text = self.config.load_player_character_text()
            if not character_text:
                self.ui.print_error("Не удалось загрузить персонажа.")
                return
            player_name = self.ui.get_input("Имя вашего персонажа")
            server_address = self.ui.get_input("Адрес сервера (ws://localhost:8765)")
            dev_password = self.config.get_dev_password()
            asyncio.run(client.join_room(
                player_name=player_name,
                server_address=server_address,
                character_desc=character_text,
                player_color=self.config.settings.get("player_color", "WHITE"),
                dev_password=dev_password
            ))
        except Exception as e:
            self.ui.print_error(f"Ошибка подключения: {e}")
        input("Нажмите Enter для возврата...")

    # ------------------------------------------------------------
    # ПОИСК СЕРВЕРОВ
    # ------------------------------------------------------------
    def find_servers(self):
        self.ui.clear_screen()
        self.ui.print_header("ПОИСК СЕРВЕРОВ")
        try:
            from client import RPGGameClient
            client = RPGGameClient()
            servers = asyncio.run(client.discover_servers())
            if not servers:
                self.ui.print_warning("Серверы не найдены.")
                input("Нажмите Enter...")
                return
            self.ui.print_info("Найденные серверы:")
            for i, srv in enumerate(servers, 1):
                status = "Игра идёт" if srv.get("game_started") else "В лобби"
                self.ui.print_colored(
                    f"{i}. {srv['room_name']} | {srv['ip']} | {srv.get('network_type','?')} | "
                    f"Игроков: {srv['players']}/{srv['max_players']} | {status}",
                    Fore.CYAN
                )
            while True:
                choice = self.ui.get_input("\nВведите номер сервера (0 - назад, P - посмотреть игроков):")
                if choice == "0":
                    break
                if choice.upper() == "P":
                    try:
                        idx = int(self.ui.get_input("Номер сервера для просмотра:")) - 1
                        if 0 <= idx < len(servers):
                            addr = servers[idx]['address']
                            players = asyncio.run(client.get_server_players(addr))
                            if players:
                                self.ui.print_info("Игроки на сервере:")
                                for p in players:
                                    self.ui.print_colored(f"  - {p}", Fore.CYAN)
                            else:
                                self.ui.print_warning("Не удалось получить список игроков.")
                    except ValueError:
                        self.ui.print_error("Неверный номер")
                    continue
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(servers):
                        addr = servers[idx]['address']
                        self.join_room_with_address(addr)
                        break
                    else:
                        self.ui.print_error("Неверный номер")
                except ValueError:
                    self.ui.print_error("Введите число")
        except Exception as e:
            self.ui.print_error(f"Ошибка поиска: {e}")
        input("Нажмите Enter...")

    def join_room_with_address(self, address):
        try:
            from client import RPGGameClient
            client = RPGGameClient()
            character_text = self.config.load_player_character_text()
            if not character_text:
                self.ui.print_warning("Персонаж не выбран!")
                self.select_character()
                character_text = self.config.load_player_character_text()
            if not character_text:
                self.ui.print_error("Не удалось загрузить персонажа.")
                return
            player_name = self.ui.get_input("Имя вашего персонажа")
            dev_password = self.config.get_dev_password()
            asyncio.run(client.join_room(
                player_name=player_name,
                server_address=address,
                character_desc=character_text,
                player_color=self.config.settings.get("player_color", "WHITE"),
                dev_password=dev_password
            ))
        except Exception as e:
            self.ui.print_error(f"Ошибка подключения: {e}")

    # ------------------------------------------------------------
    # ОНЛАЙН ИГРА
    # ------------------------------------------------------------
    def online_menu(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("ОНЛАЙН ИГРА")
            self.ui.print_menu([
                "Поиск публичных комнат",
                "Создать публичную комнату",
                "Назад"
            ], title="")
            choice = self.ui.get_input(">")
            if choice == "1":
                self.find_public_rooms()
            elif choice == "2":
                self.config.set_use_public(True)
                self.create_room()
                self.config.set_use_public(False)
            elif choice == "3":
                break
            else:
                self.ui.print_error("Неверный выбор")
            if choice != "3":
                input("Нажмите Enter...")

    def find_public_rooms(self):
        self.ui.clear_screen()
        self.ui.print_header("ПУБЛИЧНЫЕ КОМНАТЫ")
        coordinator = self.config.get_coordinator_address()
        self.ui.print_info(f"Координатор: {coordinator}")
        try:
            from client import RPGGameClient
            client = RPGGameClient()
            rooms = asyncio.run(client.get_public_rooms(coordinator))
            if not rooms:
                self.ui.print_warning("Нет доступных публичных комнат.")
                input("Нажмите Enter...")
                return
            self.ui.print_info("Доступные публичные комнаты:")
            for i, room in enumerate(rooms, 1):
                status = "Игра идёт" if room.get("game_started") else "В лобби"
                self.ui.print_colored(
                    f"{i}. {room['room_name']} | {room['ip']}:{room['port']} | "
                    f"Игроков: {room['players']}/{room['max_players']} | {status}",
                    Fore.CYAN
                )
            while True:
                choice = self.ui.get_input("\nВведите номер комнаты (0 - назад):")
                if choice == "0":
                    break
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(rooms):
                        addr = f"ws://{rooms[idx]['ip']}:{rooms[idx]['port']}"
                        self.join_room_with_address(addr)
                        break
                    else:
                        self.ui.print_error("Неверный номер")
                except ValueError:
                    self.ui.print_error("Введите число")
        except Exception as e:
            self.ui.print_error(f"Ошибка: {e}")
        input("Нажмите Enter...")

    # ------------------------------------------------------------
    # НАСТРОЙКИ
    # ------------------------------------------------------------
    def settings_menu(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("НАСТРОЙКИ")
            self.ui.print_menu([
                "Настройки модели Ollama",
                "Выбрать персонажа",
                "Выбрать цвет игрока",
                "Сетевые настройки (IP, дружба, координатор)",
                "Управление характеристиками (шаблон)",
                "Пароль разработчика",
                "Назад"
            ], title="")
            choice = self.ui.get_input(">")
            if choice == "1":
                self.ollama_settings()
            elif choice == "2":
                self.select_character()
            elif choice == "3":
                self.select_player_color()
            elif choice == "4":
                self.network_settings()
            elif choice == "5":
                self.manage_stats_template()
            elif choice == "6":
                self.set_dev_password()
            elif choice == "7":
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
            ], title="")
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

    def network_settings(self):
        self.ui.clear_screen()
        self.ui.print_header("СЕТЕВЫЕ НАСТРОЙКИ")
        current_ip = self.config.get_manual_ip()
        allow = self.config.settings.get("allow_friend_requests", True)
        coordinator = self.config.get_coordinator_address()
        use_public = self.config.get_use_public()
        self.ui.print_info(f"Ручной IP: {current_ip if current_ip else 'авто'}")
        self.ui.print_info(f"Принимать запросы дружбы: {'да' if allow else 'нет'}")
        self.ui.print_info(f"Координатор: {coordinator}")
        self.ui.print_info(f"Публичные комнаты: {'включены' if use_public else 'выключены'}")
        self.ui.print_menu([
            "Изменить ручной IP",
            "Переключить приём запросов дружбы",
            "Настроить адрес координатора",
            "Включить/выключить публичные комнаты",
            "Назад"
        ], title="")
        choice = self.ui.get_input(">")
        if choice == "1":
            new_ip = self.ui.get_input("Введите IP (пусто – авто):")
            self.config.set_manual_ip(new_ip)
            self.ui.print_success("Сохранено.")
        elif choice == "2":
            self.config.settings["allow_friend_requests"] = not allow
            self.config.save_settings()
            self.ui.print_success(f"Приём запросов дружбы: {'включён' if not allow else 'выключен'}")
        elif choice == "3":
            new_addr = self.ui.get_input("Адрес координатора (ws://...):")
            self.config.set_coordinator_address(new_addr)
            self.ui.print_success(f"Координатор: {new_addr}")
        elif choice == "4":
            self.config.set_use_public(not use_public)
            self.ui.print_success(f"Публичные комнаты: {'включены' if not use_public else 'выключены'}")
        elif choice == "5":
            return
        else:
            self.ui.print_error("Неверный выбор")
        input("Нажмите Enter...")

    def select_player_color(self):
        self.ui.clear_screen()
        self.ui.print_header("ВЫБОР ЦВЕТА ИГРОКА")
        color_names = list(self.colors.keys())
        for i, name in enumerate(color_names, 1):
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

    # ------------------------------------------------------------
    # ШАБЛОН ХАРАКТЕРИСТИК
    # ------------------------------------------------------------
    def manage_stats_template(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("ШАБЛОН ХАРАКТЕРИСТИК")
            template = self.config.load_stats_template()
            if template:
                self.ui.print_info("Текущий шаблон:")
                for key, val in template.items():
                    self.ui.print_colored(f"  {key}: {val}", Fore.CYAN)
            else:
                self.ui.print_info("Шаблон пуст")
            self.ui.print_menu([
                "Добавить характеристику",
                "Изменить значение по умолчанию",
                "Удалить характеристику",
                "Назад"
            ], title="")
            choice = self.ui.get_input(">")
            if choice == "1":
                name = self.ui.get_input("Название новой характеристики (англ.):")
                if name:
                    try:
                        default_val = float(self.ui.get_input("Значение по умолчанию:"))
                        template[name] = default_val
                        self.config.save_stats_template(template)
                        self.ui.print_success(f"'{name}' добавлена")
                    except ValueError:
                        self.ui.print_error("Нужно число")
            elif choice == "2":
                if not template:
                    self.ui.print_error("Нет характеристик")
                    continue
                name = self.ui.get_input("Название характеристики для изменения:")
                if name in template:
                    try:
                        new_val = float(self.ui.get_input(f"Новое значение для {name}:"))
                        template[name] = new_val
                        self.config.save_stats_template(template)
                        self.ui.print_success("Значение обновлено")
                    except ValueError:
                        self.ui.print_error("Число!")
                else:
                    self.ui.print_error("Не найдено")
            elif choice == "3":
                if not template:
                    self.ui.print_error("Пусто")
                    continue
                name = self.ui.get_input("Название для удаления:")
                if name in template:
                    del template[name]
                    self.config.save_stats_template(template)
                    self.ui.print_success(f"'{name}' удалена")
                else:
                    self.ui.print_error("Не найдено")
            elif choice == "4":
                break
            input("Нажмите Enter...")

    # ------------------------------------------------------------
    # ПАРОЛЬ РАЗРАБОТЧИКА
    # ------------------------------------------------------------
    def set_dev_password(self):
        self.ui.clear_screen()
        self.ui.print_header("ПАРОЛЬ РАЗРАБОТЧИКА")
        self.ui.print_info("Этот пароль даст вам читерские права на сервере.")
        current = self.config.get_dev_password()
        if current:
            self.ui.print_info("Пароль уже задан. Введите новый или оставьте пустым для удаления.")
        else:
            self.ui.print_info("Пароль не задан. Введите новый.")
        new_pwd = self.ui.get_password("Введите пароль (скрытый ввод):")
        if new_pwd.strip() == "":
            if current:
                if self.ui.get_input("Удалить пароль? (y/n)").lower() == 'y':
                    self.config.set_dev_password("")
                    self.ui.print_success("Пароль удалён.")
            else:
                self.ui.print_info("Пароль не изменён.")
        else:
            self.config.set_dev_password(new_pwd)
            self.ui.print_success("Пароль сохранён.")
        input("Нажмите Enter...")

    # ------------------------------------------------------------
    # УПРАВЛЕНИЕ ПЕРСОНАЖАМИ
    # ------------------------------------------------------------
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
            ], title="")
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
            if self.ui.get_input("Персонаж уже существует. Перезаписать? (y/n)").lower() != 'y':
                return
        content = self.ui.get_multiline_input("Введите описание персонажа (пустая строка — конец):")
        if not content:
            return
        self.config.save_character(name, content)
        if self.ui.get_input("Добавить характеристики? (y/n)").lower() == 'y':
            self.configure_character_stats(name)
        else:
            self.config.delete_character_stats(name)
        self.ui.print_success(f"Персонаж '{name}' сохранён!")

    def configure_character_stats(self, name):
        template = self.config.load_stats_template()
        if not template:
            self.ui.print_info("Шаблон характеристик пуст. Создайте его в настройках.")
            return
        stats = {}
        self.ui.print_info("Настройка характеристик (оставьте пустым для значения по умолчанию):")
        for key, default_val in template.items():
            val_input = self.ui.get_input(f"{key} (по умолчанию {default_val}):")
            if val_input.strip() == "":
                stats[key] = default_val
            else:
                try:
                    stats[key] = float(val_input)
                except ValueError:
                    self.ui.print_error("Не число, будет использовано значение по умолчанию")
                    stats[key] = default_val
        self.config.save_character_stats(name, stats)
        self.ui.print_success("Характеристики сохранены.")

    def edit_character(self):
        self.ui.clear_screen()
        self.ui.print_header("РЕДАКТИРОВАНИЕ ПЕРСОНАЖА")
        chars = self.config.list_characters()
        if not chars:
            self.ui.print_info("Нет персонажей")
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
                new_content = self.ui.get_multiline_input("Новый текст (пустая строка — отмена):")
                if new_content.strip():
                    self.config.save_character(name, new_content)
                stats = self.config.get_character_stats(name)
                if stats:
                    self.ui.print_info("Текущие характеристики:")
                    for k, v in stats.items():
                        self.ui.print_colored(f"  {k}: {v}", Fore.CYAN)
                if self.ui.get_input("Изменить характеристики? (y/n)").lower() == 'y':
                    self.configure_character_stats(name)
                self.ui.print_success(f"Персонаж '{name}' обновлён")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")
        input("Нажмите Enter...")

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
                if self.ui.get_input(f"Удалить '{name}'? (y/n)").lower() == 'y':
                    self.config.delete_character(name)
                    self.config.delete_character_stats(name)
                    self.ui.print_success(f"'{name}' удалён")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")
        input("Нажмите Enter...")

    def select_character(self):
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
                    manual = self.ui.get_multiline_input("Введите описание:")
                    if manual:
                        temp_name = "_manual_character"
                        self.config.save_character(temp_name, manual)
                        self.config.set_player_character_file(temp_name)
                        self.config.delete_character_stats(temp_name)
                        self.ui.print_success("Персонаж установлен")
                elif 1 <= idx <= len(chars):
                    name = chars[idx-1]
                    self.config.set_player_character_file(name)
                    self.ui.print_success(f"Выбран персонаж '{name}'")
                else:
                    self.ui.print_error("Неверный номер")
            except ValueError:
                self.ui.print_error("Введите число")
        else:
            self.ui.print_info("Нет сохранённых персонажей")
            manual = self.ui.get_multiline_input("Введите описание:")
            if manual:
                temp_name = "_manual_character"
                self.config.save_character(temp_name, manual)
                self.config.set_player_character_file(temp_name)
                self.ui.print_success("Персонаж установлен")
        input("Нажмите Enter...")

    # ------------------------------------------------------------
    # УПРАВЛЕНИЕ МИРАМИ
    # ------------------------------------------------------------
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
            ], title="")
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
        input("Нажмите Enter...")

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
        input("Нажмите Enter...")

    def select_or_create_world(self):
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

    # ------------------------------------------------------------
    # ДРУЗЬЯ
    # ------------------------------------------------------------
    def friends_menu(self):
        while True:
            self.ui.clear_screen()
            self.ui.print_header("ДРУЗЬЯ")
            friends = self.config.get_friends()
            if friends:
                self.ui.print_info("Список друзей:")
                for i, (nick, ip) in enumerate(friends.items(), 1):
                    online = asyncio.run(self.check_friend_online(ip))
                    status = "🟢 В сети" if online else "🔴 Не в сети"
                    self.ui.print_colored(f"{i}. {nick} | {ip} | {status}", Fore.CYAN)
                self.ui.print_info(f"Всего друзей: {len(friends)}")
            else:
                self.ui.print_info("У вас пока нет друзей.")
            self.ui.print_menu([
                "Посмотреть сервера друзей",
                "Удалить друга",
                "Назад"
            ], title="")
            choice = self.ui.get_input(">")
            if choice == "1":
                self.view_friends_servers()
            elif choice == "2":
                self.delete_friend()
            elif choice == "3":
                break
            else:
                self.ui.print_error("Неверный выбор")
            if choice != "3":
                input("Нажмите Enter...")

    async def check_friend_online(self, ip):
        from client import RPGGameClient
        client = RPGGameClient()
        info = await client.check_friend_online(ip)
        return info is not None

    def view_friends_servers(self):
        self.ui.clear_screen()
        self.ui.print_header("СЕРВЕРА ДРУЗЕЙ")
        friends = self.config.get_friends()
        if not friends:
            self.ui.print_info("Нет друзей для проверки.")
            input("Нажмите Enter...")
            return
        self.ui.print_info("Проверка серверов...")
        servers = []
        for nick, ip in friends.items():
            info = asyncio.run(self._check_friend_server(ip))
            if info:
                info['address'] = f"ws://{info['ip']}:{info['port']}"
                info['friend_nick'] = nick
                servers.append(info)
        if not servers:
            self.ui.print_warning("Ни один друг не запустил сервер.")
            input("Нажмите Enter...")
            return
        self.ui.print_info("Доступные сервера друзей:")
        for i, srv in enumerate(servers, 1):
            status = "Игра идёт" if srv.get("game_started") else "В лобби"
            self.ui.print_colored(
                f"{i}. {srv['friend_nick']} | {srv['room_name']} | {srv['ip']} | "
                f"Игроков: {srv['players']}/{srv['max_players']} | {status}",
                Fore.CYAN
            )
        while True:
            choice = self.ui.get_input("\nВведите номер сервера (0 - назад):")
            if choice == "0":
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(servers):
                    addr = servers[idx]['address']
                    self.join_room_with_address(addr)
                    break
                else:
                    self.ui.print_error("Неверный номер")
            except ValueError:
                self.ui.print_error("Введите число")
        input("Нажмите Enter...")

    async def _check_friend_server(self, ip):
        from client import RPGGameClient
        client = RPGGameClient()
        return await client.check_friend_online(ip)

    def delete_friend(self):
        self.ui.clear_screen()
        self.ui.print_header("УДАЛЕНИЕ ДРУГА")
        friends = self.config.get_friends()
        if not friends:
            self.ui.print_info("Нет друзей для удаления.")
            input("Нажмите Enter...")
            return
        for i, (nick, ip) in enumerate(friends.items(), 1):
            self.ui.print_colored(f"{i}. {nick}", Fore.CYAN)
        try:
            idx = int(self.ui.get_input("Номер для удаления")) - 1
            if 0 <= idx < len(friends):
                nick = list(friends.keys())[idx]
                if self.ui.get_input(f"Удалить '{nick}' из друзей? (y/n)").lower() == 'y':
                    self.config.remove_friend(nick)
                    self.ui.print_success(f"'{nick}' удалён.")
            else:
                self.ui.print_error("Неверный номер")
        except ValueError:
            self.ui.print_error("Введите число")
        input("Нажмите Enter...")


if __name__ == "__main__":
    try:
        menu = MainMenu()
        menu.run()
    except KeyboardInterrupt:
        print("\nВыход из программы...")
        sys.exit(0)
    except Exception as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
        traceback.print_exc()
        with open("error_log.txt", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        input("Нажмите Enter для выхода...")