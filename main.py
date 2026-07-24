import asyncio
import random
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from posts import POSTS

logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Копия списка постов для работы по принципу "Shuffle Queue"
current_queue = []

def get_next_post():
    """Берет следующий пост без частых повторов"""
    global current_queue
    if not current_queue:
        current_queue = POSTS.copy()
        random.shuffle(current_queue)
    return current_queue.pop()

async def send_random_post():
    """Формирует и отправляет пост в канал"""
    post = get_next_post()
    
    # Сборка инлайн-кнопок
    keyboard_buttons = []
    for btn in post.get("buttons", []):
        keyboard_buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons) if keyboard_buttons else None

    try:
        if post.get("photo"):
            await bot.send_photo(
                chat_id=config.CHAT_ID,
                photo=post["photo"],
                caption=post["text"],
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await bot.send_message(
                chat_id=config.CHAT_ID,
                text=post["text"],
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        logging.info("Объявление успешно опубликовано!")
    except Exception as e:
        logging.error(f"Ошибка при отправке поста: {e}")

async def poster_loop():
    """Фоновый цикл, отправляющий посты по расписанию"""
    while True:
        await send_random_post()
        await asyncio.sleep(config.POST_INTERVAL)

# --- Веб-сервер для поддержки Render ---
async def handle_ping(request):
    """Эндпоинт для внешнего крона (cron-job.org / uptimerobot)"""
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {config.PORT}")

async def main():
    # Запускаем веб-сервер для пинга
    await start_web_server()
    
    # Запускаем фоновую рассылку
    asyncio.create_task(poster_loop())
    
    # Запускаем поллинг (если захочешь добавить команды боту)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())