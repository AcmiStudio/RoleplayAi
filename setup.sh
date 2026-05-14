#!/bin/bash

# setup.sh – Установка RPG Chat в Termux
# Запуск: bash setup.sh

echo "=============================================="
echo "  Установка RPG Chat для Termux"
echo "=============================================="

# 1. Обновление пакетов Termux
echo ""
echo "[1/5] Обновление пакетов..."
pkg update -y && pkg upgrade -y

# 2. Установка Python и pip
echo ""
echo "[2/5] Установка Python, Ollama..."
pkg install python -y
pkg install iproute2 -y
pkg install ollama -y
# 3. Установка Python-зависимостей через pip
echo ""
echo "[3/5] Установка Python-модулей (websockets, colorama, aiohttp)..."
pip install --upgrade pip
pip install websockets colorama aiohttp websockets

# 4. Создание структуры папок и settings.json по умолчанию
echo ""
echo "[4/5] Создание структуры папок и базовых настроек..."
mkdir -p data/characters
mkdir -p data/worlds

SETTINGS_FILE="data/settings.json"
if [ ! -f "$SETTINGS_FILE" ]; then
    cat > "$SETTINGS_FILE" <<EOF
{
  "ollama": {
    "model": "gemma4:31b-cloud",
    "temperature": 0.7,
    "narrator_prompt": "You are a creative RPG narrator..."
  },
  "player_character": "",
  "player_color": "WHITE",
  "network": {
    "host": "localhost",
    "port": 8765
  }
}
EOF
    echo "   Создан $SETTINGS_FILE"
else
    echo "   Файл $SETTINGS_FILE уже существует, пропускаем."
fi

# 5. Проверка Ollama (опционально)
echo ""
echo "[5/5] Проверка Ollama..."
if command -v ollama &> /dev/null; then
    echo "   Ollama установлена. Войдите в систему Ollama"
    echo "   Внимание! После того как пропишите ollama serve, в другой сессии запустите приложение."
    echo "   Рекомендуется загрузить модель (если ещё не):"
    echo "   ollama pull gemma4:31b-cloud  (или ваша модель)"
else
    echo "   Ollama не найдена в Termux."
    echo "   Для работы ИИ-рассказчика необходим сервер Ollama."
    echo "   Вы можете запустить его на другом устройстве и указать"
    echo "   адрес в коде сервера (пока что настроено на localhost:11434)."
    
fi

echo ""
echo "=============================================="
echo "  Установка завершена!"
echo "  Запустите игру: python main.py"
echo "=============================================="