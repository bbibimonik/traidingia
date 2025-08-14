import asyncio
import logging
import json
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from binance_data import fetch_all_metrics
import google.generativeai as genai

# 🔐 Переменные окружения
TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not TOKEN or not GOOGLE_API_KEY:
    raise ValueError("❌ BOT_TOKEN и GOOGLE_API_KEY должны быть заданы в переменных окружения.")

# Настройка Gemini API
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-pro')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

HISTORY_FILE = 'ai_advice_history.json'
ai_advice_history = {}

# ===== Функции истории =====
def load_history():
    global ai_advice_history
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            ai_advice_history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ai_advice_history = {}

def save_history():
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(ai_advice_history, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logging.error(f"Ошибка записи истории: {e}")

# ===== Меню =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Выбрать монету", callback_data="choose_coin")],
        [InlineKeyboardButton(text="🧠 ИИ совет", callback_data="generate_idea")],
        [InlineKeyboardButton(text="📜 История советов", callback_data="show_history")]
    ])

def coin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="BTC", callback_data="coin_BTC"),
         InlineKeyboardButton(text="ETH", callback_data="coin_ETH"),
         InlineKeyboardButton(text="SOL", callback_data="coin_SOL")],
        [InlineKeyboardButton(text="BNB", callback_data="coin_BNB"),
         InlineKeyboardButton(text="XRP", callback_data="coin_XRP"),
         InlineKeyboardButton(text="DOGE", callback_data="coin_DOGE")],
        [InlineKeyboardButton(text="ADA", callback_data="coin_ADA"),
         InlineKeyboardButton(text="LINK", callback_data="coin_LINK"),
         InlineKeyboardButton(text="DOT", callback_data="coin_DOT")],
        [InlineKeyboardButton(text="AVAX", callback_data="coin_AVAX"),
         InlineKeyboardButton(text="SHIB", callback_data="coin_SHIB")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back")]
    ])

# ===== Состояние =====
user_state = {}

# ===== Команды =====
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer("👋 Привет! Я крипто-помощник. Выбери монету и сгенерируй торговую идею.", reply_markup=main_menu())

@dp.callback_query(F.data == "show_history")
async def show_history_callback(call: CallbackQuery):
    user_id = str(call.from_user.id)
    history_for_user = ai_advice_history.get(user_id)

    if not history_for_user:
        await call.message.edit_text("📜 Ваша история советов пуста.", reply_markup=main_menu())
        return

    history_text = "📜 <b>Ваша история советов:</b>\n\n"
    start_index = max(0, len(history_for_user) - 5)
    for i, entry in enumerate(history_for_user[start_index:], 1):
        history_text += (
            f"--- Совет #{i} ---\n"
            f"📅 {entry['timestamp']}\n"
            f"💰 {entry['coin']}\n"
            f"🧠 {entry['advice']}\n\n"
        )

    await call.message.edit_text(history_text, reply_markup=main_menu())

# ===== Генерация совета =====
async def generate_ai_advice(coin: str, metrics: dict) -> str:
    for key, value in metrics.items():
        if value is None:
            metrics[key] = 0.0

    prompt = (
        f"Ты криптоаналитик. Проанализируй данные по {coin} и дай краткий план:\n"
        f"- Цена: {metrics['current_price']:.2f}\n"
        f"- OI: {metrics['open_interest']:.2f}\n"
        f"- Funding Rate: {metrics['funding_rate']:.5f}\n"
        f"- Taker Buy: {metrics['taker_buy_volume']:.2f}\n"
        f"- Taker Sell: {metrics['taker_sell_volume']:.2f}\n"
        f"- Long/Short Ratio: {metrics['long_short_ratio']:.2f}\n"
        f"- Fear/Greed: {metrics['fear_greed_index_value']} ({metrics['fear_greed_index_grade']})"
    )
    try:
        response = await model.generate_content_async(prompt)
        return response.text if response.text else "ИИ не смог сгенерировать совет."
    except Exception as e:
        logging.error(f"Ошибка Gemini API: {e}")
        return "Ошибка генерации совета."

@dp.callback_query()
async def handle_callback(call: CallbackQuery):
    data = call.data
    user_id = str(call.from_user.id)

    if data == "choose_coin":
        await call.message.edit_text("Выбери монету:", reply_markup=coin_menu())

    elif data.startswith("coin_"):
        coin = data.split("_")[1]
        user_state[user_id] = {"coin": coin}
        await call.message.edit_text(f"✅ Монета выбрана: {coin}", reply_markup=main_menu())

    elif data == "back":
        await call.message.edit_text("Главное меню:", reply_markup=main_menu())

    elif data == "generate_idea":
        coin = user_state.get(user_id, {}).get("coin")
        if not coin:
            await call.message.answer("⚠️ Сначала выбери монету.")
            return

        await call.message.answer(f"⏳ Получаю данные по {coin}...")
        metrics = await fetch_all_metrics(coin)
        if not metrics:
            await call.message.answer("❌ Ошибка получения данных.")
            return

        advice = await generate_ai_advice(coin, metrics)
        await call.message.answer(f"📊 {coin}\n🧠 {advice}", reply_markup=main_menu())

        if user_id not in ai_advice_history:
            ai_advice_history[user_id] = []
        ai_advice_history[user_id].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "coin": coin,
            "advice": advice
        })
        save_history()

# ===== Запуск =====
async def main():
    logging.basicConfig(level=logging.INFO)
    load_history()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

