import asyncio
import logging
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton # Импортируем InlineKeyboardMarkup и InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from binance_data import fetch_all_metrics # Убедись, что fetch_all_metrics теперь возвращает цену

import google.generativeai as genai

# 🔐 Укажи токен своего бота
TOKEN = '7244165248:AAG4HAz9lm5y4zkfYjmGn4zmeYp6P_duFrE'

# 🔑 Укажи свой API ключ Gemini
GOOGLE_API_KEY = "AIzaSyAOoQAVUe1Ytfu_DRDB_Z6PxqtRrsXtPu0" # <--- ЗАМЕНИ НА СВОЙ КЛЮЧ

# Настройка Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# Инициализация модели Gemini
model = genai.GenerativeModel('models/gemini-2.5-pro')

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Файл для хранения истории
HISTORY_FILE = 'ai_advice_history.json'
# Глобальная переменная для хранения истории в оперативной памяти
# Структура: {user_id: [{timestamp: ..., coin: ..., metrics: ..., advice: ...}, ...]}
ai_advice_history = {}

# --- НОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С ИСТОРИЕЙ ---

def load_history():
    """Загружает историю советов из JSON-файла."""
    global ai_advice_history
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            ai_advice_history = json.load(f)
            logging.info(f"История советов загружена из {HISTORY_FILE}")
    except FileNotFoundError:
        logging.warning(f"Файл истории {HISTORY_FILE} не найден. Создаем новую.")
        ai_advice_history = {}
    except json.JSONDecodeError:
        logging.error(f"Ошибка чтения JSON из {HISTORY_FILE}. Файл поврежден или пуст.")
        ai_advice_history = {} # Очищаем историю, чтобы избежать дальнейших ошибок

def save_history():
    """Сохраняет историю советов в JSON-файл."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(ai_advice_history, f, ensure_ascii=False, indent=4)
            logging.info(f"История советов сохранена в {HISTORY_FILE}")
    except IOError as e:
        logging.error(f"Ошибка записи истории в {HISTORY_FILE}: {e}")

# --- КОНЕЦ НОВЫХ ФУНКЦИЙ ---

# Состояние пользователя
user_state = {}

# 📍 Главное меню
def main_menu():
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Выбрать монету", callback_data="choose_coin")],
        [InlineKeyboardButton(text="🧠 ИИ совет", callback_data="generate_idea")],
        [InlineKeyboardButton(text="📜 История советов", callback_data="show_history")]
    ])
    return builder

# 📍 Меню выбора монеты
def coin_menu():
    # Расширенный список монет
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
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
    return keyboard

# 👋 Команда /start
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я крипто-помощник. Выбери монету и сгенерируй торговую идею.",
        reply_markup=main_menu()
    )

# НОВАЯ ФУНКЦИЯ: Показать историю советов
@dp.callback_query(F.data == "show_history")
async def show_history_callback(call: CallbackQuery):
    user_id = str(call.from_user.id)
    history_for_user = ai_advice_history.get(user_id)

    if not history_for_user:
        await call.message.edit_text("📜 Ваша история советов пуста.", reply_markup=main_menu())
        return

    history_text = "📜 <b>Ваша история советов:</b>\n\n"
    # Показываем последние 5 советов, чтобы не перегружать сообщение
    start_index = max(0, len(history_for_user) - 5)
    for i, entry in enumerate(history_for_user[start_index:], 1):
        history_text += (
            f"--- Совет #{i} ---\n"
            f"📅 Дата: {entry['timestamp']}\n"
            f"💰 Монета: {entry['coin']}\n"
            f"🧠 Совет:\n{entry['advice']}\n\n"
        )

    if len(history_for_user) > 5:
        history_text += f"Показаны последние 5 из {len(history_for_user)} советов.\n"

    # Разделяем сообщение, если оно слишком длинное (Telegram имеет лимит 4096 символов)
    # Используем edit_text, чтобы обновить текущее сообщение, из которого вызвали историю
    if len(history_text) > 4000:
        await call.message.edit_text("📜 <b>Ваша история советов:</b> (слишком длинная, показана часть)\n", reply_markup=main_menu())
        # Отправляем остальные части отдельными сообщениями
        for chunk in [history_text[i:i+4000] for i in range(0, len(history_text), 4000)][1:]: # Начинаем со второго чанка
            await call.message.answer(chunk)
    else:
        await call.message.edit_text(history_text, reply_markup=main_menu())


# --- ФУНКЦИЯ ГЕНЕРАЦИИ СОВЕТА ИИ (ОБНОВЛЕННЫЙ ПРОМПТ) ---
async def generate_ai_advice(coin: str, metrics: dict) -> str:
    for key, value in metrics.items():
        if value is None:
            metrics[key] = 0.0

    prompt = (
        f"Ты опытный криптоаналитик, специализирующийся на фьючерсных рынках. "
        f"Проанализируй следующие метрики по криптовалюте {coin} и предложи КОНКРЕТНЫЙ торговый план для кратковроеменной сделки, метрики используются 15 минутные. "
        "Твой совет должен быть кратким (не более 4-5 предложений) и содержать:\n"
        "1. **Тип сделки:** (Например, 'Покупка', 'Продажа', 'Удержание').\n"
        "2. **Рекомендуемая точка входа:** (Числовое значение, максимально приближенное к текущей цене, но с учетом логики).\n"
        "3. **Рекомендуемый Стоп-Лосс (SL):** (Числовое значение, для ограничения убытков).\n"
        "4. **Рекомендуемый Тейк-Профит (TP):** (Числовое значение, для фиксации прибыли).\n"
        "Поясни свой выбор, основываясь на представленных данных. "
        "Используй русский язык и отвечай в структурированном виде, примерно как в примере ниже:\n\n"
        "**Тип сделки:** Покупка\n"
        "**Вход:** [значение] USDT\n"
        "**SL:** [значение] USDT\n"
        "**TP:** [значение] USDT\n"
        "**Обоснование:** [Твой анализ]\n\n"
        f"Текущие данные по {coin}:\n"
        f"- Текущая цена: {metrics['current_price']:.2f} USDT\n"
        f"- Открытый Интерес (Open Interest): {metrics['open_interest']:.2f}\n"
        f"- Ставка Финансирования (Funding Rate): {metrics['funding_rate']:.5f}\n"
        f"- Объем Покупок (Taker Long Vol): {metrics['taker_buy_volume']:.2f}\n"
        f"- Объем Продаж (Taker Short Vol): {metrics['taker_sell_volume']:.2f}\n"
        f"- Соотношение Лонг/Шорт: {metrics['long_short_ratio']:.2f}\n"
        f"- Индекс Страха и Жадности: {metrics['fear_greed_index_value']:.0f} ({metrics['fear_greed_index_grade']})\n"
    )
    try:
        response = await model.generate_content_async(prompt)
        if response.text:
            return response.text
        else:
            return "ИИ не смог сгенерировать совет. Попробуйте еще раз."
    except Exception as e:
        logging.error(f"Ошибка при обращении к Gemini API: {e}")
        return "Произошла ошибка при генерации совета ИИ. Попробуйте еще раз."

# 🎛 Обработка нажатий на кнопки
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

        await call.message.answer(f"⏳ Получаю данные по {coin} и генерирую совет ИИ...")

        metrics = await fetch_all_metrics(coin)
        if not metrics:
            await call.message.answer("❌ Ошибка получения данных.")
            return

        advice = await generate_ai_advice(coin, metrics)

        text = (
            f"📊 <b>Анализ по монете: {coin}</b>\n\n"
            f"💰 <b>Цена:</b> {metrics['current_price']:.2f} USDT\n"
            f"📈 <b>Открытый Интерес (OI):</b> {metrics['open_interest']:.2f}\n"
            f"💸 <b>Ставка Финансирования (Funding Rate):</b> {metrics['funding_rate']:.5f}\n"
            f"🟢 <b>Объем Покупок (Taker Long Vol):</b> {metrics['taker_buy_volume']:.2f}\n"
            f"🔴 <b>Объем Продаж (Taker Short Vol):</b> {metrics['taker_sell_volume']:.2f}\n"
            f"⚖️ <b>Соотношение Лонг/Шорт:</b> {metrics['long_short_ratio']:.2f}\n"
            f"😱 <b>Индекс Страха и Жадности:</b> {metrics['fear_greed_index_value']:.0f} ({metrics['fear_greed_index_grade']})\n"
            f"\n🧠 <b>Совет ИИ:</b>\n{advice}\n\n"
            "<i>(Примечание: Это рекомендация ИИ, не финансовый совет. Торговля на фьючерсах сопряжена с рисками.)</i>"
        )

        await call.message.answer(text, reply_markup=main_menu())

        if user_id not in ai_advice_history:
            ai_advice_history[user_id] = []

        ai_advice_history[user_id].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "coin": coin,
            "advice": advice
        })
        save_history() # Сохраняем историю сразу после добавления нового совета

# 🚀 Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Загружаем историю при старте бота
    load_history()

    try:
        await dp.start_polling(bot)
    finally:
        # Сохраняем историю перед завершением работы
        # Эта часть кода может не всегда срабатывать при аварийном завершении.
        # Более надежно сохранять после каждого нового совета, что я добавил выше.
        pass

if __name__ == "__main__":
    asyncio.run(main())
