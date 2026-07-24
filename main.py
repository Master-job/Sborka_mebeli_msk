import asyncio
import random
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove
)

import config
from posts import POSTS

logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- Состояния Калькулятора (FSM) ---
class CalcState(StatesGroup):
    category = State()
    type_detail = State()
    size = State()
    photo_or_contact = State()

# --- Логика автопостинга ---
current_queue = []

def get_next_post():
    global current_queue
    if not current_queue:
        current_queue = POSTS.copy()
        random.shuffle(current_queue)
    return current_queue.pop()

async def send_random_post():
    post = get_next_post()
    
    keyboard_buttons = []
    for btn in post.get("buttons", []):
        keyboard_buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
    
    # Добавляем в каждый пост кнопку калькулятора!
    bot_info = await bot.get_me()
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="🧮 Рассчитать стоимость (Калькулятор)", 
            url=f"https://t.me/{bot_info.username}?start=calc"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

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
    while True:
        await send_random_post()
        await asyncio.sleep(config.POST_INTERVAL)

# --- ХЕНДЛЕРЫ КАЛЬКУЛЯТОРА ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚪 Шкаф / Гардеробная", callback_data="cat_wardrobe"),
            InlineKeyboardButton(text="🍳 Кухня", callback_data="cat_kitchen")
        ],
        [
            InlineKeyboardButton(text="🛏 Кровать / Спальня", callback_data="cat_bed"),
            InlineKeyboardButton(text="🛋 Другая мебель", callback_data="cat_other")
        ]
    ])
    
    text = (
        "👋 **Приветствуем!**\n\n"
        "Давайте быстро рассчитаем примерную стоимость сборки вашей мебели за 30 секунд.\n\n"
        "**Выберите категорию мебели:**"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)
    await state.set_state(CalcState.category)

# Шаг 1: Выбор категории
@dp.callback_query(CalcState.category, F.data.startswith("cat_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    cat_code = callback.data.split("_")[1]
    
    if cat_code == "wardrobe":
        await state.update_data(category="Шкаф / Гардеробная")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚪 Шкаф-купе", callback_data="type_coupe")],
            [InlineKeyboardButton(text="🚪 Распашной шкаф", callback_data="type_swing")],
            [InlineKeyboardButton(text="📦 ИКЕА ПАКС / Гардеробная", callback_data="type_pax")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
        ])
        text = "Отлично! Какой у вас тип шкафа?"
    elif cat_code == "bed":
        await state.update_data(category="Кровать / Спальня")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛏 Обычная кровать", callback_data="type_bed_std")],
            [InlineKeyboardButton(text="🛏 С подъемным механизмом", callback_data="type_bed_lift")],
            [InlineKeyboardButton(text="🧸 Детская / Двухъярусная", callback_data="type_bed_kids")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
        ])
        text = "Укажите тип кровати:"
    else:
        # Для кухонь или прочего
        await state.update_data(category="Кухня / Другое", type_detail="Стандартный монтаж", est_price="от 2 000 до 5 000 руб.")
        await ask_contact_step(callback.message, state)
        await callback.answer()
        return

    await state.set_state(CalcState.type_detail)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# Кнопка "Назад"
@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery, state: FSMContext):
    await cmd_start(callback.message, state)
    await callback.answer()

# Шаг 2: Уточнение типа шкафа / кровати
@dp.callback_query(CalcState.type_detail, F.data.startswith("type_"))
async def process_type(callback: types.CallbackQuery, state: FSMContext):
    type_code = callback.data.split("_")[1]
    
    data = await state.get_data()
    category = data.get("category")
    
    if "wardrobe" in category.lower() or type_code in ["coupe", "swing", "pax"]:
        type_names = {
            "coupe": "Шкаф-купе",
            "swing": "Распашной шкаф",
            "pax": "ИКЕА ПАКС / Гардеробная"
        }
        await state.update_data(type_detail=type_names.get(type_code, "Шкаф"))
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="2 двери", callback_data="size_2")],
            [InlineKeyboardButton(text="3 двери", callback_data="size_3")],
            [InlineKeyboardButton(text="4 двери и более", callback_data="size_4")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")]
        ])
        text = "Укажите количество дверей у шкафа:"
        await state.set_state(CalcState.size)
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        bed_types = {
            "std": ("Кровать стандарт", "1 800 – 2 500 руб."),
            "lift": ("Кровать с подъемным механизмом", "2 500 – 3 500 руб."),
            "kids": ("Детская / Двухъярусная кровать", "2 500 – 4 000 руб.")
        }
        name, price = bed_types.get(type_code, ("Кровать", "от 2 000 руб."))
        await state.update_data(type_detail=name, est_price=price)
        await ask_contact_step(callback.message, state)

    await callback.answer()

# Шаг 3: Размер шкафа
@dp.callback_query(CalcState.size, F.data.startswith("size_"))
async def process_size(callback: types.CallbackQuery, state: FSMContext):
    size_code = callback.data.split("_")[1]
    
    price_map = {
        "2": ("2 двери", "2 000 – 2 800 руб."),
        "3": ("3 двери", "2 800 – 3 800 руб."),
        "4": ("4+ дверей", "3 800 – 5 500 руб.")
    }
    size_str, price = price_map.get(size_code, ("Стандарт", "от 2 500 руб."))
    await state.update_data(size=size_str, est_price=price)
    
    await ask_contact_step(callback.message, state)
    await callback.answer()

# Переход к финалу
async def ask_contact_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    category = data.get("category", "")
    type_detail = data.get("type_detail", "")
    size = data.get("size", "")
    est_price = data.get("est_price", "по договоренности")
    
    text = (
        "📊 **Предварительный расчет готов!**\n\n"
        f"🔹 **Категория:** {category}\n"
        f"🔹 **Детали:** {type_detail} {f'({size})' if size else ''}\n"
        f"💰 **Ориентировочная стоимость:** {est_price}\n\n"
        "Чтобы зафиксировать цену или получить точную оценку:\n"
        "📸 **Отправьте сюда фото / ссылку на мебель**\n"
        "или нажмите кнопку ниже, чтобы передать контакт мастеру!"
    )
    
    # Reply-кнопка для отправки телефона (по желанию)
    btn_phone = KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)
    reply_kb = ReplyKeyboardMarkup(keyboard=[[btn_phone]], resize_keyboard=True, one_time_keyboard=True)
    
    await message.answer(text, parse_mode="Markdown", reply_markup=reply_kb)
    await state.set_state(CalcState.photo_or_contact)

# Прием ответа (фото, текст или контакт)
@dp.message(CalcState.photo_or_contact)
async def process_final_step(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    user = message.from_user
    username = f"@{user.username}" if user.username else "Нет юзернейма"
    
    phone = message.contact.phone_number if message.contact else "Не указан (написал текстом/фото)"
    user_text = message.text if message.text else ""
    
    admin_card = (
        "🔔 **НОВАЯ ЗАЯВКА ИЗ КАЛЬКУЛЯТОРА!**\n\n"
        f"👤 **Клиент:** {user.full_name} ({username})\n"
        f"📱 **Телефон:** {phone}\n"
        f"🛠 **Услуга:** {data.get('category')} - {data.get('type_detail')} {data.get('size', '')}\n"
        f"💰 **Оценка бота:** {data.get('est_price')}\n"
    )
    if user_text:
        admin_card += f"💬 **Сообщение от клиента:** {user_text}\n"
        
    # Отправка уведомления администратору (в CHAT_ID)
    try:
        if message.photo:
            await bot.send_photo(chat_id=config.CHAT_ID, photo=message.photo[-1].file_id, caption=admin_card, parse_mode="Markdown")
        else:
            await bot.send_message(chat_id=config.CHAT_ID, text=admin_card, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить заявку в чат: {e}")

    await message.answer(
        "✅ **Заявка принята!**\n\nМастер уже изучает детали и свяжется с вами в течение 5–10 минут для уточнения точного времени выезда.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

# --- Веб-сервер для Render ---
async def handle_ping(request):
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
    await start_web_server()
    asyncio.create_task(poster_loop())
    # Включаем обратно polling, чтобы бот мог общаться с людьми
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())