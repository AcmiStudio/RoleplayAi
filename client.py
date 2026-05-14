"""
client.py – Клиент RPG (исправленное подключение)
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
        self.room_name = ""
        self.my_turn = False
        self.running = True

    async def join_room(self, player_name, server_address, character_desc, player_color="WHITE"):
        self.player_name = player_name
        self.character_desc = character_desc
        self.player_color = player_color
        self.config.settings["player_color"] = player_color
        self.config.settings["player_character"] = character_desc
        self.config.save_settings()
        self.ui.print_info("Подключение к серверу...")
        await self.connect_to_server(server_address)

    async def connect_to_server(self, uri):
        try:
            self.websocket = await websockets.connect(uri)
        except OSError as e:
            self.ui.print_error(f"Не удалось подключиться к {uri}")
            if e.errno == 10061 or "ConnectionRefused" in str(e):
                self.ui.print_error("Сервер не доступен. Проверьте:")
                self.ui.print_error("  - IP-адрес сервера (введите его точно как показано в консоли сервера)")
                self.ui.print_error("  - Брандмауэр Windows: разрешите входящие соединения на порт 8765")
                self.ui.print_error("  - Что сервер запущен и показывает IP, а не localhost")
            else:
                self.ui.print_error(f"Системная ошибка: {e}")
            return
        except Exception as e:
            self.ui.print_error(f"Неизвестная ошибка подключения: {e}")
            return

        try:
            player_info = {
                "name": self.player_name,
                "character": self.character_desc,
                "color": self.player_color
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
            self.ui.print_warning("Соединение с сервером разорвано")
            self.running = False

    async def process_server_message(self, data):
        msg_type = data.get("type", "")
        if msg_type == "room_info":
            self.room_name = data["room_name"]
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
        cmd = parts[0].lower()
        if cmd == "/help":
            self.ui.print_info("Доступные команды:")
            self.ui.print_info("  /help - справка")
            self.ui.print_info("  /quit - выйти из игры")
            if self.is_admin:
                self.ui.print_info("  Администраторские команды:")
                self.ui.print_info("  /kick <имя>, /jail <имя>, /unjail <имя>")
                self.ui.print_info("  /mode <free/turn>, /start, /stop")
        elif cmd == "/quit":
            self.running = False
            await self.websocket.close()
        elif cmd in ["/kick", "/jail", "/unjail", "/mode", "/start", "/stop"]:
            if self.is_admin:
                await self.websocket.send(json.dumps({
                    "type": "admin_command",
                    "command": command
                }))
            else:
                self.ui.print_error("Только администратор может использовать эту команду")
        else:
            self.ui.print_error("Неизвестная команда. /help для списка")