"""
config.py – Управление настройками, персонажами, мирами, характеристиками, друзьями
"""
import json
import os
from pathlib import Path

class Config:
    def __init__(self):
        self.data_dir = Path("./data")
        self.settings_file = self.data_dir / "settings.json"
        self.characters_dir = self.data_dir / "characters"
        self.worlds_dir = self.data_dir / "worlds"
        self.stats_template_file = self.data_dir / "stats_template.json"
        self.friends_file = self.data_dir / "friends.json"
        self.ensure_directories()
        self.settings = self.load_settings()
        self.migrate_character_text()

    def ensure_directories(self):
        self.data_dir.mkdir(exist_ok=True)
        self.characters_dir.mkdir(exist_ok=True)
        self.worlds_dir.mkdir(exist_ok=True)

    def load_settings(self):
        default_settings = {
            "ollama": {
                "model": "gemma4:31b-cloud",
                "temperature": 0.7,
                "narrator_prompt": (
                    "You are a creative RPG narrator. "
                    "If a character takes damage, heals, or earns money, "
                    "insert [[setstat:CharacterName:stat:value]] in your response, "
                    "then remove it from the visible text."
                )
            },
            "player_character_file": "",
            "player_color": "WHITE",
            "dev_password": "",
            "allow_friend_requests": True,
            "coordinator": {
                "address": "ws://localhost:8770",
                "use_public": False
            },
            "network": {
                "host": "localhost",
                "port": 8765,
                "manual_ip": ""
            }
        }
        if self.settings_file.exists():
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for key, value in default_settings.items():
                    if key not in loaded:
                        loaded[key] = value
                return loaded
        else:
            self.save_settings(default_settings)
            return default_settings

    def save_settings(self, settings=None):
        if settings:
            self.settings = settings
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)

    def migrate_character_text(self):
        old_text = self.settings.pop("player_character", None)
        if old_text and not self.settings.get("player_character_file"):
            name = "_migrated_character"
            self.save_character(name, old_text)
            self.settings["player_character_file"] = name
            self.save_settings()

    # ---------- Ollama ----------
    def update_ollama_settings(self, model=None, temperature=None, prompt=None):
        if model:
            self.settings["ollama"]["model"] = model
        if temperature is not None:
            self.settings["ollama"]["temperature"] = float(temperature)
        if prompt:
            self.settings["ollama"]["narrator_prompt"] = prompt
        self.save_settings()

    # ---------- Сеть ----------
    def set_manual_ip(self, ip):
        self.settings["network"]["manual_ip"] = ip.strip()
        self.save_settings()

    def get_manual_ip(self):
        return self.settings["network"].get("manual_ip", "")

    def get_coordinator_address(self):
        return self.settings.get("coordinator", {}).get("address", "ws://localhost:8770")

    def set_coordinator_address(self, addr):
        if "coordinator" not in self.settings:
            self.settings["coordinator"] = {}
        self.settings["coordinator"]["address"] = addr.strip()
        self.save_settings()

    def get_use_public(self):
        return self.settings.get("coordinator", {}).get("use_public", False)

    def set_use_public(self, value):
        if "coordinator" not in self.settings:
            self.settings["coordinator"] = {}
        self.settings["coordinator"]["use_public"] = value
        self.save_settings()

    # ---------- Персонаж (файловая ссылка) ----------
    def set_player_character_file(self, file_name):
        self.settings["player_character_file"] = file_name
        self.save_settings()

    def get_player_character_file(self):
        return self.settings.get("player_character_file", "")

    def load_player_character_text(self):
        file_name = self.get_player_character_file()
        if file_name:
            return self.load_character(file_name)
        return ""

    # ---------- Управление персонажами (текст) ----------
    def list_characters(self):
        files = list(self.characters_dir.glob("*.txt")) + list(self.characters_dir.glob("*.md"))
        names = {f.stem for f in files}
        return sorted(names)

    def load_character(self, name):
        for ext in ('.txt', '.md'):
            path = self.characters_dir / (name + ext)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        return None

    def save_character(self, name, content):
        path = self.characters_dir / (name + ".txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_character(self, name):
        for ext in ('.txt', '.md'):
            path = self.characters_dir / (name + ext)
            if path.exists():
                os.remove(path)
                return True
        return False

    # ---------- Характеристики персонажей ----------
    def get_character_stats(self, name):
        path = self.characters_dir / (name + ".stats.json")
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_character_stats(self, name, stats):
        path = self.characters_dir / (name + ".stats.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def delete_character_stats(self, name):
        path = self.characters_dir / (name + ".stats.json")
        if path.exists():
            os.remove(path)

    # ---------- Шаблон характеристик ----------
    def load_stats_template(self):
        if self.stats_template_file.exists():
            with open(self.stats_template_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            default = {"hp": 100, "mana": 50, "money": 0}
            self.save_stats_template(default)
            return default

    def save_stats_template(self, template):
        with open(self.stats_template_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)

    # ---------- Пароль разработчика ----------
    def get_dev_password(self):
        return self.settings.get("dev_password", "")

    def set_dev_password(self, pwd):
        self.settings["dev_password"] = pwd
        self.save_settings()

    # ---------- Друзья ----------
    def load_friends(self):
        if self.friends_file.exists():
            with open(self.friends_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_friends(self, friends):
        with open(self.friends_file, 'w', encoding='utf-8') as f:
            json.dump(friends, f, indent=2, ensure_ascii=False)

    def add_friend(self, nickname, ip):
        friends = self.load_friends()
        friends[nickname] = ip
        self.save_friends(friends)

    def remove_friend(self, nickname):
        friends = self.load_friends()
        if nickname in friends:
            del friends[nickname]
            self.save_friends(friends)
            return True
        return False

    def get_friends(self):
        return self.load_friends()

    # ---------- Управление мирами ----------
    def list_worlds(self):
        files = list(self.worlds_dir.glob("*.txt")) + list(self.worlds_dir.glob("*.md"))
        names = {f.stem for f in files}
        return sorted(names)

    def load_world(self, name):
        for ext in ('.txt', '.md'):
            path = self.worlds_dir / (name + ext)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        return None

    def save_world(self, name, content):
        path = self.worlds_dir / (name + ".txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_world(self, name):
        for ext in ('.txt', '.md'):
            path = self.worlds_dir / (name + ext)
            if path.exists():
                os.remove(path)
                return True
        return False