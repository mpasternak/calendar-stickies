#!/usr/bin/env python3
"""Spotkania z kalendarza macOS (EventKit) — dla karteczek Übersicht.

Czyta wszystkie kalendarze widoczne w aplikacji Kalendarz (iCloud, Google, Exchange…)
bezpośrednio przez EventKit, poza wykluczonymi w ~/.config/calendar-stickies/config.json
(klucz "exclude_calendars" — nazwy kalendarzy; wzór: config.example.json).

Użycie:
    python cal_events.py                  # dziś + jutro (tekst, test w terminalu)
    python cal_events.py --days 7 --json  # tydzień, JSON dla widgetu
    python cal_events.py --calendars      # nazwy kalendarzy (do konfiguracji)

Wymaga: pyobjc-framework-EventKit (install.sh zakłada .venv). Przy pierwszym
uruchomieniu z Übersicht macOS zapyta o dostęp do Kalendarzy dla Übersicht.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger("cal_events")

CONFIG = Path(os.environ.get("CALENDAR_STICKIES_CONFIG", "~/.config/calendar-stickies/config.json")).expanduser()
WEEKDAYS = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]


def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text())
    except FileNotFoundError:
        return {}  # brak konfiguracji = wszystkie kalendarze


# --- EventKit -----------------------------------------------------------------------


def _store():
    """EKEventStore z dostępem do wydarzeń (przy pierwszym razie macOS pyta użytkownika)."""
    import EventKit  # import tu, żeby testy logiki nie wymagały pyobjc

    store = EventKit.EKEventStore.alloc().init()
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    granted = status in (EventKit.EKAuthorizationStatusFullAccess, EventKit.EKAuthorizationStatusAuthorized)
    if status == EventKit.EKAuthorizationStatusNotDetermined:
        result, done = {}, threading.Event()

        def handler(ok, _err):  # błąd = brak zgody; szczegół nie jest nam potrzebny
            result["ok"] = bool(ok)
            done.set()

        if hasattr(store, "requestFullAccessToEventsWithCompletion_"):  # macOS 14+
            store.requestFullAccessToEventsWithCompletion_(handler)
        else:
            store.requestAccessToEntityType_completion_(EventKit.EKEntityTypeEvent, handler)
        done.wait(timeout=60)
        granted = result.get("ok", False)
    if not granted:
        raise PermissionError(
            "Brak dostępu do Kalendarzy — Ustawienia systemowe → Prywatność i ochrona → "
            "Kalendarze: włącz dla Übersicht (i Terminala, jeśli testujesz z terminala)."
        )
    return store


def _dt(nsdate) -> datetime:
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970())


def _hex(nscolor) -> str:
    """NSColor kalendarza → #rrggbb (kolor kropki przy wydarzeniu)."""
    if nscolor is None:
        return ""
    c = nscolor.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
    if c is None:
        return ""
    rgb = (c.redComponent(), c.greenComponent(), c.blueComponent())
    return "#" + "".join(f"{round(x * 255):02x}" for x in rgb)


def list_calendars() -> list[str]:
    import EventKit

    cals = _store().calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    return sorted({c.title() for c in cals})


def fetch_events(start: datetime, end: datetime) -> list[dict]:
    """Wydarzenia nachodzące na [start, end) — powtarzające się już rozwinięte przez EventKit."""
    from Foundation import NSDate

    store = _store()
    pred = store.predicateForEventsWithStartDate_endDate_calendars_(
        NSDate.dateWithTimeIntervalSince1970_(start.timestamp()),
        NSDate.dateWithTimeIntervalSince1970_(end.timestamp()),
        None,  # None = wszystkie kalendarze; wykluczenia robimy sami (po nazwie)
    )
    events = []
    for ev in store.eventsMatchingPredicate_(pred) or []:
        cal = ev.calendar()
        url = ev.URL()
        events.append(
            {
                "title": (ev.title() or "").strip().split("\n")[0] or "(bez tytułu)",
                "start": _dt(ev.startDate()),
                "end": _dt(ev.endDate()),
                "all_day": bool(ev.isAllDay()),
                "calendar": cal.title() if cal else "",
                "color": _hex(cal.color()) if cal else "",
                "location": (ev.location() or "").split("\n")[0],
                "url": str(url.absoluteString()) if url else "",
            }
        )
    return events


# --- raport (czysta logika — testowana bez EventKit) ---------------------------------


def day_label(d: date, today: date) -> str:
    rel = {0: "Dziś", 1: "Jutro"}.get((d - today).days)
    short = f"{WEEKDAYS[d.weekday()]} {d.day}.{d.month:02d}"
    return f"{rel} · {short}" if rel else short


def _covers(ev: dict, d: date) -> bool:
    """Czy wydarzenie trwa choć chwilę w dniu d (koniec traktujemy jako wyłączny)."""
    day_start = datetime.combine(d, datetime.min.time())
    day_end = day_start + timedelta(days=1)
    end = ev["end"] if ev["end"] > ev["start"] else ev["start"] + timedelta(seconds=1)
    return ev["start"] < day_end and end > day_start


def _item(ev: dict, d: date, now: datetime) -> dict:
    if ev["all_day"]:
        time_s, end_s, dim, live = "", "", False, False
    else:
        time_s = ev["start"].strftime("%H:%M") if ev["start"].date() == d else "…"
        end_s = ev["end"].strftime("%H:%M") if ev["end"].date() == d else "…"
        dim = ev["end"] <= now
        live = ev["start"] <= now < ev["end"]
    tip = ev["title"]
    if not ev["all_day"]:
        tip += f"\n{ev['start']:%d.%m %H:%M} – {ev['end']:%d.%m %H:%M}"
    if ev["location"]:
        tip += f"\n📍 {ev['location']}"
    if ev["calendar"]:
        tip += f"\n🗓 {ev['calendar']}"
    return {
        "time": time_s,
        "end": end_s,
        "title": ev["title"],
        "sub": ev["location"],
        "color": ev.get("color", ""),
        "tip": tip,
        "url": ev["url"] if ev["url"].startswith(("http://", "https://")) else "",
        "dim": dim,  # już się skończyło
        "now": live,  # trwa teraz
    }


def build_report(events: list[dict], days: int, today: date, now: datetime, exclude: set[str]) -> dict:
    events = [e for e in events if e["calendar"] not in exclude]
    # To samo spotkanie bywa w kilku kalendarzach (np. zaproszenie na dwa konta) — pokaż raz.
    seen, uniq = set(), []
    for e in events:
        key = (e["start"], e["title"])
        if key not in seen:
            seen.add(key)
            uniq.append(e)
    sections = []
    for i in range(days):
        d = today + timedelta(days=i)
        todays = [e for e in uniq if _covers(e, d)]
        todays.sort(key=lambda e: (not e["all_day"], e["start"], e["title"].lower()))
        sections.append(
            {
                "title": day_label(d, today),
                "date": d.isoformat(),
                "weekend": d.weekday() >= 5,
                "items": [_item(e, d, now) for e in todays],
            }
        )
    left_today = sum(1 for it in sections[0]["items"] if it["time"] and not it["dim"]) if sections else 0
    total = sum(len(s["items"]) for s in sections)
    return {
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "summary": f"dziś jeszcze {left_today} · razem {total}",
        "sections": sections,
    }


def _text(rep: dict) -> str:
    lines = [rep["summary"], ""]
    for s in rep["sections"]:
        lines.append(f"— {s['title']} —")
        for it in s["items"]:
            mark = "▶" if it["now"] else ("·" if it["dim"] else " ")
            place = f"  📍 {it['sub']}" if it["sub"] else ""
            lines.append(f" {mark} {it['time'] or 'cały d.':>7}  {it['title']}{place}")
        if not s["items"]:
            lines.append("   (nic)")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Spotkania z kalendarza macOS (EventKit).")
    ap.add_argument("--days", type=int, default=2, help="ile dni od dziś (domyślnie 2 = dziś + jutro)")
    ap.add_argument("--json", action="store_true", help="wyjście JSON (dla widgetu Übersicht)")
    ap.add_argument("--calendars", action="store_true", help="wypisz nazwy kalendarzy i zakończ")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(message)s")

    try:
        if a.calendars:
            print("\n".join(list_calendars()))
            return 0
        now = datetime.now()
        start = datetime.combine(now.date(), datetime.min.time())
        exclude = set(load_config().get("exclude_calendars", []))
        events = fetch_events(start, start + timedelta(days=a.days))
        rep = build_report(events, a.days, now.date(), now, exclude)
    except (OSError, ValueError, ImportError) as exc:
        # Brak dostępu do kalendarzy (PermissionError) / brak pyobjc / zepsuty config —
        # krótki komunikat; widget pokaże wtedy ostatnie zapamiętane dane.
        log.error("Nie udało się odczytać kalendarza: %s", exc)
        if a.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(rep, ensure_ascii=False) if a.json else _text(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
