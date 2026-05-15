"""
server.py – Полный сервер RPG (поддержка dev-режима, мета-команды ИИ)
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
    system = platform.system()
    if system == "Windows":
        try:
            result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10,
                                    encoding="cp866", errors="replace")
            output = result.stdout
            adapters = re.split(r'\r?\n(?=\S)', output)
            for adapter in adapters:
                if any(skip in adapter.lower() for skip in
                       ["virtual", "vmware", "virtualbox", "hyper-v", "bluetooth", "loopback"]):
                    continue
                ip_match = re.search(r'IPv4[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', adapter)
                if ip_match:
                    ip = ip_match.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        octets = list(map(int, ip.split('.')))
                        if (octets[0] == 10 or
                            (octets[0] == 172 and 16 <= octets[1] <= 31) or
                            (octets[0] == 192 and octets[1] == 168)):
                            return ip
            for adapter in adapters:
                ip_match = re.search(r'IPv4[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', adapter)
                if ip_match:
                    ip = ip_match.group(1)
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        return ip
        except:
            pass
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"
    else:
        try:
            result = subprocess.run(["ip", "-o", "addr", "show", "up"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and '127.0.0.1' not in line:
                        parts = line.strip().split()
                        for i, part in enumerate(parts):
                            if part == 'inet':
                                ip = parts[i+1].split('/')[0]
                                if not ip.startswith("172."):
                                    return ip
        except:
            pass
        try:
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
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
        self.server_dev_password = self.config.get_dev_password()
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

        manual_ip = self.config.get_manual_ip()
        if manual_ip:
            local_ip = manual_ip
            self.ui.print_info(f"Используется ручной IP: {local_ip}")
        else:
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
            stats = player_info.get("stats", {})
            dev_password = player_info.get("dev_password", "")
            is_dev = False
            if dev_password and self.server_dev_password and dev_password == self.server_dev_password:
                is_dev = True
                self.ui.print_success(f"Игрок {player_info.get('name')} вошёл как разработчик")
            self.clients[websocket] = {
                "name": player_info.get("name", "Unknown"),
                "character": player_info.get("character", ""),
                "color": player_info.get("color", "WHITE"),
                "stats": stats,
                "flags": [],
                "dev_mode": is_dev,
                "joined_at": datetime.now().isoformat(),
                "websocket": websocket
            }
            await self.broadcast({
                "type": "player_joined",
                "player_name": self.clients[websocket]["name"],
                "total_players": len(self.clients),
                "max_players": self.max_players
            })
            self.ui.print_success(f"Игрок {self.clients[websocket]['name']} подключился")
            await websocket.send(json.dumps({
                "type": "room_info",
                "room_name": self.room_name,
                "players": [{"name": info["name"]} for info in self.clients.values()],
                "mode": self.turn_mode,
                "game_started": self.game_started,
                "you_are_dev": is_dev
            }))
            if stats:
                await websocket.send(json.dumps({
                    "type": "stats_update",
                    "player_name": self.clients[websocket]["name"],
                    "stats": stats
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
            elif data["type"] == "player_command":
                await self.handle_player_command(websocket, data["command"])
        except json.JSONDecodeError:
            self.ui.print_error("Неверный формат сообщения")

    async def handle_player_command(self, websocket, command):
        parts = command.split()
        if not parts:
            return
        cmd = parts[0].lower()
        player_name = self.clients[websocket]["name"]
        if cmd == "/msg" and len(parts) >= 3:
            target = parts[1]
            text = " ".join(parts[2:])
            target_ws = None
            for ws, info in self.clients.items():
                if info["name"].lower() == target.lower():
                    target_ws = ws
                    break
            if target_ws:
                await target_ws.send(json.dumps({
                    "type": "private_message",
                    "from": player_name,
                    "text": text,
                    "player_color": self.clients[websocket]["color"]
                }))
                await websocket.send(json.dumps({
                    "type": "private_message",
                    "from": "Система",
                    "text": f"Вы -> {target}: {text}",
                    "player_color": "MAGENTA"
                }))
            else:
                await websocket.send(json.dumps({"type": "error", "message": "Игрок не найден"}))
        elif cmd == "/players":
            players_list = []
            for ws, info in self.clients.items():
                players_list.append({
                    "name": info["name"],
                    "character": info["character"],
                    "stats": info.get("stats", {}),
                    "flags": info.get("flags", [])
                })
            await websocket.send(json.dumps({"type": "players_list", "players": players_list}))
        elif cmd == "/stats":
            target = player_name
            if len(parts) > 1:
                target = parts[1]
            target_ws = None
            for ws, info in self.clients.items():
                if info["name"].lower() == target.lower():
                    target_ws = ws
                    break
            if target_ws:
                stats = self.clients[target_ws].get("stats", {})
                await websocket.send(json.dumps({
                    "type": "stats_display",
                    "player_name": target,
                    "stats": stats
                }))
            else:
                await websocket.send(json.dumps({"type": "error", "message": "Игрок не найден"}))
        else:
            await websocket.send(json.dumps({"type": "error", "message": "Неизвестная команда"}))

    async def process_game_message(self, websocket, content):
        player_name = self.clients[websocket]["name"]
        if player_name in self.jailed_players:
            await websocket.send(json.dumps({"type": "error", "message": "Вы заблокированы"}))
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
        prompt = self.build_ai_prompt(player_name, content)
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

    def build_ai_prompt(self, player_name, action, event_text=None):
        if event_text:
            return f"{self.narrator_prompt}\n\nМИР:\n{self.world_description}\n\nСОБЫТИЕ:\n{event_text}\n\nОпиши результат."
        context = f"{self.narrator_prompt}\n\nМИР ИГРЫ:\n{self.world_description}\n\n"
        for ws, info in self.clients.items():
            if info["name"] not in self.jailed_players:
                context += f"- {info['name']}: {info['character']}\n"
                stats = info.get("stats", {})
                if stats:
                    stats_str = ", ".join(f"{k}: {v}" for k, v in stats.items())
                    context += f"  Характеристики: {stats_str}\n"
        context += f"\nДЕЙСТВИЕ: {player_name} делает: {action}\n"
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
                        text = data.get("response", "")
                        # Мета-команды [[setstat:...]]
                        pattern = r'\[\[(.*?)\]\]'
                        for cmd_str in re.findall(pattern, text):
                            parts = cmd_str.split(':')
                            if len(parts) >= 4 and parts[0] == 'setstat':
                                target = parts[1]
                                stat = parts[2]
                                try:
                                    value = float(parts[3])
                                except ValueError:
                                    continue
                                for ws, info in self.clients.items():
                                    if info["name"].lower() == target.lower():
                                        if "stats" not in info:
                                            info["stats"] = {}
                                        info["stats"][stat] = value
                                        await self.broadcast({
                                            "type": "stats_update",
                                            "player_name": target,
                                            "stats": info["stats"]
                                        })
                                        break
                        text = re.sub(r'\[\[.*?\]\]', '', text).strip()
                        return text
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
        # Команды доступны, если это первый клиент (админ) или если у клиента есть флаг dev_mode
        if websocket != list(self.clients.keys())[0] and not self.clients[websocket].get("dev_mode", False):
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Только администратор или разработчик может использовать команды"
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
        elif cmd == "/event" and len(parts) >= 4:
            show = parts[-1].lower() == "true"
            event_name = parts[-2]
            event_text = " ".join(parts[1:-2])
            if show:
                await self.broadcast({"type": "event_announcement", "event_name": event_name, "text": event_text})
            prompt = self.build_ai_prompt(None, None, event_text=event_text)
            response = await self.get_ai_response(prompt)
            await self.broadcast({
                "type": "narrator_response",
                "from": "Событие",
                "action": event_name,
                "response": response,
                "player_color": "YELLOW"
            })
        elif cmd == "/setstat" and len(parts) >= 4:
            target = parts[1]
            stat = parts[2]
            try:
                value = float(parts[3])
            except ValueError:
                self.ui.print_error("Значение должно быть числом")
                return
            target_ws = None
            for ws, info in self.clients.items():
                if info["name"].lower() == target.lower():
                    target_ws = ws
                    break
            if not target_ws:
                self.ui.print_error(f"Игрок {target} не найден")
                return
            if "stats" not in self.clients[target_ws]:
                self.clients[target_ws]["stats"] = {}
            self.clients[target_ws]["stats"][stat] = value
            await self.broadcast({
                "type": "stats_update",
                "player_name": target,
                "stats": self.clients[target_ws]["stats"]
            })
            self.ui.print_success(f"Стат {stat} игрока {target} установлен в {value}")
        elif cmd == "/modstat" and len(parts) >= 4:
            target = parts[1]
            stat = parts[2]
            try:
                delta = float(parts[3])
            except ValueError:
                self.ui.print_error("Дельта должна быть числом")
                return
            target_ws = None
            for ws, info in self.clients.items():
                if info["name"].lower() == target.lower():
                    target_ws = ws
                    break
            if not target_ws:
                self.ui.print_error(f"Игрок {target} не найден")
                return
            if "stats" not in self.clients[target_ws]:
                self.clients[target_ws]["stats"] = {}
            current = self.clients[target_ws]["stats"].get(stat, 0)
            self.clients[target_ws]["stats"][stat] = current + delta
            await self.broadcast({
                "type": "stats_update",
                "player_name": target,
                "stats": self.clients[target_ws]["stats"]
            })
            self.ui.print_success(f"Стат {stat} игрока {target} изменён на {delta}")
        elif cmd == "/setflag" and len(parts) >= 3:
            target = parts[1]
            flag = parts[2]
            target_ws = None
            for ws, info in self.clients.items():
                if info["name"].lower() == target.lower():
                    target_ws = ws
                    break
            if not target_ws:
                self.ui.print_error("Игрок не найден")
                return
            if "flags" not in self.clients[target_ws]:
                self.clients[target_ws]["flags"] = []
            flags = self.clients[target_ws]["flags"]
            if flag.startswith("no"):
                flag_name = flag[2:]
                if flag_name in flags:
                    flags.remove(flag_name)
                    self.ui.print_success(f"Флаг {flag_name} снят с {target}")
            else:
                if flag not in flags:
                    flags.append(flag)
                    self.ui.print_success(f"Флаг {flag} добавлен {target}")
            await self.broadcast({
                "type": "flags_update",
                "player_name": target,
                "flags": flags
            })
        elif cmd == "/stats":
            if len(parts) > 1:
                target = parts[1]
                target_ws = None
                for ws, info in self.clients.items():
                    if info["name"].lower() == target.lower():
                        target_ws = ws
                        break
                if target_ws:
                    stats = self.clients[target_ws].get("stats", {})
                    await self.broadcast({"type": "stats_display", "player_name": target, "stats": stats})
                else:
                    self.ui.print_error("Игрок не найден")
            else:
                for ws, info in self.clients.items():
                    stats = info.get("stats", {})
                    if stats:
                        self.ui.print_colored(f"{info['name']}: {stats}", Fore.CYAN)
                    else:
                        self.ui.print_colored(f"{info['name']}: нет характеристик", Fore.CYAN)
        elif cmd == "/dev":
            if len(parts) < 2:
                self.ui.print_error("Укажите пароль")
                return
            if self.server_dev_password and parts[1] == self.server_dev_password:
                self.ui.print_success("Режим разработчика активирован в консоли сервера")
            else:
                self.ui.print_error("Неверный пароль или пароль не задан")
        elif cmd == "/help":
            self.show_help()
        else:
            self.ui.print_error("Неизвестная команда. /help для списка")

    def show_help(self):
        self.ui.print_info("Команды: /start, /stop, /kick, /jail, /unjail, /mode, /event")
        self.ui.print_info("  /setstat <игрок> <стат> <значение>")
        self.ui.print_info("  /modstat <игрок> <стат> <дельта>")
        self.ui.print_info("  /stats [игрок]")
        self.ui.print_info("  /setflag <игрок> <флаг>")
        self.ui.print_info("  /dev <пароль> - активировать режим разработчика в консоли сервера")

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

Начни игру с захватывающего вступления.
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
        elif msg_type == "event_announcement":
            self.ui.print_colored(f"⚠ СОБЫТИЕ: {message['event_name']}", Fore.YELLOW)
            self.ui.print_colored(f"{message['text']}", Fore.YELLOW)
        elif msg_type == "stats_update":
            stats = message.get("stats", {})
            self.ui.print_colored(f"Статы {message['player_name']}: {stats}", Fore.CYAN)
        elif msg_type == "stats_display":
            stats = message.get("stats", {})
            self.ui.print_colored(f"Статы {message['player_name']}: {stats}", Fore.CYAN)
        elif msg_type == "flags_update":
            self.ui.print_colored(f"Флаги {message['player_name']}: {message.get('flags', [])}", Fore.MAGENTA)

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