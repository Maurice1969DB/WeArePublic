import smtplib
from email.mime.text import MIMEText

import requests
import json
from datetime import datetime
from pathlib import Path

API_URL = "https://wapi.wearepublic.nl/v2.0/events/"
API_KEY = "YDQ-Ep-Jy6gvLiKa4yUjC!ZUaCJCssu7sd@HQpBF!muTeU_P-HvigpL!-anTaV6y"

QUERY = "Alles"
DISCIPLINES = "Muziek"
MAX_DAYS_AHEAD = 120
SEEN_FILE = Path("seen_events.json")

# ✉️ Mailinstellingen
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = "mauricevanloon1969@gmail.com"
EMAIL_TO = "mauricevanloon1969@gmail.com"
EMAIL_USER = "mauricevanloon1969@gmail.com"
EMAIL_PASS = "tyzw eaux uoqp vmxn"

def format_date(iso_string):
    dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.strftime("📅 %a %d %B %Y om %H:%M")

def load_seen_ids():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen_ids(ids):
    SEEN_FILE.write_text(json.dumps(list(ids), indent=2))

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
    response = requests.get(API_URL, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("events", [])

def filter_events(events):
    today = datetime.now()
    # def is_relevant(ev):
    #     try:
    #         start_date = datetime.strptime(ev["start_date"], "%Y-%m-%dT%H:%M:%S.%fZ")
    #         delta_days = (start_date - today).days
    #         discipline_names = ", ".join(d["name"] for d in ev.get("disciplines", []))
    #         return discipline_names in DISCIPLINES
    #     except Exception as e:
    #         print(f"Fout bij filteren event: {e}")
    #         return False
    return list(events)

def send_email(event_lines):
    msg = MIMEText("\n".join(event_lines))
    msg["Subject"] = "🎭 Nieuwe interessante events!"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print(f"✅ Mail verzonden naar {EMAIL_TO}")

def main():
    seen_ids = load_seen_ids()
    new_ids = set()
    new_events = []

    events = fetch_events()
    filtered = filter_events(events)

    for ev in filtered:
        if ev["id"] not in seen_ids:
            new_ids.add(ev["id"])
            new_events.append(ev)

    if new_events:
        print(f"🎭 Nieuwe interessante events gevonden: {len(new_events)}\n")
        lines = []
        for ev in new_events:
            title = ev["title"]
            link = f"https://wearepublic.nl/programma/{ev['uri']}"
            lines.append(f"🎭 {title} – {link}")
        send_email(lines)
        save_seen_ids(seen_ids.union(new_ids))
    else:
        print("Geen nieuwe interessante events gevonden.")

if __name__ == "__main__":
    main()