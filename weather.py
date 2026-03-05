import os
import re
import time
import threading
import json
import sopel.plugin
import requests
import datetime

# PirateWeather API key (get one from https://pirateweather.net)
WEATHER_API_KEY = "6NRuZmTmaHWw5WsEIIJidnEEiEYSFvGi"

# Delay between PM lines when sending alerts (seconds) - keep low enough to be
# useful but high enough to avoid flood kicks
ALERT_PM_DELAY = 1.5

# File to store user registered locations
LOCATION_FILE = os.path.expanduser("~/.sopel/weather_locations.json")
user_locations = {}


def load_locations():
    global user_locations
    if os.path.exists(LOCATION_FILE):
        try:
            with open(LOCATION_FILE, "r", encoding="utf-8") as f:
                user_locations = json.load(f)
        except Exception:
            user_locations = {}
    else:
        user_locations = {}


def save_locations():
    with open(LOCATION_FILE, "w", encoding="utf-8") as f:
        json.dump(user_locations, f, ensure_ascii=False)


# Load registered locations on module load
load_locations()


def get_prefix(bot):
    """Return the display prefix (unescaped from its regex pattern)."""
    return re.sub(r'\\(.)', r'\1', bot.config.core.prefix)


def sanitize_input(text):
    if not isinstance(text, str):
        text = str(text)
    try:
        sanitized = text.encode("ascii", "ignore").decode("ascii")
    except Exception:
        sanitized = text
    return " ".join(sanitized.strip().split())


def colorize_temperature(temp_c):
    temp_f = temp_c * 9 / 5 + 32
    if temp_c < 10:
        color_code = "12"  # Blue
    elif temp_c < 20:
        color_code = "08"  # Yellow
    elif temp_c < 30:
        color_code = "07"  # Orange
    else:
        color_code = "04"  # Red
    return f"\x03{color_code}{temp_c:.1f}°C ({temp_f:.1f}°F)\x03"


def wind_direction(deg):
    if deg is None:
        return "?"
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = round(deg / 45) % 8
    return dirs[ix]


def shorten_location_name(display_name: str) -> str:
    if not display_name:
        return "Unknown location"
    parts = display_name.split(", ")
    cleaned = [p for p in parts if not any(c.isdigit() for c in p)]
    if len(cleaned) >= 3:
        return f"{cleaned[0]}, {cleaned[-2]}"
    elif len(cleaned) >= 2:
        return f"{cleaned[0]}, {cleaned[1]}"
    return cleaned[0] if cleaned else display_name


def get_coordinates(location):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": location, "format": "json", "limit": 1}
        headers = {"User-Agent": "SopelWeatherBot/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if data:
            result = data[0]
            lat = float(result["lat"])
            lon = float(result["lon"])
            display_name = shorten_location_name(result["display_name"])
            return lat, lon, display_name
        else:
            return None, None, None
    except Exception:
        return None, None, None


def resolve_location(nick, args):
    if args:
        # Check if the argument is a known username first
        target_nick = args.strip().lower()
        if target_nick in user_locations:
            loc = user_locations[target_nick]
            return loc["lat"], loc["lon"], loc["name"]

        # If not a user, try to geocode it as a location
        lat, lon, display_name = get_coordinates(sanitize_input(args))
        if not lat:
            return None, None, None
        return lat, lon, display_name
    elif nick.lower() in user_locations:
        loc = user_locations[nick.lower()]
        return loc["lat"], loc["lon"], loc["name"]
    return None, None, None


def parse_nick_flag(args):
    """Parse -n <username> from the beginning of args.
    Returns (target_nick, remaining_args) where target_nick is the
    username (lowercase, no leading '-n') or None if flag not present.
    remaining_args is whatever is left after stripping the -n flag."""
    if not args:
        return None, None
    parts = args.strip().split()
    if parts[0].lower() == "-n" and len(parts) >= 2:
        target_nick = parts[1].lower()
        remaining = " ".join(parts[2:]) if len(parts) > 2 else ""
        return target_nick, remaining or None
    return None, args.strip() or None


def send_alerts_pm(bot, nick, alerts, display_name):
    """Send weather alerts to a user via PM, spaced to avoid flood kicks.

    Runs in a background thread. Each alert gets a header line, then its
    description chunked into IRC-safe pieces, then a link if available.
    ALERT_PM_DELAY seconds are inserted between every send.
    """
    IRC_SAFE_LEN = 380  # conservative max chars per message

    def pm(text):
        bot.say(text, nick)
        time.sleep(ALERT_PM_DELAY)

    pm(f"⚠️ \x02Weather Alerts for {display_name}\x02 ({len(alerts)} alert(s)):")

    for i, alert in enumerate(alerts, 1):
        title = alert.get("title", "Unknown Alert")
        severity = alert.get("severity", "unknown").capitalize()
        expires = alert.get("expires")
        description = alert.get("description", "No details available.").strip()
        uri = alert.get("uri", "")

        expires_str = ""
        if expires:
            try:
                dt = datetime.datetime.fromtimestamp(expires)
                expires_str = f"  |  Expires: {dt.strftime('%a %b %d %I:%M %p')}"
            except Exception:
                pass

        # Severity colour: red=warning, orange=watch, yellow=advisory
        sev_lower = severity.lower()
        if "warning" in sev_lower:
            sev_color = "\x0304"   # red
        elif "watch" in sev_lower:
            sev_color = "\x0307"   # orange
        else:
            sev_color = "\x0308"   # yellow

        pm(
            f"── Alert {i}/{len(alerts)}: "
            f"{sev_color}\x02[{severity}]\x02\x03 \x02{title}\x02{expires_str}"
        )

        # Send description in chunks so we don't hit IRC line limits
        for pos in range(0, len(description), IRC_SAFE_LEN):
            pm(description[pos:pos + IRC_SAFE_LEN])

        if uri:
            pm(f"🔗 More info: {uri}")

    pm(f"── End of alerts for {display_name} ──")


@sopel.plugin.command("register_location")
def register_location(bot, trigger):
    args = trigger.group(2)
    if not args:
        bot.say(f"Usage: {get_prefix(bot)}register_location <location>")
        return
    location = sanitize_input(args)
    lat, lon, display_name = get_coordinates(location)
    if not lat:
        bot.say(f"Location '{location}' not found.")
        return
    user_locations[trigger.nick.lower()] = {
        "lat": lat,
        "lon": lon,
        "name": display_name,
    }
    save_locations()
    bot.say(f"Location for {trigger.nick} registered as: {display_name}")


@sopel.plugin.command("change_location")
def change_location(bot, trigger):
    args = trigger.group(2)
    if not args:
        bot.say(f"Usage: {get_prefix(bot)}change_location <new location>")
        return
    location = sanitize_input(args)
    lat, lon, display_name = get_coordinates(location)
    if not lat:
        bot.say(f"Location '{location}' not found.")
        return
    user_locations[trigger.nick.lower()] = {
        "lat": lat,
        "lon": lon,
        "name": display_name,
    }
    save_locations()
    bot.say(f"Your location has been updated to: {display_name}")


@sopel.plugin.command("unregister_location")
def unregister_location(bot, trigger):
    nick = trigger.nick.lower()
    if nick in user_locations:
        del user_locations[nick]
        save_locations()
        bot.say("Your registered location has been removed.")
    else:
        bot.say("You do not have a registered location.")


@sopel.plugin.command("w")
def current_weather(bot, trigger):
    args = trigger.group(2)
    target_nick, remaining_args = parse_nick_flag(args)
    prefix = get_prefix(bot)

    if target_nick is not None:
        # -n flag was explicitly given — look up that user's saved location only
        if target_nick not in user_locations:
            bot.say(
                f"{target_nick} has not set a location. "
                f"They need to use: {prefix}register_location <location>"
            )
            return
        loc = user_locations[target_nick]
        lat, lon, display_name = loc["lat"], loc["lon"], loc["name"]
    else:
        lat, lon, display_name = resolve_location(trigger.nick, remaining_args)
        if not lat:
            bot.say(f"No location found. Use {prefix}w <location> or {prefix}register_location <location>")
            return

    url = f"https://api.pirateweather.net/forecast/{WEATHER_API_KEY}/{lat},{lon}?units=si"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except Exception as e:
        bot.say(f"Error retrieving weather: {e}")
        return

    if "currently" not in data:
        bot.say("No weather data available.")
        return

    c = data["currently"]
    temp_c = c.get("temperature", 0.0)
    pressure = c.get("pressure", 0.0)
    humidity = c.get("humidity", 0.0) * 100
    wind_speed = c.get("windSpeed", 0.0)
    wind_bearing = c.get("windBearing")
    wind_dir = wind_direction(wind_bearing)
    clouds = c.get("cloudCover", 0.0) * 100
    precipitation = c.get("precipIntensity", 0.0)
    summary = c.get("summary", "Unknown")
    emoji = "☀️" if "Clear" in summary else "⛅" if "Cloud" in summary else "🌧️" if "Rain" in summary else "🌦️"

    wind_speed_kmh = wind_speed * 3.6
    wind_speed_mph = wind_speed * 2.23694

    color_temp = colorize_temperature(temp_c)

    # Wind direction arrow
    arrow_map = {"N": "↑", "NE": "↗", "E": "→", "SE": "↘", "S": "↓", "SW": "↙", "W": "←", "NW": "↖"}
    wind_arrow = arrow_map.get(wind_dir, "")

    sep = "\x0314 · \x03"
    output = (
        f"🌍 \x02{display_name}\x02{sep}"
        f"{emoji} \x02{summary}\x02{sep}"
        f"🌡️ {color_temp}{sep}"
        f"💧 \x02{humidity:.0f}%\x02 humidity{sep}"
        f"🌬️ \x02{wind_speed_kmh:.1f}\x02 km/h (\x02{wind_speed_mph:.1f}\x02 mph) {wind_arrow}{wind_dir}{sep}"
        f"☁️ \x02{clouds:.0f}%\x02 cloud{sep}"
        f"🌧️ \x02{precipitation:.1f}\x02 mm/hr{sep}"
        f"📊 \x02{pressure:.0f}\x02 hPa"
    )
    bot.say(output)

    # Notify about active weather alerts without auto-spamming via PM
    alerts = data.get("alerts", [])
    if alerts:
        prefix = get_prefix(bot)
        count = len(alerts)
        bot.say(
            f"⚠️ \x02{count}\x02 active weather alert(s) for {display_name} — "
            f"use \x02{prefix}wa\x02 to receive details via PM."
        )


@sopel.plugin.command("wa")
def weather_alerts(bot, trigger):
    """Send active weather alerts to the requesting user via PM.

    Usage:
        !wa            – alerts for your own registered location
        !wa -n <user>  – alerts for another user's registered location
    """
    args = trigger.group(2)
    target_nick, remaining_args = parse_nick_flag(args)
    prefix = get_prefix(bot)
    requester = trigger.nick

    if target_nick is not None:
        # -n flag: look up another user's saved location
        if target_nick not in user_locations:
            bot.say(
                f"{target_nick} has not set a location. "
                f"They need to use: {prefix}register_location <location>"
            )
            return
        loc = user_locations[target_nick]
        lat, lon, display_name = loc["lat"], loc["lon"], loc["name"]
    else:
        # No -n flag — resolve_location handles:
        #   remaining_args = "arlington, va"  → geocode it
        #   remaining_args = None and caller has a saved location → use it
        lat, lon, display_name = resolve_location(requester, remaining_args)
        if not lat:
            bot.say(
                f"No location found. Use {prefix}wa <location> or "
                f"{prefix}register_location <location> to save one."
            )
            return

    url = f"https://api.pirateweather.net/forecast/{WEATHER_API_KEY}/{lat},{lon}?units=si"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except Exception as e:
        bot.say(f"Error retrieving weather alerts: {e}")
        return

    alerts = data.get("alerts", [])
    if not alerts:
        bot.say(f"No active weather alerts for {display_name}.")
        return

    count = len(alerts)
    bot.say(
        f"⚠️ \x02{count}\x02 weather alert(s) for {display_name} — "
        f"sending you a PM, {requester}."
    )
    threading.Thread(
        target=send_alerts_pm,
        args=(bot, requester, alerts, display_name),
        daemon=True,
    ).start()


@sopel.plugin.command("f")
def forecast_weather(bot, trigger):
    args = trigger.group(2)
    target_nick, remaining_args = parse_nick_flag(args)
    prefix = get_prefix(bot)

    if target_nick is not None:
        # -n flag was explicitly given — look up that user's saved location only
        if target_nick not in user_locations:
            bot.say(
                f"{target_nick} has not set a location. "
                f"They need to use: {prefix}register_location <location>"
            )
            return
        loc = user_locations[target_nick]
        lat, lon, display_name = loc["lat"], loc["lon"], loc["name"]
    else:
        lat, lon, display_name = resolve_location(trigger.nick, remaining_args)
        if not lat:
            bot.say(f"No location found. Use {prefix}f <location> or {prefix}register_location <location>")
            return

    url = f"https://api.pirateweather.net/forecast/{WEATHER_API_KEY}/{lat},{lon}?units=si"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except Exception as e:
        bot.say(f"Error retrieving forecast: {e}")
        return

    if "daily" not in data or "data" not in data["daily"]:
        bot.say("No forecast data available.")
        return

    daily_data = data["daily"]["data"][:4]
    sep = "\x0314 · \x03"

    # Line 1: header
    bot.say(f"📅 \x024-Day Forecast\x02{sep}\x02{display_name}\x02")

    # Line 2: all 4 days compact — emoji + short day name + high/low
    day_parts = []
    for day in daily_data:
        dt = datetime.datetime.fromtimestamp(day["time"])
        weekday = dt.strftime("%a")   # Sat, Sun, Mon, Tue
        summary = day.get("summary", "Unknown")
        temp_min = day.get("temperatureMin", 0.0)
        temp_max = day.get("temperatureMax", 0.0)

        emoji = "☀️" if "Clear" in summary else "⛅" if "Cloud" in summary else "🌧️" if "Rain" in summary else "🌦️"
        max_temp_str = colorize_temperature(temp_max)
        min_temp_str = colorize_temperature(temp_min)

        day_parts.append(f"{emoji} \x02{weekday}\x02 ↑{max_temp_str} ↓{min_temp_str}")

    bot.say(sep.join(day_parts))


def send_forecast_pm(bot, nick, daily_data, display_name):
    """Send an extended multi-day forecast via PM with flood-safe delays."""
    IRC_SAFE_LEN = 380

    def pm(text):
        bot.say(text, nick)
        time.sleep(ALERT_PM_DELAY)

    count = len(daily_data)
    pm(f"📅 \x02Extended {count}-Day Forecast for {display_name}\x02")
    pm(f"{'─' * 42}")

    for i, day in enumerate(daily_data, 1):
        dt = datetime.datetime.fromtimestamp(day["time"])
        day_name = dt.strftime("%A")        # Monday, Tuesday, ...
        date_str = dt.strftime("%b %d")      # Mar 05
        summary = day.get("summary", "No summary")
        temp_min = day.get("temperatureMin", 0.0)
        temp_max = day.get("temperatureMax", 0.0)
        humidity = day.get("humidity", 0.0) * 100
        precip_prob = day.get("precipProbability", 0.0) * 100
        precip_type = day.get("precipType", "")
        wind_speed = day.get("windSpeed", 0.0)
        wind_bearing = day.get("windBearing")
        wind_dir = wind_direction(wind_bearing)
        wind_gust = day.get("windGust", 0.0)
        uv = day.get("uvIndex", 0)

        # Emoji based on summary
        s = summary.lower()
        if "clear" in s or "sunny" in s:
            emoji = "☀️"
        elif "partly" in s:
            emoji = "⛅"
        elif "cloud" in s or "overcast" in s:
            emoji = "☁️"
        elif "snow" in s or "sleet" in s or "flurr" in s:
            emoji = "❄️"
        elif "thunder" in s or "storm" in s:
            emoji = "⛈️"
        elif "rain" in s or "drizzle" in s or "shower" in s:
            emoji = "🌧️"
        elif "fog" in s or "mist" in s:
            emoji = "🌫️"
        elif "wind" in s:
            emoji = "💨"
        else:
            emoji = "🌦️"

        # Precip annotation
        precip_str = ""
        if precip_prob > 0:
            ptype = precip_type.capitalize() if precip_type else "Precip"
            precip_str = f"  |  🌧️ {ptype} \x02{precip_prob:.0f}%\x02"

        # Wind with arrow
        arrow_map = {
            "N": "↑", "NE": "↗", "E": "→", "SE": "↘",
            "S": "↓", "SW": "↙", "W": "←", "NW": "↖",
        }
        wind_arrow = arrow_map.get(wind_dir, "")
        wind_kmh = wind_speed * 3.6
        wind_mph = wind_speed * 2.23694
        gust_kmh = wind_gust * 3.6

        max_temp_str = colorize_temperature(temp_max)
        min_temp_str = colorize_temperature(temp_min)

        # UV color
        if uv >= 8:
            uv_color = "\x0304"  # red
        elif uv >= 6:
            uv_color = "\x0307"  # orange
        elif uv >= 3:
            uv_color = "\x0308"  # yellow
        else:
            uv_color = "\x0303"  # green

        # Line 1: Day header with summary & temps
        pm(
            f"{emoji} \x02{day_name}, {date_str}\x02  —  {summary}  |  "
            f"↑ {max_temp_str}  ↓ {min_temp_str}"
        )
        # Line 2: Details
        pm(
            f"   💧 Humidity \x02{humidity:.0f}%\x02{precip_str}  |  "
            f"🌬️ Wind \x02{wind_kmh:.0f}\x02 km/h ({wind_mph:.0f} mph) {wind_arrow}{wind_dir}  "
            f"(gusts \x02{gust_kmh:.0f}\x02 km/h)  |  "
            f"☀️ UV {uv_color}\x02{uv}\x03\x02"
        )

    pm(f"{'─' * 42}")
    pm(f"📍 End of forecast for \x02{display_name}\x02")


@sopel.plugin.command("ef")
def extended_forecast(bot, trigger):
    """Send an extended 8-day forecast via PM.

    Usage:
        !ef            – forecast for your registered location
        !ef <location>  – forecast for a specific location
        !ef -n <user>  – forecast for another user's registered location
    """
    args = trigger.group(2)
    target_nick, remaining_args = parse_nick_flag(args)
    prefix = get_prefix(bot)
    requester = trigger.nick

    if target_nick is not None:
        if target_nick not in user_locations:
            bot.say(
                f"{target_nick} has not set a location. "
                f"They need to use: {prefix}register_location <location>"
            )
            return
        loc = user_locations[target_nick]
        lat, lon, display_name = loc["lat"], loc["lon"], loc["name"]
    else:
        lat, lon, display_name = resolve_location(requester, remaining_args)
        if not lat:
            bot.say(
                f"No location found. Use {prefix}ef <location> or "
                f"{prefix}register_location <location> to save one."
            )
            return

    url = f"https://api.pirateweather.net/forecast/{WEATHER_API_KEY}/{lat},{lon}?units=si"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except Exception as e:
        bot.say(f"Error retrieving forecast: {e}")
        return

    if "daily" not in data or "data" not in data["daily"]:
        bot.say("No forecast data available.")
        return

    daily_data = data["daily"]["data"]
    if not daily_data:
        bot.say("No forecast data available.")
        return

    count = len(daily_data)
    bot.say(
        f"📅 Sending \x02{count}-day extended forecast\x02 for "
        f"{display_name} via PM, {requester}."
    )
    threading.Thread(
        target=send_forecast_pm,
        args=(bot, requester, daily_data, display_name),
        daemon=True,
    ).start()


@sopel.plugin.command("space", "spaceweather")
def space_weather(bot, trigger):
    args = trigger.group(2)
    target_nick, remaining_args = parse_nick_flag(args)
    prefix = get_prefix(bot)

    if target_nick is not None:
        if target_nick not in user_locations:
            bot.say(
                f"{target_nick} has not set a location. "
                f"They need to use: {prefix}register_location <location>"
            )
            return
        loc = user_locations[target_nick]
        lat, lon, display_name = loc["lat"], loc["lon"], loc["name"]
    else:
        lat, lon, display_name = resolve_location(trigger.nick, remaining_args)

    # We proceed even if no location is found, to show global stats.

    def get_json(url):
        try:
            return requests.get(url, timeout=5).json()
        except:
            return None

    # Global Kp Index
    kp_data = get_json("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json")
    kp = kp_data[-1]['kp_index'] if kp_data else "?"

    # Solar Wind
    wind_data = get_json("https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json")
    if wind_data:
        speed = wind_data[-1].get('proton_speed', '?')
        density = wind_data[-1].get('proton_density', '?')
    else:
        speed, density = "?", "?"

    # Magnetic Field
    mag_data = get_json("https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json")
    bz = mag_data[-1].get('bz_gsm', '?') if mag_data else "?"

    # Aurora Probability (Local)
    aurora_prob = None
    if lat and lon:
        ovation_data = get_json("https://services.swpc.noaa.gov/json/ovation_aurora_latest.json")
        if ovation_data and 'coordinates' in ovation_data:
            target_lon = round(lon) % 360
            target_lat = round(lat)
            for entry in ovation_data['coordinates']:
                if entry[0] == target_lon and entry[1] == target_lat:
                    aurora_prob = entry[2]
                    break
            if aurora_prob is None:
                aurora_prob = 0

    sep = "\x0314 · \x03"

    # Location / header
    if display_name:
        header = f"🌌 \x02{display_name}\x02"
    else:
        header = "🌌 \x02Global Space Weather\x02"

    # Kp formatting
    try:
        kp_val = float(kp)
        kp_color = "\x0303"
        if kp_val >= 4: kp_color = "\x0308"
        if kp_val >= 5: kp_color = "\x0307"
        if kp_val >= 6: kp_color = "\x0304"
        kp_str = f"☀️ Kp \x02{kp_color}{kp}\x03\x02"
    except:
        kp_str = f"☀️ Kp \x02{kp}\x02"

    wind_str = f"🌬️ \x02{speed}\x02 km/s  \x02{density}\x02 p/cm³"

    try:
        bz_val = float(bz)
        bz_color = "\x0303"
        if bz_val < -5: bz_color = "\x0308"
        if bz_val < -10: bz_color = "\x0304"
        bz_str = f"🧲 Bz \x02{bz_color}{bz} nT\x03\x02"
    except:
        bz_str = f"🧲 Bz \x02{bz} nT\x02"

    if aurora_prob is not None:
        prob_color = "\x0303"
        if aurora_prob > 10: prob_color = "\x0308"
        if aurora_prob > 50: prob_color = "\x0304"
        aurora_str = f"🌠 Aurora \x02{prob_color}{aurora_prob}%\x03\x02"
    elif lat is None:
        aurora_str = "🌠 Aurora \x02set location for local forecast\x02"
    else:
        aurora_str = None

    parts = [header, kp_str, wind_str, bz_str]
    if aurora_str:
        parts.append(aurora_str)

    bot.say(sep.join(parts))


@sopel.plugin.command("helpweather")
def help_weather(bot, trigger):
    p = get_prefix(bot)
    bot.say(
        f"🌦 WeatherBot Commands (1/3): "
        f"{p}w [location] = Current weather | "
        f"{p}w -n <user> = Weather for another user | "
        f"{p}f [location] = 4-day forecast | "
        f"{p}f -n <user> = Forecast for another user"
    )
    bot.say(
        f"🌦 WeatherBot Commands (2/3): "
        f"{p}ef [location] = Extended 8-day forecast via PM | "
        f"{p}ef -n <user> = Extended forecast for another user via PM | "
        f"{p}wa = PM me active alerts for my location | "
        f"{p}wa -n <user> = PM me alerts for another user"
    )
    bot.say(
        f"🌦 WeatherBot Commands (3/3): "
        f"{p}space [location] = Space weather & aurora | "
        f"{p}register_location <location> = Save your location | "
        f"{p}change_location <location> = Update saved location | "
        f"{p}unregister_location = Remove saved location"
    )
