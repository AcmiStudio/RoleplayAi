"""
server.py – Полный сервер RPG (правильный локальный IP для Windows, устойчивость)
"""
import asyncio
import json
import socket
import subprocess
import platform
import re
from datetime import datetime
from config import Config
from utils import ConsoleUI
from colorama import Fore, Style, init
import aiohttp

init(autoreset=True)

try:
    import websockets
except ImportError:
    print("Ошибка: модуль 'websockets' не установлен!")
    print("Установите его командой: pip install websockets")
    exit(1)


def get_local_ip():
    """
    Возвращает локальный IP, доступный в частной сети (предпочитает Wi‑Fi/Ethernet).
    Для Windows – парсит ipconfig, для Linux/Android – ip addr show up.
    """
    system = platform.system()
    if system == "Windows":
        try:
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True, text=True, timeout=10,
                encoding="cp866", errors="replace"  # корректная кодировка для русской Windows
            )
            output = result.stdout
            # Ищем все адаптеры и их IPv4-адреса
            adapters = re.split(r'\r?\n(?=\S)', output)  # разделяем на блоки адаптеров
            for adapter in adapters:
                # Виртуальные адаптеры часто содержат ключевые слова, пропускаем их
                if any(skip in adapter.lower() for skip in
                       ["virtual", "vmware", "virtualbox", "hyper-v", "bluetooth", "loopback"]):
                    continue
                # Ищем строку с IPv4
                ip_match = re.search(r'IPv4[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', adapter)
                if ip_match:
                    ip = ip_match.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254."):  # игнорируем loopback и APIPA
                        # Проверяем, что IP принадлежит частному диапазону
                        octets = list(map(int, ip.split('.')))
                        if (octets[0] == 10 or
                            (octets[0] == 172 and 16 <= octets[1] <= 31) or
                            (octets[0] == 192 and octets[1] == 168)):
                            return ip
            # Если не нашли частный IP, возвращаем первый не‑loopback
            for adapter in adapters:
                ip_match = re.search(r'IPv4[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', adapter)
                if ip_match:
                    ip = ip_match.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        return ip
        except Exception as e:
            pass
        # Fallback: старый способ
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

    else:
        # Linux / Android (Termux)
        try:
            result = subprocess.run(
                ["ip", "-o", "addr", "show", "up"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and '127.0.0.1' not in line:
                        parts = line.strip().split()
                        for i, part in enumerate(parts):
                            if part == 'inet':
                                ip = parts[i+1].split('/')[0]
                                if not ip.startswith("172."):  # отсекаем Docker
                                    return ip
        except:
            pass
        try:
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                for ip in ips:
                    if not ip.startswith("127.") and not ip.startswith("172."):
                        return ip
                if ips:
                    return ips[0]
        except:
            pass
        return "127.0.0.1"


class RPGGameServer:
    def __init__(self):
        self.config = Config()
        self.ui = ConsoleUI()

        self.clients = {}
        self.max_players = 4
        self.game_started = False
        self.turn_mode = "free"
        self.current_turn_index = 0
        self.room_name = ""
        self.world_description = ""
        self.jailed_players = set()

        self.ollama_model = self.config.settings["ollama"]["model"]
        self.temperature = self.config.settings["ollama"]["temperature"]
        self.narrator_prompt = self.config.settings["ollama"]["narrator_prompt"]

    async def start_server(self, host, port, room_name, max_players, turn_mode, world_description):
        self.room_name = room_name
        self.max_players = max_players
        self.turn_mode = turn_mode
        self.world_description = world_description

        if not await self.check_ollama():
            self.ui.print_warning("Ollama недоступна или модель не найдена. Игра может не работать.")
        else:
            self.ui.print_success(f"Модель {self.ollama_model} готова")

        local_ip = get_local_ip()
        if local_ip == "127.0.0.1":
            self.ui.print_warning("Не удалось определить сетевой IP, используется 127.0.0.1 (только локально)")

        self.ui.clear_screen()
        self.ui.print_header("СЕРВЕР ЗАПУЩЕН")
        self.ui.print_success(f"Комната: {self.room_name}")
        self.ui.print_success(f"Режим: {'Свободный' if self.turn_mode == 'free' else 'Поочерёдный'}")
        self.ui.print_success(f"Игроки: 0/{self.max_players}")
        self.ui.print_info(f"Адрес: ws://{local_ip}:{port}")
        self.ui.print_info("Ожидание подключений...")
        self.ui.print_info("Вводите команды (/start, /help и т.д.)")
        self.ui.print_warning("Ctrl+C для остановки")

        console_task = asyncio.create_task(self.console_input_task())

        try:
            async with websockets.serve(self.handle_client, host, port):
                await asyncio.Future()
        except asyncio.CancelledError:
            pass
        finally:
            console_task.cancel()

    async def check_ollama(self):
        url = "http://localhost:11434/api/tags"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m["name"] for m in data.get("models", [])]
                        return self.ollama_model in models
        except:
            pass
        return False

    async def handle_client(self, websocket):
        if len(self.clients) >= self.max_players:
            await websocket.send(json.dumps({"type": "error", "message": "Комната заполнена"}))
            return

        try:
            player_info_raw = await websocket.recv()
            player_info = json.loads(player_info_raw)

            self.clients[websocket] = {
                "name": player_info.get("name", "Unknown"),
                "character": player_info.get("character", ""),
                "color": player_info.get("color", "WHITE"),
                "joined_at": datetime.now().isoformat(),
                "websocket": websocket
            }

            await self.broadcast({
                "type": "player_joined",
                "player_name": self.clients[websocket]["name"],
                "total_players": len(self.clients),
                "max_players": self.max_players
            })

            self.ui.print_success(f"Игрок {self.clients[websocket]['name']} подключился "
                                  f"({len(self.clients)}/{self.max_players})")

            await websocket.send(json.dumps({
                "type": "room_info",
                "room_name": self.room_name,
                "players": [{"name": info["name"]} for info in self.clients.values()],
                "mode": self.turn_mode,
                "game_started": self.game_started
            }))

            async for message in websocket:
                await self.handle_message(websocket, message)

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            self.ui.print_error(f"Ошибка: {e}")
        finally:
            await self.handle_disconnect(websocket)

    async def handle_message(self, websocket, message):
        try:
            data = json.loads(message)
            player_name = self.clients[websocket]["name"]
            if data["type"] == "chat":
                if self.game_started:
                    await self.process_game_message(websocket, data["content"])
                else:
                    await self.broadcast({
                        "type": "lobby_message",
                        "from": player_name,
                        "content": data["content"],
                        "player_color": self.clients[websocket]["color"]
                    })
            elif data["type"] == "admin_command":
                await self.handle_admin_command(websocket, data["command"])
        except json.JSONDecodeError:
            self.ui.print_error("Неверный формат сообщения")

    async def process_game_message(self, websocket, content):
        player_name = self.clients[websocket]["name"]
        if player_name in self.jailed_players:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Вы заблокированы администратором"
            }))
            return

        if self.turn_mode == "turn":
            player_list = list(self.clients.values())
            if self.current_turn_index >= len(player_list):
                self.current_turn_index = 0
            current_player = player_list[self.current_turn_index]
            if current_player["name"] != player_name:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Сейчас ход игрока {current_player['name']}"
                }))
                return

        character = self.clients[websocket]["character"]
        prompt = self.build_ai_prompt(player_name, character, content)
        response = await self.get_ai_response(prompt)

        await self.broadcast({
            "type": "narrator_response",
            "from": player_name,
            "action": content,
            "response": response,
            "player_color": self.clients[websocket]["color"]
        })

        if self.turn_mode == "turn":
            self.current_turn_index = (self.current_turn_index + 1) % len(self.clients)
            next_player = list(self.clients.values())[self.current_turn_index]
            await self.broadcast({
                "type": "next_turn",
                "player": next_player["name"]
            })

    def build_ai_prompt(self, player_name, character, action):
        context = f"""
{self.narrator_prompt}

МИР ИГРЫ:
{self.world_description}

ТЕКУЩИЕ ИГРОКИ:
"""
        for client_info in self.clients.values():
            if client_info["name"] not in self.jailed_players:
                context += f"- {client_info['name']}: {client_info['character']}\n"
        context += f"""
ДЕЙСТВИЕ ИГРОКА:
{player_name} ({character}) делает: {action}

Как рассказчик, опиши результат этого действия и развитие событий. 
Учти особенности персонажа и окружающий мир.
Ответь атмосферно и детально, сохраняя стиль повествования.
"""
        return context

    async def get_ai_response(self, prompt):
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature}
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "Пустой ответ")
                    else:
                        error_text = await response.text()
                        self.ui.print_error(f"HTTP ошибка {response.status}: {error_text}")
                        return f"Ошибка HTTP {response.status}"
        except aiohttp.ClientConnectorError:
            self.ui.print_error("Не удалось подключиться к Ollama (порт 11434)")
            return "Ошибка: Ollama не запущена."
        except Exception as e:
            self.ui.print_error(f"Ошибка API: {e}")
            return f"Ошибка связи с Ollama: {str(e)}"

    async def handle_admin_command(self, websocket, command):
        if websocket != list(self.clients.keys())[0]:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Только администратор может использовать команды"
            }))
            return
        await self._execute_admin_command(command)

    async def _execute_admin_command(self, command):
        parts = command.split()
        if not parts:
            return
        cmd = parts[0].lower()
        if cmd == "/kick" and len(parts) > 1:
            await self.kick_player(parts[1])
        elif cmd == "/jail" and len(parts) > 1:
            self.jailed_players.add(parts[1])
            await self.broadcast({"type": "player_jailed", "player": parts[1]})
        elif cmd == "/unjail" and len(parts) > 1:
            self.jailed_players.discard(parts[1])
            await self.broadcast({"type": "player_unjailed", "player": parts[1]})
        elif cmd == "/mode" and len(parts) > 1:
            new_mode = parts[1]
            if new_mode in ["free", "turn"]:
                self.turn_mode = new_mode
                await self.broadcast({"type": "mode_changed", "mode": new_mode})
        elif cmd == "/stop":
            await self.stop_game()
        elif cmd == "/start":
            await self.start_game()
        elif cmd == "/help":
            self.show_help()
        else:
            self.ui.print_error("Неизвестная команда. /help для списка")

    def show_help(self):
        self.ui.print_info("Доступные команды:")
        self.ui.print_info("  /start - начать игру")
        self.ui.print_info("  /stop - завершить игру")
        self.ui.print_info("  /kick <имя> - отключить игрока")
        self.ui.print_info("  /jail <имя> - заблокировать")
        self.ui.print_info("  /unjail <имя> - разблокировать")
        self.ui.print_info("  /mode <free/turn> - сменить режим")
        self.ui.print_info("  /help - эта справка")

    async def console_input_task(self):
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, "")
                line = line.strip()
                if not line:
                    continue
                if line.startswith("/"):
                    await self._execute_admin_command(line)
                else:
                    self.ui.print_warning("Используйте команды, начинающиеся с /")
            except EOFError:
                break
            except Exception as e:
                self.ui.print_error(f"Ошибка ввода: {e}")

    async def start_game(self):
        if len(self.clients) < 2:
            self.ui.print_error("Нужно минимум 2 игрока")
            return
        self.game_started = True
        initial_prompt = f"""
{self.narrator_prompt}

МИР ИГРЫ:
{self.world_description}

Начни игру с захватывающего вступления. Опиши начальную сцену и ситуацию, 
в которой оказались персонажи. Создай атмосферу и задай тон повествованию.
"""
        initial_scene = await self.get_ai_response(initial_prompt)
        await self.broadcast({
            "type": "game_started",
            "scene": initial_scene,
            "mode": self.turn_mode
        })
        if self.turn_mode == "turn":
            if self.clients:
                first_player = list(self.clients.values())[0]
                await self.broadcast({
                    "type": "next_turn",
                    "player": first_player["name"]
                })

    async def stop_game(self):
        self.game_started = False
        await self.broadcast({
            "type": "game_stopped",
            "message": "Администратор завершил игру"
        })

    async def kick_player(self, player_name):
        for ws, info in list(self.clients.items()):
            if info["name"] == player_name:
                await ws.send(json.dumps({
                    "type": "kicked",
                    "message": "Вы были отключены администратором"
                }))
                await ws.close()
                break

    async def handle_disconnect(self, websocket):
        if websocket in self.clients:
            player_name = self.clients[websocket]["name"]
            del self.clients[websocket]
            await self.broadcast({
                "type": "player_left",
                "player_name": player_name,
                "total_players": len(self.clients)
            })
            self.ui.print_warning(f"Игрок {player_name} отключился")

    async def broadcast(self, message):
        msg_type = message.get("type", "")
        if msg_type == "player_joined":
            self.ui.print_colored(f"✓ Игрок {message['player_name']} подключился "
                                  f"({message['total_players']}/{message['max_players']})", Fore.GREEN)
        elif msg_type == "player_left":
            self.ui.print_colored(f"⚠ Игрок {message['player_name']} отключился", Fore.YELLOW)
        elif msg_type == "lobby_message":
            color = getattr(Fore, message.get("player_color", "WHITE"), Fore.WHITE)
            self.ui.print_colored(f"[Лобби] {message['from']}: {message['content']}", color)
        elif msg_type == "narrator_response":
            color = getattr(Fore, message.get("player_color", "WHITE"), Fore.WHITE)
            self.ui.print_colored(f"\n{message['from']} делает: {message['action']}", color)
            self.ui.print_colored(f"Рассказчик: {message['response']}\n", Fore.WHITE)
        elif msg_type == "game_started":
            self.ui.print_header("ИГРА НАЧАЛАСЬ!")
            self.ui.print_colored(message['scene'] + "\n", Fore.WHITE)
        elif msg_type == "game_stopped":
            self.ui.print_header("ИГРА ЗАВЕРШЕНА")
            self.ui.print_info(message.get("message", ""))
        elif msg_type == "next_turn":
            self.ui.print_colored(f"Ход переходит к: {message['player']}", Fore.GREEN)
        elif msg_type == "player_jailed":
            self.ui.print_colored(f"⛔ Игрок {message['player']} заблокирован", Fore.RED)
        elif msg_type == "player_unjailed":
            self.ui.print_colored(f"✓ Игрок {message['player']} разблокирован", Fore.GREEN)
        elif msg_type == "mode_changed":
            mode_name = "Свободный" if message['mode'] == 'free' else 'Поочерёдный'
            self.ui.print_colored(f"Режим изменён на: {mode_name}", Fore.CYAN)
        elif msg_type == "error":
            self.ui.print_colored(f"Ошибка: {message.get('message', '')}", Fore.RED)

        if self.clients:
            message_json = json.dumps(message)
            for ws in list(self.clients.keys()):
                try:
                    await ws.send(message_json)
                except websockets.exceptions.ConnectionClosed:
                    if ws in self.clients:
                        self.ui.print_warning(f"Клиент {self.clients[ws]['name']} отключился при отправке")
                        del self.clients[ws]
                except Exception as e:
                    self.ui.print_error(f"Ошибка отправки клиенту: {e}")