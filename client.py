"""
client.py – Клиент RPG (поддержка dev-режима, характеристик, флагов)
"""
import asyncio
import json
from config import Config
from utils import ConsoleUI
from colorama import Fore

try:
    import websockets
except ImportError:
    print("Ошибка: модуль 'websockets' не установлен!")
    print("Установите его командой: pip install websockets")
    exit(1)


class RPGGameClient:
    def __init__(self):
        self.config = Config()
        self.ui = ConsoleUI()
        self.websocket = None
        self.player_name = ""
        self.character_desc = ""
        self.player_color = "WHITE"
        self.is_admin = False
        self.is_dev = False
        self.room_name = ""
        self.my_turn = False
        self.running = True
        self.stats = {}
        self.dev_password = ""

    async def join_room(self, player_name, server_address, character_desc, player_color="WHITE", dev_password=""):
        self.player_name = player_name
        self.character_desc = character_desc
        self.player_color = player_color
        self.dev_password = dev_password
        char_file = self.config.get_player_character_file()
        self.stats = self.config.get_character_stats(char_file) if char_file else {}
        self.config.save_settings()
        self.ui.print_info("Подключение к серверу...")
        await self.connect_to_server(server_address)

    async def connect_to_server(self, uri):
        try:
            self.websocket = await websockets.connect(uri)
        except OSError as e:
            self.ui.print_error(f"Не удалось подключиться к {uri}")
            if "ConnectionRefused" in str(e) or e.errno == 10061:
                self.ui.print_error("Сервер не доступен. Проверьте IP, порт и брандмауэр.")
            else:
                self.ui.print_error(f"Ошибка: {e}")
            return
        except Exception as e:
            self.ui.print_error(f"Неизвестная ошибка подключения: {e}")
            return

        try:
            player_info = {
                "name": self.player_name,
                "character": self.character_desc,
                "color": self.player_color,
                "stats": self.stats,
                "dev_password": self.dev_password
            }
            await self.websocket.send(json.dumps(player_info))
            receive_task = asyncio.create_task(self.receive_messages())
            send_task = asyncio.create_task(self.send_messages())
            await asyncio.gather(receive_task, send_task)
        except websockets.exceptions.ConnectionClosed:
            self.ui.print_warning("Соединение закрыто сервером")
        except Exception as e:
            self.ui.print_error(f"Ошибка: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()

    async def receive_messages(self):
        try:
            while self.running:
                message = await self.websocket.recv()
                data = json.loads(message)
                await self.process_server_message(data)
        except websockets.exceptions.ConnectionClosed:
            self.ui.print_warning("Соединение разорвано")
            self.running = False

    async def process_server_message(self, data):
        msg_type = data.get("type", "")
        if msg_type == "room_info":
            self.room_name = data["room_name"]
            self.is_dev = data.get("you_are_dev", False)
            if self.is_dev:
                self.ui.print_success("Вы вошли как разработчик!")
            self.ui.print_header(f"КОМНАТА: {self.room_name}")
            self.ui.print_info(f"Режим: {data['mode']}")
            self.ui.print_info("Игроки в комнате:")
            for player in data["players"]:
                self.ui.print_colored(f"  - {player['name']}", Fore.CYAN)
        elif msg_type == "player_joined":
            self.ui.print_success(f"Игрок {data['player_name']} присоединился "
                                  f"({data['total_players']}/{data['max_players']})")
        elif msg_type == "player_left":
            self.ui.print_warning(f"Игрок {data['player_name']} покинул комнату")
        elif msg_type == "game_started":
            self.ui.clear_screen()
            self.ui.print_header("ИГРА НАЧАЛАСЬ!")
            self.ui.print_colored("\n" + data["scene"] + "\n", Fore.WHITE)
            self.ui.print_info("Описывайте действия вашего персонажа")
        elif msg_type == "narrator_response":
            color = getattr(Fore, data.get("player_color", "WHITE"), Fore.WHITE)
            self.ui.print_colored(f"\n{data['from']} делает: {data['action']}", color)
            self.ui.print_colored(f"Рассказчик: {data['response']}\n", Fore.WHITE)
        elif msg_type == "next_turn":
            if data["player"] == self.player_name:
                self.my_turn = True
                self.ui.print_colored("ВАШ ХОД!", Fore.GREEN)
            else:
                self.my_turn = False
                self.ui.print_info(f"Ход игрока: {data['player']}")
        elif msg_type == "lobby_message":
            color = getattr(Fore, data.get("player_color", "WHITE"), Fore.WHITE)
            self.ui.print_colored(f"[Лобби] {data['from']}: {data['content']}", color)
        elif msg_type == "private_message":
            color = getattr(Fore, data.get("player_color", "MAGENTA"), Fore.MAGENTA)
            self.ui.print_colored(f"[ЛС] {data['from']}: {data['text']}", color)
        elif msg_type == "players_list":
            self.ui.print_info("Список игроков:")
            for p in data["players"]:
                line = f"  {p['name']}"
                if p.get("stats"):
                    line += f" | Статы: {p['stats']}"
                if p.get("flags"):
                    line += f" | Флаги: {p['flags']}"
                self.ui.print_colored(line, Fore.CYAN)
        elif msg_type == "stats_update":
            if data["player_name"] == self.player_name:
                self.stats = data["stats"]
            self.ui.print_colored(f"[Статы] {data['player_name']}: {data['stats']}", Fore.CYAN)
        elif msg_type == "stats_display":
            self.ui.print_colored(f"Статы игрока {data['player_name']}: {data['stats']}", Fore.CYAN)
        elif msg_type == "flags_update":
            self.ui.print_colored(f"[Флаги] {data['player_name']}: {data.get('flags', [])}", Fore.MAGENTA)
        elif msg_type == "event_announcement":
            self.ui.print_colored(f"⚠ СОБЫТИЕ: {data['event_name']}", Fore.YELLOW)
            self.ui.print_colored(f"{data['text']}", Fore.YELLOW)
        elif msg_type == "player_jailed":
            self.ui.print_warning(f"Игрок {data['player']} заблокирован")
        elif msg_type == "player_unjailed":
            self.ui.print_success(f"Игрок {data['player']} разблокирован")
        elif msg_type == "mode_changed":
            mode_name = "Свободный" if data['mode'] == 'free' else 'Поочерёдный'
            self.ui.print_info(f"Режим изменён на: {mode_name}")
        elif msg_type == "game_stopped":
            self.ui.print_header("ИГРА ЗАВЕРШЕНА")
            self.ui.print_info(data.get("message", ""))
            self.running = False
        elif msg_type == "kicked":
            self.ui.print_error(data.get("message", ""))
            self.running = False
        elif msg_type == "error":
            self.ui.print_error(data.get("message", ""))

    async def send_messages(self):
        self.ui.print_info("Вводите сообщения (или /help для списка команд):")
        while self.running:
            try:
                loop = asyncio.get_event_loop()
                message = await loop.run_in_executor(None, input, "> ")
                if not message:
                    continue
                if message.startswith("/"):
                    await self.handle_client_command(message)
                else:
                    await self.websocket.send(json.dumps({
                        "type": "chat",
                        "content": message
                    }))
            except EOFError:
                break
            except Exception as e:
                self.ui.print_error(f"Ошибка отправки: {e}")
                break

    async def handle_client_command(self, command):
        parts = command.split()
        if not parts:
            return
        cmd = parts[0].lower()
        if cmd in ["/kick", "/jail", "/unjail", "/mode", "/start", "/stop", "/event", "/setstat", "/modstat", "/setflag"]:
            if self.is_admin or self.is_dev:
                await self.websocket.send(json.dumps({
                    "type": "admin_command",
                    "command": command
                }))
            else:
                self.ui.print_error("Только администратор или разработчик может использовать эту команду")
        elif cmd in ["/msg", "/players", "/stats"]:
            await self.websocket.send(json.dumps({
                "type": "player_command",
                "command": command
            }))
        elif cmd == "/quit":
            self.running = False
            await self.websocket.close()
        elif cmd == "/help":
            self.ui.print_info("/help, /quit, /msg <игрок> <текст>, /players, /stats")
            if self.is_dev or self.is_admin:
                self.ui.print_info("Команды разработчика: /setstat, /modstat, /setflag, /event, /kick, /jail, /mode...")
        else:
            self.ui.print_error("Неизвестная команда. /help для списка")