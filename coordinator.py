"""
coordinator.py – Центральный сервер-координатор публичных комнат (исправленный)
Запуск: python coordinator.py
"""
import asyncio
import json
import websockets
from datetime import datetime

rooms = {}

async def handler(websocket):
    try:
        async for message in websocket:
            data = json.loads(message)
            action = data.get("action")
            if action == "register":
                room_id = f"{data['ip']}:{data['port']}"
                rooms[room_id] = {
                    "room_name": data["room_name"],
                    "ip": data["ip"],
                    "port": data["port"],
                    "network_type": data.get("network_type", "?"),
                    "players": data.get("players", 0),
                    "max_players": data.get("max_players", 4),
                    "game_started": data.get("game_started", False),
                    "last_update": datetime.now().isoformat()
                }
                await websocket.send(json.dumps({"status": "ok", "room_id": room_id}))
            elif action == "update":
                room_id = f"{data['ip']}:{data['port']}"
                if room_id in rooms:
                    rooms[room_id].update({
                        "players": data.get("players", rooms[room_id]["players"]),
                        "game_started": data.get("game_started", rooms[room_id]["game_started"]),
                        "last_update": datetime.now().isoformat()
                    })
                await websocket.send(json.dumps({"status": "updated"}))
            elif action == "unregister":
                room_id = f"{data['ip']}:{data['port']}"
                rooms.pop(room_id, None)
                await websocket.send(json.dumps({"status": "unregistered"}))
            elif action == "list":
                now = datetime.now()
                for rid in list(rooms.keys()):
                    last = datetime.fromisoformat(rooms[rid]["last_update"])
                    if (now - last).total_seconds() > 30:
                        del rooms[rid]
                await websocket.send(json.dumps({
                    "type": "public_rooms_list",
                    "rooms": list(rooms.values())
                }))
    except websockets.exceptions.ConnectionClosed:
        pass

async def main():
    print("Координатор запущен на ws://0.0.0.0:8770")
    async with websockets.serve(handler, "0.0.0.0", 8770):
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nКоординатор остановлен")