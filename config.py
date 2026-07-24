import os

# Токен бота из @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")

# ID твоего канала/чата (например: -100123456789 или @my_channel_username)
CHAT_ID = os.getenv("CHAT_ID", "@твой_канал")

# Интервал публикации в секундах (3600 сек = 1 час)
POST_INTERVAL = int(os.getenv("POST_INTERVAL", 3600))

# Порт для веб-сервера Render
PORT = int(os.getenv("PORT", 8080))