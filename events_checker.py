import json
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

import requests
from datetime import datetime, timedelta, timezone

API_URL = "https://wapi.wearepublic.nl/v2.0/events/"
API_KEY = "YDQ-Ep-Jy6gvLiKa4yUjC!ZUaCJCssu7sd@HQpBF!muTeU_P-HvigpL!-anTaV6y"

SEEN_FILE = Path("seen_events.json")

# ✉️ Mailinstellingen
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

SEEN_RETENTION_DAYS = 180
HTTP_TIMEOUT = 30

NL_MONTHS = {
    'January': 'januari', 'February': 'februari', 'March': 'maart',
    'April': 'april', 'May': 'mei', 'June': 'juni',
    'July': 'juli', 'August': 'augustus', 'September': 'september',
    'October': 'oktober', 'November': 'november', 'December': 'december',
}


def load_seen_ids():
    """Lees seen-state uit SEEN_FILE. Geeft None terug als de file ontbreekt,
    leeg is of een lege dict/lijst bevat — main() behandelt dat als bootstrap
    zonder mail. Zonder die check zou een per ongeluk lege state alle events
    als 'nieuw' mailen (80-event bom)."""
    if not SEEN_FILE.exists():
        return None
    text = SEEN_FILE.read_text().strip()
    if not text:
        return None
    data = json.loads(text)
    # Backwards-compat: vroeger was de file een list van IDs.
    if isinstance(data, list):
        if not data:
            return None
        today = datetime.now(timezone.utc).date().isoformat()
        return {eid: today for eid in data}
    if not data:
        return None
    return data


def save_seen_ids(seen):
    SEEN_FILE.write_text(json.dumps(seen, indent=2, sort_keys=True) + "\n")


def prune_seen(seen):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_RETENTION_DAYS)).date().isoformat()
    return {eid: d for eid, d in seen.items() if d >= cutoff}


def fetch_events():
    headers = {
        "x-api-key": API_KEY,
        "origin": "https://www.wearepublic.nl",
        "accept": "application/json"
    }
    params = {
        "limit": 80,
        "page": 1,
        "preset": "just-confirmed"
    }
    response = requests.get(API_URL, headers=headers, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json().get("events", [])


def format_event_line(ev):
    title = ev["title"]
    link = f"https://wearepublic.nl/programma/{ev['uri']}"

    date_str = ev.get("start_date", "")
    if date_str:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        formatted_date = date_obj.strftime("%-d %B %Y %H:%M")  # %-d verwijdert voorloopnul bij dag
        for en, nl in NL_MONTHS.items():
            formatted_date = formatted_date.replace(en, nl)
        formatted_date += " uur"
    else:
        formatted_date = "Datum onbekend"

    disciplines = ", ".join(d["name"] for d in ev.get("disciplines", []))
    discipline_text = f" ({disciplines})" if disciplines else ""
    return f'📅 {formatted_date} - 🎭 <a href="{link}">{title}</a>{discipline_text}'


def send_email(event_lines):
    html_content = '<br>'.join(event_lines)
    msg = MIMEText(html_content, 'html')
    msg["Subject"] = "🎭 Nieuwe interessante events!"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print(f"✅ Mail verzonden naar {EMAIL_TO}")


def main():
    seen = load_seen_ids()
    events = fetch_events()
    today = datetime.now(timezone.utc).date().isoformat()

    # Bootstrap: geen seen-file betekent eerste run. Alle huidige events
    # registreren we als 'seen' zonder te mailen, anders krijg je 80 events
    # ineens. Vanaf de volgende run worden alleen écht nieuwe events gemaild.
    if seen is None:
        save_seen_ids({ev["id"]: today for ev in events})
        print(f"Bootstrap: {len(events)} events geseed als seen. Geen mail verzonden.")
        return

    new_events = [ev for ev in events if ev["id"] not in seen]

    if not new_events:
        print("Geen nieuwe interessante events gevonden.")
        return

    print(f"🎭 Nieuwe interessante events gevonden: {len(new_events)}\n")

    lines = [format_event_line(ev) for ev in new_events]

    # State eerst opslaan, dan pas mailen — als de save faalt willen we de
    # mail niet versturen, anders krijgen we volgende run dubbele meldingen.
    for ev in new_events:
        seen[ev["id"]] = today
    seen = prune_seen(seen)
    save_seen_ids(seen)

    send_email(lines)


if __name__ == "__main__":
    main()