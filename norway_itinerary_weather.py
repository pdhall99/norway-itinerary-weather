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
USER_AGENT = "github.com/pdhall99/norway-itinerary-weather"

# Pushing coordinates further offshore to avoid "Land Mask" issues
ITINERARY = [
    {
        "date": "2026-04-18",
        "loc": "Southampton",
        "lat": 50.90,
        "lon": -1.40,
        "s_lat": 50.50,
        "s_lon": -1.00,
    },
    {
        "date": "2026-04-19",
        "loc": "🌊 North Sea",
        "lat": 56.00,
        "lon": 1.00,
        "s_lat": 56.00,
        "s_lon": 1.00,
    },
    {
        "date": "2026-04-20",
        "loc": "Stavanger",
        "lat": 58.97,
        "lon": 5.73,
        "s_lat": 59.00,
        "s_lon": 5.00,
    },
    {
        "date": "2026-04-21",
        "loc": "Olden",
        "lat": 61.83,
        "lon": 6.81,
        "s_lat": 62.00,
        "s_lon": 4.50,
    },
    {
        "date": "2026-04-22",
        "loc": "Ålesund",
        "lat": 62.47,
        "lon": 6.15,
        "s_lat": 62.60,
        "s_lon": 5.50,
    },
    {
        "date": "2026-04-23",
        "loc": "Haugesund",
        "lat": 59.41,
        "lon": 5.27,
        "s_lat": 59.40,
        "s_lon": 4.50,
    },
    {
        "date": "2026-04-24",
        "loc": "🌊 English Channel",
        "lat": 52.00,
        "lon": 1.00,
        "s_lat": 52.00,
        "s_lon": 1.00,
    },
    {
        "date": "2026-04-25",
        "loc": "Southampton",
        "lat": 50.90,
        "lon": -1.40,
        "s_lat": 50.50,
        "s_lon": -1.00,
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
            lat, lon, s_lat, s_lon = (
                stop["lat"],
                stop["lon"],
                stop["s_lat"],
                stop["s_lon"],
            )

            # Fetch Endpoints
            wf = await fetch_one(
                client,
                f"https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={lat}&lon={lon}",
            )
            oc = await fetch_one(
                client,
                f"https://api.met.no/weatherapi/oceanforecast/2.0/complete?lat={s_lat}&lon={s_lon}",
            )
            sn = await fetch_one(
                client,
                f"https://api.met.no/weatherapi/sunrise/3.0/sun?lat={lat}&lon={lon}&date={d_str}&offset=+02:00",
            )

            data = {
                "t_mid": "-",
                "t_min": "-",
                "wind": "-",
                "rain": "-",
                "sym": "unknown",
                "wave": "-",
                "flow": "-",
                "w_temp": "-",
                "rise": "-:-",
                "set": "-:-",
            }

            if wf:
                ts = wf["properties"]["timeseries"]
                mid = next((t for t in ts if f"{d_str}T12:00:00Z" in t["time"]), ts[0])
                data["t_mid"] = round(
                    mid["data"]["instant"]["details"]["air_temperature"]
                )
                data["wind"] = round(mid["data"]["instant"]["details"]["wind_speed"])
                p = mid["data"].get("next_6_hours") or mid["data"].get("next_12_hours")
                if p:
                    data["sym"] = p["summary"]["symbol_code"]
                    data["rain"] = round(
                        p["details"].get("probability_of_precipitation", 0)
                    )
                all_t = [
                    t["data"]["instant"]["details"]["air_temperature"]
                    for t in ts
                    if d_str in t["time"]
                ]
                if all_t:
                    data["t_min"] = round(min(all_t))

            found_oc = False
            if oc:
                for entry in oc["properties"]["timeseries"]:
                    if f"{d_str}T12:00:00Z" in entry["time"]:
                        det = entry["data"]["instant"]["details"]
                        if det.get("sea_surface_wave_height") is not None:
                            data["wave"], data["flow"], data["w_temp"] = (
                                det["sea_surface_wave_height"],
                                det["sea_water_speed"],
                                det["sea_water_temperature"],
                            )
                            found_oc = True

            if not found_oc:
                om = await fetch_one(
                    client,
                    f"https://marine-api.open-meteo.com/v1/marine?latitude={s_lat}&longitude={s_lon}&hourly=wave_height&timezone=GMT",
                )
                if om:
                    for i, t in enumerate(om["hourly"]["time"]):
                        if f"{d_str}T12:00" in t:
                            data["wave"] = om["hourly"]["wave_height"][i]
                            break

            if sn:
                data["rise"] = (
                    sn["properties"].get("sunrise", {}).get("time", "    ")[11:16]
                )
                data["set"] = (
                    sn["properties"].get("sunset", {}).get("time", "    ")[11:16]
                )

            day_offset = (target_date - today).days
            # Yr.no URL format: hourly-table/{lat,lon}/Norway/{lat,lon}?i={offset}
            # Note: format coords to 3 decimal places as per Yr.no standard
            l1, n1 = f"{stop['lat']:.3f}", f"{stop['lon']:.3f}"
            data["url"] = f"https://www.yr.no/en/forecast/daily-table/{l1},{n1}/Norway/{l1},{n1}"
            results.append({**stop, **data})

            # Be polite to the API
            await asyncio.sleep(1.0)

    # --- HTML GENERATION ---
    html = f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Norway itinerary weather</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #000b14; color: #e0e0e0; padding: 15px; margin: 0; }}
            .container {{ max-width: 500px; margin: auto; }}
            h1 {{ font-weight: 200; color: #4fc3f7; text-align: center; margin-bottom: 25px; }}
            .card {{ background: linear-gradient(180deg, #011f35 0%, #00121a 100%); border-radius: 20px; padding: 20px; margin-bottom: 15px; border: 1px solid #1a3a4a; }}
            .header {{ display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 12px; margin-bottom: 15px; }}
            .city {{ font-size: 1.3em; font-weight: bold; color: #fff; }}
            .temp-block {{ text-align: right; }}
            .temp-max {{ font-size: 2.2em; font-weight: 100; color: #fff; line-height: 1; }}
            .temp-min {{ font-size: 0.8em; opacity: 0.5; margin-top: 4px; }}
            .metrics-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; align-items: center; gap: 10px; margin-bottom: 20px; }}
            .ocean-stats {{ background: rgba(0,0,0,0.4); padding: 15px; border-radius: 12px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; font-size: 0.75em; border: 1px solid rgba(255,255,255,0.05); text-align: center; }}
            .lbl {{ display: block; font-size: 0.65em; opacity: 0.5; text-transform: uppercase; margin-bottom: 4px; }}
            .val {{ font-weight: bold; color: #fff; font-size: 1.1em; }}
            .sun-row {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding-top: 10px; font-size: 0.85em; }}
            .yr-btn {{ background: #4fc3f7; color: #001a2c; text-decoration: none; padding: 8px 16px; border-radius: 8px; font-size: 0.75em; font-weight: bold; }}
            img.icon {{ width: 50px; display: block; margin: auto; }}
            footer {{ text-align: center; font-size: 0.7em; opacity: 0.3; margin-top: 40px; line-height: 1.6; padding-bottom: 40px; }}
            footer a {{ color: #4fc3f7; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Norway itinerary weather</h1>
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
                        <div class="temp-max">{r['t_mid']}°</div>
                        <div class="temp-min">Min: {r['t_min']}°</div>
                    </div>
                </div>

                <div class="metrics-grid">
                    <div style="text-align:left;">
                        <span class="lbl">Prob. Rain</span>
                        <span class="val" style="color:#4fc3f7;">💧 {r['rain']}%</span>
                    </div>
                    <div style="text-align:center;"><img class="icon" src="https://raw.githubusercontent.com/metno/weathericons/main/weather/svg/{r['sym']}.svg"></div>
                    <div style="text-align:right;">
                        <span class="lbl">Wind</span>
                        <span class="val">💨 {r['wind']} m/s</span>
                    </div>
                </div>

                <div class="ocean-stats">
                    <div><span class="lbl">Waves</span><span class="val">🌊 {r['wave']}m</span></div>
                    <div><span class="lbl">Water Flow</span><span class="val">⚓ {r['flow']}m/s</span></div>
                    <div><span class="lbl">Sea Temp</span><span class="val">🌡️ {r['w_temp']}°</span></div>
                </div>

                <div class="sun-row">
                    <span>🌅 {r['rise']}</span>
                    <a href="{r['url']}" class="yr-btn" target="_blank">DAILY TABLE ↗</a>
                    <span>🌇 {r['set']}</span>
                </div>
            </div>
            '''
                for r in results
            ]
        )
    }

            <footer>
                Weather data from <a href="https://www.met.no/en">MET Norway</a><br>
                Marine data via <a href="https://open-meteo.com/">Open-Meteo</a><br>
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


if __name__ == "__main__":
    asyncio.run(main())
