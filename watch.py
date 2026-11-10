#!/usr/bin/env python3
"""Watch the HK Immigration ID-card booking quota for one date and push to ntfy.

Stdlib only. Needs NTFY_TOPIC in the environment. Set TEST_PUSH=true to also
send a "watcher running" push with the current status.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TARGET = "11/13/2026"
TARGET_LABEL = "Fri Nov 13"
HKT = timezone(timedelta(hours=8))
STOP_AFTER = datetime(2026, 11, 13, 16, 30, tzinfo=HKT)
FEED = "https://eservices.es2.immd.gov.hk/surgecontrolgate/ticket/getSituation?svcId=579&t={}"
BOOK = "https://www.gov.hk/icbooking"
NTFY = "https://ntfy.sh/"
STATE = Path(__file__).resolve().parent / "state.json"
FAIL_ALERT_AFTER = 6  # consecutive failed fetches (about an hour) before warning

# Kowloon first, then the rest in rough order of travel time.
ORDER = ["RKO", "RHK", "RTK", "FTO", "TMO", "YLO"]
SHORT = {"RKO": "Kowloon", "RHK": "Wan Chai", "RTK": "Tseung Kwan O",
         "FTO": "Fo Tan", "TMO": "Tuen Mun", "YLO": "Yuen Long"}
NAMES = {"RKO": "Kowloon Office", "RHK": "Hong Kong Office (Wan Chai)",
         "RTK": "Tseung Kwan O Office", "FTO": "Fo Tan Office",
         "TMO": "Tuen Mun Office", "YLO": "Yuen Long Office"}
WHERE = {
    "RKO": "3/F Cheung Sha Wan Govt Offices, 303 Cheung Sha Wan Rd\nMTR Sham Shui Po, Exit C1",
    "RHK": "8/F Immigration Tower, 7 Gloucester Rd\nMTR Wan Chai, Exit A5",
    "RTK": "Immigration HQ, 61 Po Yap Rd\nMTR Tseung Kwan O, Exit B1",
    "FTO": "4/F Jubilee Square, 2-18 Lok King St\nMTR Fo Tan, Exit C",
    "TMO": "3/F Tuen Mun Siu Lun Govt Complex, 19 Siu Lun St\nLight Rail Sam Shing",
    "YLO": "1/F Yuen Long Govt Offices, 2 Kiu Lok Sq\nMTR Long Ping, Exit E",
}
STATUS = {"quota-g": "Quota Available", "quota-y": "Limited Quota", "quota-r": "Full"}


def log(msg):
    print(f"{datetime.now(HKT):%Y-%m-%d %H:%M} HKT  {msg}", flush=True)


def push(topic, title, message, priority=3, tags=None):
    body = {"topic": topic, "title": title, "message": message, "priority": priority,
            "click": BOOK, "actions": [{"action": "view", "label": "Open booking", "url": BOOK}]}
    if tags:
        body["tags"] = tags
    req = urllib.request.Request(NTFY, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            urllib.request.urlopen(req, timeout=20).read()
            log(f"pushed: {title}")
            return
        except Exception as e:
            log(f"push failed ({e}), attempt {attempt + 1}")
            time.sleep(5)
    sys.exit("could not reach ntfy")


def fetch():
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(FEED.format(int(time.time() * 1000)),
                                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            last = e
            time.sleep(10)
    raise last


def describe(hits):
    return "\n\n".join(f"{NAMES[o]}: {STATUS[q]}\n{WHERE[o]}" for o, q in hits)


def main():
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        sys.exit("NTFY_TOPIC is not set")
    test = os.environ.get("TEST_PUSH", "").lower() == "true"

    if datetime.now(HKT) > STOP_AFTER:
        log("past stop time, nothing to do")
        return

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    prev = state.get("open", [])

    try:
        d = fetch()
    except Exception as e:
        state["fail_count"] = state.get("fail_count", 0) + 1
        log(f"feed fetch failed ({state['fail_count']} in a row): {e}")
        if state["fail_count"] == FAIL_ALERT_AFTER or test:
            push(topic, "HKID watcher can't reach the feed",
                 f"{state['fail_count']} failed checks in a row. Check the booking site yourself for now.\nLast error: {e}")
        STATE.write_text(json.dumps(state, indent=1) + "\n")
        return

    if state.get("fail_count", 0) >= FAIL_ALERT_AFTER:
        push(topic, "HKID watcher is reading the feed again", "Back to normal checks.", priority=2)
    state.pop("fail_count", None)

    updated = d.get("lastUpdateTime", "?")
    rows = {r.get("officeId"): r.get("quotaR") for r in d.get("data", []) if r.get("date") == TARGET}
    hits = [(o, rows[o]) for o in ORDER if rows.get(o) in ("quota-g", "quota-y")]
    hits += [(o, q) for o, q in rows.items() if o not in ORDER and q in ("quota-g", "quota-y")]
    now_open = [o for o, _ in hits]

    if not rows:
        log(f"no rows for {TARGET} (feed updated {updated} HKT)")
        summary = f"The feed has no rows for {TARGET_LABEL} right now."
    elif hits:
        log(f"OPEN on {TARGET}: " + ", ".join(f"{o} {rows[o]}" for o in now_open) + f" (feed {updated})")
        summary = describe(hits)
    else:
        log(f"all full on {TARGET} (feed updated {updated} HKT)")
        summary = f"All offices full for {TARGET_LABEL}."

    if rows and set(now_open) != set(prev):
        if hits:
            names = ", ".join(SHORT.get(o, o) for o in now_open)
            push(topic, f"HKID {TARGET_LABEL} open: {names}",
                 f"{summary}\n\nFeed updated {updated} HKT. These go fast.",
                 priority=4, tags=["rotating_light"])
        else:
            push(topic, f"HKID {TARGET_LABEL}: full again",
                 f"The slots that opened earlier are gone.\nFeed updated {updated} HKT.")
        state["open"] = now_open
    elif test:
        push(topic, "HKID watcher started",
             f"Test push. Checking {TARGET_LABEL} about every 10 minutes until 4:30 pm HKT that day.\n\n"
             f"Right now: {summary}\nFeed updated {updated} HKT.",
             tags=["white_check_mark"])

    STATE.write_text(json.dumps(state, indent=1) + "\n")


if __name__ == "__main__":
    main()
