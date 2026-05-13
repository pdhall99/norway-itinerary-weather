# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx[http2]",
# ]
# ///

import asyncio
import datetime
import logging

import httpx

logging.basicConfig(level=logging.DEBUG, force=True)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
USER_AGENT = "github.com/pdhall99/north-america-itinerary-weather"

# Itinerary
ITINERARY = [
    {
        "date": "2026-05-19",
        "loc": "Seattle",
        "lat": 47.61,
        "lon": -122.33,
    },
    {
        "date": "2026-05-25",
        "loc": "Haines",
        "lat": 59.23,
        "lon": -135.44,
    },
    {
        "date": "2026-05-25",
        "loc": "Juneau",
        "lat": 58.30,
        "lon": -134.42,
    },
    {
        "date": "2026-06-04",
        "loc": "Vancouver",
        "lat": 49.28,
        "lon": -123.12,
    },
    {
        "date": "2026-06-06",
        "loc": "Jasper",
        "lat": 52.88,
        "lon": -118.08,
    },
    {
        "date": "2026-06-10",
        "loc": "Banff",
        "lat": 51.18,
        "lon": -115.57,
    },
    {
        "date": "2026-06-12",
        "loc": "Niagara Falls",
        "lat": 43.09,
        "lon": -79.08,
    },
]


async def fetch_one(client, url):
    try:
        resp = await client.get(url, timeout=10.0)
        return resp.json() if resp.status_code == 200 else None
    except httpx.HttpError:
        return None


async def main():
    results = []
    today = datetime.datetime.now(datetime.UTC).date()

    async with httpx.AsyncClient(
        http2=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        for stop in ITINERARY:
            print(f"Fetching {stop['loc']}...")

            d_str = stop["date"]
            target_date = datetime.datetime.strptime(d_str, "%Y-%m-%d").date()
            lat, lon = stop["lat"], stop["lon"]

            # Open-Meteo API
            forecast_url = (
                "https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&"
                "hourly=temperature_2m,precipitation_probability,wind_speed_10m,weather_code&"
                "daily=sunrise,sunset,temperature_2m_max,temperature_2m_min&"
                "timezone=auto&"
                f"start_date={d_str}&end_date={d_str}"
                "&wind_speed_unit=mph"
            )

            wf = await fetch_one(client, forecast_url)

            data = {
                "t_mid": "-",
                "t_min": "-",
                "t_max": "-",
                "wind": "-",
                "rain": "-",
                "sym": "unknown",
                "rise": "-:-",
                "set": "-:-",
            }

            if wf:
                # Daily data
                if wf.get("daily"):
                    daily = wf["daily"]
                    if daily.get("temperature_2m_max"):
                        data["t_max"] = round(daily["temperature_2m_max"][0])
                    if daily.get("temperature_2m_min"):
                        data["t_min"] = round(daily["temperature_2m_min"][0])
                    if daily.get("sunrise"):
                        sunrise = daily["sunrise"][0]
                        data["rise"] = sunrise[11:16] if len(sunrise) > 11 else "-:-"
                    if daily.get("sunset"):
                        sunset = daily["sunset"][0]
                        data["set"] = sunset[11:16] if len(sunset) > 11 else "-:-"

                # Hourly data (get midday values)
                if wf.get("hourly"):
                    hourly = wf["hourly"]
                    times = hourly.get("time", [])

                    # Find noon or closest hour
                    target_hour = f"{d_str}T12:00"
                    idx = None
                    for i, t in enumerate(times):
                        if target_hour in t:
                            idx = i
                            break

                    if idx is None and times:
                        # Fallback to first available hour
                        idx = 0

                    if idx is not None:
                        if hourly.get("temperature_2m"):
                            data["t_mid"] = round(hourly["temperature_2m"][idx])
                        if hourly.get("wind_speed_10m"):
                            data["wind"] = round(hourly["wind_speed_10m"][idx])
                        if hourly.get("precipitation_probability"):
                            data["rain"] = round(
                                hourly["precipitation_probability"][idx]
                            )
                        if hourly.get("weather_code"):
                            # Map Open-Meteo weather codes to simple descriptors
                            wmo_code = hourly["weather_code"][idx]
                            data["sym"] = map_weather_code(wmo_code)

            # Generate forecast URL
            data["url"] = f"https://open-meteo.com/en/docs#{lat},{lon}"

            results.append({**stop, **data})

            # Be polite to the API
            await asyncio.sleep(0.5)

    # --- HTML GENERATION ---
    html = f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Itinerary weather</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #0a1628; color: #e0e0e0; padding: 15px; margin: 0; }}
            .container {{ max-width: 500px; margin: auto; }}
            h1 {{ font-weight: 200; color: #60a5fa; text-align: center; margin-bottom: 25px; }}
            .card {{ background: linear-gradient(180deg, #1e3a5f 0%, #0f1c2e 100%); border-radius: 20px; padding: 20px; margin-bottom: 15px; border: 1px solid #2d4a6f; }}
            .header {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 12px; margin-bottom: 15px; }}
            .city {{ font-size: 1.3em; font-weight: bold; color: #fff; }}
            .temp-block {{ text-align: right; }}
            .temp-max {{ font-size: 2.2em; font-weight: 100; color: #fff; line-height: 1; }}
            .temp-min {{ font-size: 0.8em; opacity: 0.5; margin-top: 4px; }}
            .metrics-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; align-items: center; gap: 10px; margin-bottom: 20px; }}
            .lbl {{ display: block; font-size: 0.65em; opacity: 0.5; text-transform: uppercase; margin-bottom: 4px; }}
            .val {{ font-weight: bold; color: #fff; font-size: 1.1em; }}
            .sun-row {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding-top: 10px; font-size: 0.85em; }}
            .om-btn {{ background: #60a5fa; color: #0a1628; text-decoration: none; padding: 8px 16px; border-radius: 8px; font-size: 0.75em; font-weight: bold; }}
            .weather-icon {{ font-size: 3em; text-align: center; }}
            footer {{ text-align: center; font-size: 0.7em; opacity: 0.3; margin-top: 40px; line-height: 1.6; padding-bottom: 40px; }}
            footer a {{ color: #60a5fa; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏔️ Itinerary weather</h1>
            {
        "".join(
            [
                f'''
            <div class="card">
                <div class="header">
                    <div>
                        <div style="font-size:0.8em; opacity:0.6;">{datetime.datetime.strptime(r['date'], '%Y-%m-%d').strftime('%A, %d %b')}</div>
                        <div class="city">{r['loc']}</div>
                    </div>
                    <div class="temp-block">
                        <div class="temp-max">{r['t_max']}°</div>
                        <div class="temp-min">Min: {r['t_min']}°</div>
                    </div>
                </div>

                <div class="metrics-grid">
                    <div style="text-align:left;">
                        <span class="lbl">Prob. Rain</span>
                        <span class="val" style="color:#60a5fa;">💧 {r['rain']}%</span>
                    </div>
                    <div class="weather-icon">{get_weather_emoji(r['sym'])}</div>
                    <div style="text-align:right;">
                        <span class="lbl">Wind</span>
                        <span class="val">💨 {r['wind']} mph</span>
                    </div>
                </div>

                <div class="sun-row">
                    <span>🌅 {r['rise']}</span>
                    <a href="{r['url']}" class="om-btn" target="_blank">FORECAST ↗</a>
                    <span>🌇 {r['set']}</span>
                </div>
            </div>
            '''
                for r in results
            ]
        )
    }

            <footer>
                Weather data from <a href="https://open-meteo.com/">Open-Meteo</a><br>
                Updated: {
        datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    }
            </footer>
        </div>
    </body>
    </html>
    """
    with open("index.html", "w") as f:
        f.write(html)


def map_weather_code(code):
    """
    Map WMO weather codes to simplified weather conditions.
    https://open-meteo.com/en/docs
    """
    if code == 0:
        return "clear"
    elif code in [1, 2]:
        return "partly_cloudy"
    elif code == 3:
        return "cloudy"
    elif code in [45, 48]:
        return "fog"
    elif code in [51, 53, 55, 56, 57]:
        return "drizzle"
    elif code in [61, 63, 65, 66, 67, 80, 81, 82]:
        return "rain"
    elif code in [71, 73, 75, 77, 85, 86]:
        return "snow"
    elif code in [95, 96, 99]:
        return "thunderstorm"
    else:
        return "unknown"


def get_weather_emoji(condition):
    """Convert weather condition to emoji"""
    emoji_map = {
        "clear": "☀️",
        "partly_cloudy": "⛅",
        "cloudy": "☁️",
        "fog": "🌫️",
        "drizzle": "🌦️",
        "rain": "🌧️",
        "snow": "❄️",
        "thunderstorm": "⛈️",
        "unknown": "🌡️",
    }
    return emoji_map.get(condition, "🌡️")


if __name__ == "__main__":
    asyncio.run(main())
