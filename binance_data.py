import aiohttp
import asyncio
import logging

# ГЛОБАЛЬНЫЕ КОНСТАНТЫ
BINANCE_BASE_URL = "https://fapi.binance.com" # Переименовал BASE_URL в BINANCE_BASE_URL для ясности
ALTERNATIVE_ME_BASE_URL = "https://api.alternative.me"

SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",    # Добавлено
    "XRP": "XRPUSDT",    # Добавлено
    "DOGE": "DOGEUSDT",  # Добавлено
    "ADA": "ADAUSDT",    # Добавлено
    "LINK": "LINKUSDT",  # Добавлено
    "DOT": "DOTUSDT",    # Добавлено
    "AVAX": "AVAXUSDT", # Добавлено
    "SHIB": "SHIBUSDT"   # Добавлено
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- ФУНКЦИИ ДЛЯ BINANCE API (ОБНОВЛЕННЫЕ И БОЛЕЕ НАДЕЖНЫЕ) ---

async def fetch_open_interest(symbol: str):
    # Используем ваш рабочий эндпоинт, но добавляем обработку ошибок
    url = f"{BINANCE_BASE_URL}/fapi/v1/openInterest?symbol={symbol}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status() # Проверяем статус ответа
                data = await response.json()
                # Проверяем, что data - это словарь и в нем есть "openInterest"
                if data and isinstance(data, dict) and "openInterest" in data:
                    return float(data.get("openInterest", 0))
                logging.warning(f"Невалидные данные Open Interest для {symbol}: {data}")
                return 0.0 # Возвращаем 0.0, если данные невалидные
    except Exception as e:
        logging.error(f"Ошибка при получении Open Interest для {symbol}: {e}")
        return None # Возвращаем None при ошибке

async def fetch_funding_rate(symbol: str):
    # Используем ваш рабочий эндпоинт, но добавляем обработку ошибок
    url = f"{BINANCE_BASE_URL}/fapi/v1/fundingRate?symbol={symbol}&limit=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status() # Проверяем статус ответа
                data = await response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return float(data[0].get("fundingRate", 0))
                logging.warning(f"Невалидные данные Funding Rate для {symbol}: {data}")
                return 0.0 # Возвращаем 0.0, если данные невалидные
    except Exception as e:
        logging.error(f"Ошибка при получении Funding Rate для {symbol}: {e}")
        return None # Возвращаем None при ошибке

async def fetch_taker_volume(symbol: str):
    url = f"{BINANCE_BASE_URL}/futures/data/takerlongshortRatio?symbol={symbol}&period=1h&limit=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    # УДАЛЯЕМ ПРЕДУПРЕЖДЕНИЕ И ВОЗВРАЩАЕМ РЕАЛЬНЫЕ ДАННЫЕ!
                    # Исходя из вашего лога, поля 'buyVol' и 'sellVol' теперь присутствуют.
                    return {
                        "longVol": float(data[0].get("buyVol", 0.0)),
                        "shortVol": float(data[0].get("sellVol", 0.0)),
                    }
                logging.warning(f"Невалидные данные Taker Volume для {symbol}: {data}. Возврат 0.")
                return {"longVol": 0.0, "shortVol": 0.0} # Возвращаем 0, если данные не получены
    except Exception as e:
        logging.error(f"Ошибка при получении Taker Volume для {symbol}: {e}")
        return None # Возвращаем None при ошибке

async def fetch_long_short_ratio(symbol: str):
    # Используем стандартный эндпоинт, который уже работал
    url = f"{BINANCE_BASE_URL}/futures/data/globalLongShortAccountRatio"
    params = {"symbol": symbol, "period": "15m", "limit": 1}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    return float(data[0].get("longShortRatio", 0.0))
                logging.warning(f"Невалидные данные Long/Short Ratio для {symbol}: {data}")
                return 0.0
    except Exception as e:
        logging.error(f"Ошибка при получении Long/Short Ratio для {symbol}: {e}")
        return None

async def fetch_current_price(symbol: str):
    url = f"{BINANCE_BASE_URL}/fapi/v1/ticker/price"
    params = {"symbol": symbol}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                if data and isinstance(data, dict):
                    return float(data.get("price", 0.0))
                logging.warning(f"Невалидные данные Current Price для {symbol}: {data}")
                return 0.0
    except Exception as e:
        logging.error(f"Ошибка при получении текущей цены для {symbol}: {e}")
        return None

# --- ФУНКЦИЯ ДЛЯ Alternative.me API (Остается без изменений) ---
async def fetch_alternative_fng_index():
    url = f"{ALTERNATIVE_ME_BASE_URL}/fng/?limit=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                if data and isinstance(data, dict) and data.get("data"):
                    latest_data = data["data"][0]
                    return {
                        "value": float(latest_data.get("value", 0)),
                        "grade": latest_data.get("value_classification", "unknown")
                    }
                logging.warning(f"Невалидные данные Fear & Greed Index: {data}")
                return {"value": 0, "grade": "unknown"}
    except Exception as e:
        logging.error(f"Ошибка при получении индекса страха и жадности от Alternative.me: {e}")
        return None

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ fetch_all_metrics ---
async def fetch_all_metrics(coin_code: str):
    symbol = SYMBOL_MAP.get(coin_code.upper())
    if not symbol:
        logging.warning(f"Неизвестный символ монеты: {coin_code}. Возврат None.")
        return None

    metrics_data = {
        "open_interest": 0.0,
        "funding_rate": 0.0,
        "taker_buy_volume": 0.0,
        "taker_sell_volume": 0.0,
        "long_short_ratio": 0.0,
        "current_price": 0.0,
        "fear_greed_index_value": 0.0,
        "fear_greed_index_grade": "unknown"
    }

    try:
        results = await asyncio.gather(
            fetch_open_interest(symbol),
            fetch_funding_rate(symbol),
            fetch_taker_volume(symbol),
            fetch_long_short_ratio(symbol), # Эта функция была без проблем
            fetch_current_price(symbol),
            fetch_alternative_fng_index(),
            return_exceptions=True
        )

        (open_interest, funding_rate, taker_volume_data, long_short_ratio, current_price,
         fear_greed_data) = results

        # Проверка Open Interest
        if not isinstance(open_interest, Exception) and open_interest is not None:
            metrics_data["open_interest"] = open_interest
        else:
            logging.error(f"Ошибка или None при получении open_interest для {symbol}.")

        # Проверка Funding Rate
        if not isinstance(funding_rate, Exception) and funding_rate is not None:
            metrics_data["funding_rate"] = funding_rate
        else:
            logging.error(f"Ошибка или None при получении funding_rate для {symbol}.")

        # Проверка Taker Volume Data (должен быть словарь)
        if not isinstance(taker_volume_data, Exception) and isinstance(taker_volume_data, dict):
            metrics_data["taker_buy_volume"] = taker_volume_data.get("longVol", 0.0)
            metrics_data["taker_sell_volume"] = taker_volume_data.get("shortVol", 0.0)
        else:
            logging.error(f"Ошибка, None или неверный тип при получении taker_volume для {symbol}. Объемы будут 0.")

        # Проверка Long/Short Ratio
        if not isinstance(long_short_ratio, Exception) and long_short_ratio is not None:
            metrics_data["long_short_ratio"] = long_short_ratio
        else:
            logging.error(f"Ошибка или None при получении long_short_ratio для {symbol}.")

        # Проверка Current Price
        if not isinstance(current_price, Exception) and current_price is not None:
            metrics_data["current_price"] = current_price
        else:
            logging.error(f"Ошибка или None при получении current_price для {symbol}.")

        # Проверка Fear & Greed Index Data (должен быть словарь)
        if not isinstance(fear_greed_data, Exception) and isinstance(fear_greed_data, dict):
            metrics_data["fear_greed_index_value"] = fear_greed_data.get("value", 0.0)
            metrics_data["fear_greed_index_grade"] = fear_greed_data.get("grade", "unknown")
        else:
            logging.error(f"Ошибка, None или неверный тип при получении Fear & Greed Index.")

        return metrics_data

    except Exception as e:
        logging.error(f"Критическая ошибка в fetch_all_metrics для {coin_code}: {e}")
        return None