import os
import smtplib
import sys
import time
from email.mime.text import MIMEText

import requests
from datetime import datetime, timedelta, timezone

API_URL = "https://wapi.wearepublic.nl/v2.0/events/"
API_KEY = "YDQ-Ep-Jy6gvLiKa4yUjC!ZUaCJCssu7sd@HQpBF!muTeU_P-HvigpL!-anTaV6y"

QUERY = "Alles"
DISCIPLINES = "Muziek"
MAX_DAYS_AHEAD = 120

# ✉️ Mailinstellingen
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
JSONBIN_ID = "684d5c4c8a456b7966adff04"
JSONBIN_KEY = "$2a$10$st35O.PoBykUmiVS/BbNXOYAktXNS16zl.U5MSRmsjJOFixaAOB7C"

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# JSONBIN_ID = os.getenv("JSONBIN_ID")
# JSONBIN_KEY = os.getenv("JSONBIN_API_KEY")

SEEN_RETENTION_DAYS = 180
HTTP_TIMEOUT = 30
JSONBIN_MAX_ATTEMPTS = 4


def _jsonbin_request(method, url, **kwargs):
    last_err = None
    for attempt in range(JSONBIN_MAX_ATTEMPTS):
        try:
            response = requests.request(method, url, timeout=HTTP_TIMEOUT, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < JSONBIN_MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)
    raise last_err


def load_seen_ids():
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}/latest"
    headers = {
        "X-Master-Key": JSONBIN_KEY,
        "X-Bin-Meta": "false"
    }
    try:
        response = _jsonbin_request("GET", url, headers=headers)
    except requests.exceptions.RequestException as e:
        # Bij stilletjes lege set teruggeven zouden ALLE events opnieuw als
        # 'nieuw' worden gezien en gemaild. Liever harde stop.
        print(f"Kon seen_ids niet laden van jsonbin.io: {e}", file=sys.stderr)
        sys.exit(1)

    data = response.json() or {}
    # Backwards-compat: oude bin was een list van IDs.
    if isinstance(data, list):
        today = datetime.now(timezone.utc).date().isoformat()
        return {eid: today for eid in data}
    return dict(data)


def save_seen_ids(seen):
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_KEY
    }
    _jsonbin_request("PUT", url, headers=headers, json=seen)


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

    new_events = [ev for ev in events if ev["id"] not in seen]

    if not new_events:
        print("Geen nieuwe interessante events gevonden.")
        return

    print(f"🎭 Nieuwe interessante events gevonden: {len(new_events)}\n")

    nl_months = {
        'January': 'januari', 'February': 'februari', 'March': 'maart',
        'April': 'april', 'May': 'mei', 'June': 'juni',
        'July': 'juli', 'August': 'augustus', 'September': 'september',
        'October': 'oktober', 'November': 'november', 'December': 'december'
    }

    lines = []
    for ev in new_events:
        title = ev["title"]
        uri = ev['uri']
        link = f"https://wearepublic.nl/programma/{uri}"

        date_str = ev.get("start_date", "")
        if date_str:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime("%-d %B %Y %H:%M")  # %-d verwijdert voorloopnul bij dag
            for en, nl in nl_months.items():
                formatted_date = formatted_date.replace(en, nl)
            formatted_date += " uur"
        else:
            formatted_date = "Datum onbekend"

        disciplines = ", ".join(d["name"] for d in ev.get("disciplines", []))
        discipline_text = f" ({disciplines})" if disciplines else ""
        lines.append(f'📅 {formatted_date} - 🎭 <a href="{link}">{title}</a>{discipline_text}')

    # State eerst opslaan: als jsonbin.io faalt mag de mail NIET uit,
    # anders krijgen we bij de volgende run dezelfde events opnieuw.
    today = datetime.now(timezone.utc).date().isoformat()
    for ev in new_events:
        seen[ev["id"]] = today
    seen = prune_seen(seen)

    try:
        save_seen_ids(seen)
    except requests.exceptions.RequestException as e:
        print(
            f"Opslaan van seen_ids mislukte ({e}); mail wordt NIET verzonden "
            "om dubbele meldingen te voorkomen. Volgende run probeert opnieuw.",
            file=sys.stderr,
        )
        sys.exit(1)

    send_email(lines)


if __name__ == "__main__":
    main()