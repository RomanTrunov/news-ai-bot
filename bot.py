import asyncio
import logging
import ssl
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp
import certifi

API_TOKEN = '7499225728:AAFfpBDui6ha0BamoB-Nztwl0jy9oe9hC_0'
NEWS_API_KEY = 'b16b1ce1082f4b85872fa73e39396c05'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class UserState(StatesGroup):
    choosing_topic = State()
    choosing_hour = State()


topics = ['ИИ', 'Машинное обучение', 'Глубокое обучение', 'Нейронные сети', 'Компьютерное зрение']
hours = ['9', '12', '15', '18', '21']


@dp.message(Command(commands=['start', 'help']))
async def send_welcome(message: Message, state: FSMContext):
    await show_topic_selection(message, state)


async def show_topic_selection(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=topic)] for topic in topics], resize_keyboard=True)
    await message.reply("Выберите тему:", reply_markup=keyboard)
    await state.set_state(UserState.choosing_topic)


@dp.message(UserState.choosing_topic)
async def process_topic(message: Message, state: FSMContext):
    if message.text not in topics:
        await message.reply("Пожалуйста, выберите тему из предложенных на клавиатуре.")
        return

    await state.update_data(chosen_topic=message.text)

    keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=hour)] for hour in hours], resize_keyboard=True)
    await message.reply("В какой час вы хотите получать свежие новости?", reply_markup=keyboard)
    await state.set_state(UserState.choosing_hour)


@dp.message(UserState.choosing_hour)
async def process_hour(message: Message, state: FSMContext):
    if message.text not in hours:
        await message.reply("Пожалуйста, выберите час из предложенных на клавиатуре.")
        return

    user_data = await state.get_data()
    await state.update_data(chosen_hour=message.text)

    topic = user_data['chosen_topic']
    hour = message.text

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Получить новости сейчас", callback_data="get_news_now")]
    ])

    await message.reply(
        f"Отлично! Вы будете получать новости о теме '{topic}' в {hour}:00.",
        reply_markup=keyboard
    )

    asyncio.create_task(send_periodic_news(message.chat.id, topic, int(hour)))


async def fetch_news(topic):
    url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={NEWS_API_KEY}&language=ru&pageSize=5"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, ssl=ssl_context) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['articles']
                else:
                    logging.error(f"Ошибка при получении новостей: {response.status}")
                    return []
    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        return []


async def send_periodic_news(chat_id, topic, hour):
    while True:
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        await asyncio.sleep((next_run - now).total_seconds())

        try:
            articles = await fetch_news(topic)
            if articles:
                for article in articles:
                    message = f"<b>{article['title']}</b>\n\n{article['description']}\n\n<a href='{article['url']}'>Читать далее</a>"
                    await bot.send_message(chat_id, message, parse_mode="HTML")
            else:
                await bot.send_message(chat_id, f"Новости по теме '{topic}' не найдены")
        except Exception as e:
            logging.error(f"Ошибка при отправке новостей: {e}")

        # Отправляем новости только один раз
        break


@dp.callback_query(lambda c: c.data == 'get_news_now')
async def get_news_now_callback(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if 'chosen_topic' in user_data:
        topic = user_data['chosen_topic']
        articles = await fetch_news(topic)
        if articles:
            for article in articles:
                message_text = f"<b>{article['title']}</b>\n\n{article['description']}\n\n<a href='{article['url']}'>Читать далее</a>"
                await bot.send_message(callback_query.from_user.id, message_text, parse_mode="HTML")
        else:
            await bot.send_message(callback_query.from_user.id, f"Новости по теме '{topic}' не найдены")
    else:
        await bot.send_message(callback_query.from_user.id,
                               "Произошла ошибка. Пожалуйста, используйте /start, чтобы настроить предпочтения заново.")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать другую тему", callback_data="select_new_topic")]
    ])
    await bot.send_message(callback_query.from_user.id, "Что вы хотите сделать дальше?", reply_markup=keyboard)
    await callback_query.answer()


@dp.callback_query(lambda c: c.data == 'select_new_topic')
async def select_new_topic_callback(callback_query: CallbackQuery, state: FSMContext):
    await show_topic_selection(callback_query.message, state)
    await callback_query.answer()


@dp.message()
async def echo(message: Message):
    await message.reply(
        "Я не понимаю эту команду. Используйте /start, чтобы настроить предпочтения новостей, или /help для получения информации.")


async def main():
    # Запуск бота
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
