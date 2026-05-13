"""
config.py - Управление настройками, персонажами и мирами
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
        self.ensure_directories()
        self.settings = self.load_settings()

    def ensure_directories(self):
        self.data_dir.mkdir(exist_ok=True)
        self.characters_dir.mkdir(exist_ok=True)
        self.worlds_dir.mkdir(exist_ok=True)

    def load_settings(self):
        default_settings = {
            "ollama": {
                "model": "gemma4:31b-cloud",
                "temperature": 0.7,
                "narrator_prompt": "You are a creative RPG narrator..."
            },
            "player_character": "",
            "player_color": "WHITE",   # цвет игрока (название цвета из Fore)
            "network": {
                "host": "localhost",
                "port": 8765
            }
        }
        if self.settings_file.exists():
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Объединяем с дефолтными, чтобы не потерять новые ключи
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

    # ---------- Настройки Ollama ----------
    def update_ollama_settings(self, model=None, temperature=None, prompt=None):
        if model:
            self.settings["ollama"]["model"] = model
        if temperature is not None:
            self.settings["ollama"]["temperature"] = float(temperature)
        if prompt:
            self.settings["ollama"]["narrator_prompt"] = prompt
        self.save_settings()

    # ---------- Управление персонажами ----------
    def list_characters(self):
        """Возвращает список файлов персонажей (без расширения)"""
        files = list(self.characters_dir.glob("*"))
        return sorted([f.stem for f in files if f.suffix in ('.txt', '.md')])

    def load_character(self, name):
        """Загружает текст персонажа по имени файла (без расширения)"""
        for ext in ('.txt', '.md'):
            path = self.characters_dir / (name + ext)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        return None

    def save_character(self, name, content):
        """Сохраняет персонажа в файл .txt"""
        path = self.characters_dir / (name + ".txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def delete_character(self, name):
        """Удаляет файл персонажа (если существует)"""
        for ext in ('.txt', '.md'):
            path = self.characters_dir / (name + ext)
            if path.exists():
                os.remove(path)
                return True
        return False

    # ---------- Управление мирами ----------
    def list_worlds(self):
        """Возвращает список файлов миров (без расширения)"""
        files = list(self.worlds_dir.glob("*"))
        return sorted([f.stem for f in files if f.suffix in ('.txt', '.md')])

    def load_world(self, name):
        """Загружает текст мира по имени файла (без расширения)"""
        for ext in ('.txt', '.md'):
            path = self.worlds_dir / (name + ext)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        return None

    def save_world(self, name, content):
        """Сохраняет мир в файл .txt"""
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