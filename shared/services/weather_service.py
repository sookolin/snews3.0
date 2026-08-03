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
    """Return today's forecast for the given coordinates, or None.

    Includes both the daily summary and an hourly series (temperature, weather
    code, precipitation probability) so the post can break the day into
    morning/day/evening/night parts — and drop parts already in the past when
    the post is published later in the day.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,precipitation_probability_max",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "timezone": "auto",
        "forecast_days": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_FORECAST, params=params)
            resp.raise_for_status()
            data = resp.json() or {}
            daily = data.get("daily") or {}
            if not daily.get("time"):
                return None
            hourly = data.get("hourly") or {}
            return {
                "code": (daily.get("weather_code") or [0])[0],
                "tmax": (daily.get("temperature_2m_max") or [None])[0],
                "tmin": (daily.get("temperature_2m_min") or [None])[0],
                "wind": (daily.get("wind_speed_10m_max") or [None])[0],
                "precip": (daily.get("precipitation_probability_max") or [None])[0],
                "hourly": {
                    "time": hourly.get("time") or [],
                    "temp": hourly.get("temperature_2m") or [],
                    "code": hourly.get("weather_code") or [],
                    "precip": hourly.get("precipitation_probability") or [],
                },
            }
    except Exception as exc:  # noqa: BLE001
        log.warning("forecast_failed", lat=lat, lon=lon, error=str(exc))
        return None


def _fmt_num(value, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{round(float(value))}{suffix}"


def _part_summary(forecast, idxs):
    temps = [forecast["hourly"]["temp"][i] for i in idxs if i < len(forecast["hourly"]["temp"]) and forecast["hourly"]["temp"][i] is not None]
    codes = [forecast["hourly"]["code"][i] for i in idxs if i < len(forecast["hourly"]["code"]) and forecast["hourly"]["code"][i] is not None]
    precs = [forecast["hourly"]["precip"][i] for i in idxs if i < len(forecast["hourly"]["precip"]) and forecast["hourly"]["precip"][i] is not None]
    if not temps:
        return None
    code = max(set(codes), key=codes.count) if codes else forecast.get("code", 0)
    t = round(sum(temps) / len(temps))
    p = max(precs) if precs else None
    return {"t": t, "code": code, "p": p}

def format_post(city_name, forecast, from_hour = 0):
    """Weather body split into day parts, skipping parts already past."""
    parts = [
        ("🌅 Утром", range(6, 12)),
        ("☀️ Днём", range(12, 18)),
        ("🌆 Вечером", range(18, 24)),
        ("🌙 Ночью", range(0, 6)),
    ]
    lines = []
    for label, hours in parts:
        idxs = [h for h in hours if h >= from_hour]
        if not idxs:
            continue
        summ = _part_summary(forecast, idxs)
        if summ is None:
            continue
        desc = _describe(summ["code"])
        line = label + ": " + str(summ["t"]) + "°, " + desc
        if summ["p"] is not None and summ["p"] >= 30:
            line += ", " + "☔️" + " " + str(round(summ["p"])) + "%"
        lines.append(line)
    return "\n".join(lines)

