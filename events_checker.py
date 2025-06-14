import os
import smtplib
from email.mime.text import MIMEText

import requests
from datetime import datetime
from pathlib import Path

API_URL = "https://wapi.wearepublic.nl/v2.0/events/"
API_KEY = os.getenv("API_KEY")

QUERY = "Alles"
DISCIPLINES = "Muziek"
MAX_DAYS_AHEAD = 120
SEEN_FILE = Path("seen_events.json")

# ✉️ Mailinstellingen
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

JSONBIN_ID = os.getenv("JSONBIN_ID")
JSONBIN_KEY = os.getenv("JSONBIN_API_KEY")

def load_seen_ids():
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}/latest"
    headers = {
        "X-Master-Key": JSONBIN_KEY,
        "X-Bin-Meta": "false"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return set(response.json() or [])
    else:
        return set()

def format_date(iso_string):
    dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.strftime("📅 %a %d %B %Y om %H:%M")


def save_seen_ids(ids):
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_KEY
    }
    response = requests.put(url, headers=headers, json=list(ids))
    response.raise_for_status()

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
