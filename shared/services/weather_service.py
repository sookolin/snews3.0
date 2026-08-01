"""Weather service: fetch a daily forecast and format a channel post."""
from __future__ import annotations

import httpx

from shared.logging import get_logger

log = get_logger("weather")

_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> short Russian description + emoji.
_WMO = {
    0: "Ясно ☀️", 1: "Малооблачно 🌤", 2: "Переменная облачность ⛅",
    3: "Пасмурно ☁️", 45: "Туман 🌫", 48: "Изморозь 🌫",
    51: "Морось 🌦", 53: "Морось 🌦", 55: "Морось 🌦",
    61: "Дождь 🌧", 63: "Дождь 🌧", 65: "Сильный дождь 🌧",
    71: "Снег 🌨", 73: "Снег 🌨", 75: "Сильный снег 🌨",
    80: "Ливень 🌧", 81: "Ливень 🌧", 82: "Сильный ливень ⛈",
    95: "Гроза ⛈", 96: "Гроза с градом ⛈", 99: "Гроза с градом ⛈",
}


def _describe(code: int) -> str:
    return _WMO.get(int(code), "Погода")


async def _geocode(name: str) -> tuple[float, float] | None:
    """Resolve a city name to (lat, lon) via Open-Meteo geocoding."""
    params = {"name": name, "count": 1, "language": "ru", "format": "json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_GEOCODE, params=params)
            resp.raise_for_status()
            results = (resp.json() or {}).get("results") or []
            if not results:
                return None
            top = results[0]
            return float(top["latitude"]), float(top["longitude"])
    except Exception as exc:  # noqa: BLE001
        log.warning("geocode_failed", city=name, error=str(exc))
        return None


async def fetch_forecast(lat: float, lon: float) -> dict | None:
    """Return today's forecast dict for the given coordinates, or None."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_FORECAST, params=params)
            resp.raise_for_status()
            daily = (resp.json() or {}).get("daily") or {}
            if not daily.get("time"):
                return None
            return {
                "code": (daily.get("weather_code") or [0])[0],
                "tmax": (daily.get("temperature_2m_max") or [None])[0],
                "tmin": (daily.get("temperature_2m_min") or [None])[0],
                "wind": (daily.get("wind_speed_10m_max") or [None])[0],
                "precip": (daily.get("precipitation_probability_max") or [None])[0],
            }
    except Exception as exc:  # noqa: BLE001
        log.warning("forecast_failed", lat=lat, lon=lon, error=str(exc))
        return None


def _fmt_num(value, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{round(float(value))}{suffix}"


def format_post(city_name: str, forecast: dict) -> str:
    """Build the HTML weather post for a city channel."""
    desc = _describe(forecast.get("code", 0))
    tmax = _fmt_num(forecast.get("tmax"), "°")
    tmin = _fmt_num(forecast.get("tmin"), "°")
    wind = _fmt_num(forecast.get("wind"), " км/ч")
    precip = forecast.get("precip")
    lines = [
        f"<b>🌤 Погода в городе {city_name}</b>",
        "",
        f"{desc}",
        f"🌡 Температура: {tmin}…{tmax}",
        f"💨 Ветер: {wind}",
    ]
    if precip is not None:
        lines.append(f"☔️ Вероятность осадков: {_fmt_num(precip, '%')}")
    return "\n".join(lines)
