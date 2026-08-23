import logging

import aiohttp
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _wmo_icon(code: int) -> str:
    """Конвертирует WMO weather code в emoji."""
    if code == 0:                        return "☀️"
    if code in (1, 2):                   return "🌤️"
    if code == 3:                        return "☁️"
    if code in (45, 48):                 return "🌫️"
    if code in (51, 53, 55):             return "🌦️"
    if code in (61, 63, 65):             return "🌧️"
    if code in (71, 73, 75, 77):         return "❄️"
    if code in (80, 81, 82):             return "🌧️"
    if code in (85, 86):                 return "🌨️"
    if code in (95, 96, 99):             return "⛈️"
    return "🌡️"

def _wmo_desc(code: int) -> str:
    """WMO code → описание на русском."""
    descriptions = {
        0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность",
        3: "Пасмурно", 45: "Туман", 48: "Изморозь",
        51: "Лёгкая морось", 53: "Морось", 55: "Сильная морось",
        61: "Небольшой дождь", 63: "Дождь", 65: "Сильный дождь",
        71: "Небольшой снег", 73: "Снег", 75: "Сильный снег", 77: "Снежная крупа",
        80: "Ливень", 81: "Сильный ливень", 82: "Очень сильный ливень",
        85: "Небольшой снегопад", 86: "Сильный снегопад",
        95: "Гроза", 96: "Гроза с градом", 99: "Гроза с сильным градом",
    }
    return descriptions.get(code, "Неизвестно")

def _wind_dir(deg: float) -> str:
    """Градусы → направление ветра."""
    dirs = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    return dirs[round(deg / 45) % 8]

def _uv_label(uv: float) -> str:
    if uv < 3:   return "Низкий"
    if uv < 6:   return "Умеренный"
    if uv < 8:   return "Высокий"
    if uv < 11:  return "Очень высокий"
    return "Экстремальный"


async def _geocode(session: aiohttp.ClientSession, city: str) -> tuple[float, float, str]:
    """Nominatim: название города → (lat, lon, display_name)."""
    params = {"q": city, "format": "json", "limit": 1, "accept-language": "ru"}
    headers = {"User-Agent": "MoldovaBot/1.0 (telegram bot)"}
    async with session.get(
        "https://nominatim.openstreetmap.org/search",
        params=params, headers=headers,
        timeout=aiohttp.ClientTimeout(total=8),
    ) as r:
        results = await r.json()
    if not results:
        raise ValueError(f"Город «{city}» не найден")
    r0 = results[0]
    name = r0.get("display_name", city).split(",")[0].strip()
    return float(r0["lat"]), float(r0["lon"]), name


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Погода через Open-Meteo (бесплатно, без ключа).
    /weather              → текущая погода в Кишинёве
    /weather <город>      → текущая погода в любом городе
    /weather forecast     → прогноз на 3 дня для Кишинёва
    /weather <город> forecast → прогноз на 3 дня для города
    """
    args = context.args or []

    if "forecast" in [a.lower() for a in args]:
        show_forecast = True
        city_parts = [a for a in args if a.lower() != "forecast"]
    else:
        show_forecast = False
        city_parts = args

    city_query = " ".join(city_parts) if city_parts else "Кишинёв"

    try:
        async with aiohttp.ClientSession() as session:
            lat, lon, city_name = await _geocode(session, city_query)

            params = {
                "latitude":            lat,
                "longitude":           lon,
                "current":             "temperature_2m,apparent_temperature,relative_humidity_2m,"
                                       "wind_speed_10m,wind_direction_10m,weather_code,"
                                       "uv_index,precipitation,surface_pressure",
                "daily":               "weather_code,temperature_2m_max,temperature_2m_min,"
                                       "precipitation_sum,wind_speed_10m_max,"
                                       "sunrise,sunset,uv_index_max",
                "timezone":            "auto",
                "forecast_days":       4,
                "wind_speed_unit":     "kmh",
            }
            async with session.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise ValueError(f"Open-Meteo HTTP {resp.status}")
                om = await resp.json()

        cur = om["current"]
        daily = om["daily"]

        temp      = cur["temperature_2m"]
        feels     = cur["apparent_temperature"]
        humidity  = cur["relative_humidity_2m"]
        wind_spd  = cur["wind_speed_10m"]
        wind_deg  = cur["wind_direction_10m"]
        wcode     = cur["weather_code"]
        uv        = cur.get("uv_index") or 0
        precip    = cur.get("precipitation") or 0
        pressure  = cur.get("surface_pressure") or 0

        icon = _wmo_icon(wcode)
        desc = _wmo_desc(wcode)
        wdir = _wind_dir(wind_deg)

        sunrise = daily["sunrise"][0].split("T")[1] if daily.get("sunrise") else "—"
        sunset  = daily["sunset"][0].split("T")[1]  if daily.get("sunset")  else "—"

        msg = (
            f"{icon} <b>Погода в {city_name}</b>\n\n"
            f"🌡️ Температура: <b>{temp:.0f}°C</b> (ощущается как {feels:.0f}°C)\n"
            f"☁️ Состояние: {desc}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind_spd / 3.6:.1f} м/с {wdir}\n"
            f"🔵 Давление: {pressure:.0f} гПа\n"
            f"🌂 Осадки: {precip:.1f} мм\n"
            f"☀️ UV-индекс: {uv:.0f} ({_uv_label(uv)})\n"
            f"🌅 Восход: {sunrise}  🌇 Закат: {sunset}\n\n"
        )

        if show_forecast:
            day_names = ["Сегодня", "Завтра", "Послезавтра"]
            forecast_lines = "📅 <b>Прогноз на 3 дня:</b>\n"
            for i in range(3):
                d_code  = daily["weather_code"][i]
                d_max   = daily["temperature_2m_max"][i]
                d_min   = daily["temperature_2m_min"][i]
                d_prec  = daily.get("precipitation_sum", [0]*4)[i] or 0
                d_wind  = daily.get("wind_speed_10m_max", [0]*4)[i] or 0
                d_icon  = _wmo_icon(d_code)
                d_desc  = _wmo_desc(d_code)
                forecast_lines += (
                    f"\n{d_icon} <b>{day_names[i]}</b>\n"
                    f"   🌡️ {d_min:.0f}°C … {d_max:.0f}°C\n"
                    f"   ☁️ {d_desc}\n"
                    f"   🌂 {d_prec:.1f} мм  💨 {d_wind / 3.6:.1f} м/с\n"
                )
            msg += forecast_lines + "\n"
        else:
            msg += "<i>Прогноз на 3 дня: /weather forecast</i>\n"

        msg += "\n<i>Источник: Open-Meteo · OpenStreetMap</i>"

    except ValueError as e:
        msg = f"⚠️ {e}"
    except Exception as e:
        logger.warning(f"Weather error: {e}")
        msg = "⚠️ Не удалось получить погоду. Попробуй позже!"

    await update.message.reply_html(msg)
