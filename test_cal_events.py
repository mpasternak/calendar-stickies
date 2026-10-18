"""Testy logiki karteczek kalendarza (bez EventKit)."""

from datetime import date, datetime

import cal_events as ce

TODAY = date(2026, 10, 19)  # poniedziałek
NOW = datetime(2026, 10, 19, 10, 0)


def _ev(title, start, end, all_day=False, calendar="Praca", **kw):
    e = {
        "title": title,
        "start": start,
        "end": end,
        "all_day": all_day,
        "calendar": calendar,
        "color": "#ff0000",
        "location": "",
        "url": "",
    }
    e.update(kw)
    return e


def _report(events, days=2, exclude=()):
    return ce.build_report(events, days, TODAY, NOW, set(exclude))


def test_day_labels():
    assert ce.day_label(TODAY, TODAY) == "Dziś · pon 19.10"
    assert ce.day_label(date(2026, 10, 20), TODAY) == "Jutro · wt 20.10"
    assert ce.day_label(date(2026, 10, 25), TODAY) == "nd 25.10"


def test_past_live_and_future_today():
    rep = _report(
        [
            _ev("rano", datetime(2026, 10, 19, 8), datetime(2026, 10, 19, 9)),
            _ev("teraz", datetime(2026, 10, 19, 9, 30), datetime(2026, 10, 19, 11)),
            _ev("później", datetime(2026, 10, 19, 15), datetime(2026, 10, 19, 16)),
        ]
    )
    items = rep["sections"][0]["items"]
    assert [(i["title"], i["dim"], i["now"]) for i in items] == [
        ("rano", True, False),
        ("teraz", False, True),
        ("później", False, False),
    ]
    assert rep["summary"].startswith("dziś jeszcze 2")


def test_all_day_first_and_multiday_spans_days():
    rep = _report(
        [
            _ev("spotkanie", datetime(2026, 10, 19, 9), datetime(2026, 10, 19, 10)),
            # EventKit: całodniowe kończy się 23:59:59 ostatniego dnia
            _ev("wyjazd", datetime(2026, 10, 19), datetime(2026, 10, 20, 23, 59, 59), all_day=True),
        ]
    )
    assert [i["title"] for i in rep["sections"][0]["items"]] == ["wyjazd", "spotkanie"]
    assert [i["title"] for i in rep["sections"][1]["items"]] == ["wyjazd"]
    assert rep["sections"][0]["items"][0]["time"] == ""


def test_all_day_ending_at_midnight_is_exclusive():
    rep = _report([_ev("jeden dzień", datetime(2026, 10, 19), datetime(2026, 10, 20), all_day=True)])
    assert len(rep["sections"][0]["items"]) == 1
    assert rep["sections"][1]["items"] == []


def test_overnight_event_continues_next_day():
    rep = _report([_ev("dyżur", datetime(2026, 10, 19, 20), datetime(2026, 10, 20, 8))])
    first, second = rep["sections"][0]["items"][0], rep["sections"][1]["items"][0]
    assert (first["time"], first["end"]) == ("20:00", "…")
    assert (second["time"], second["end"]) == ("…", "08:00")


def test_excluded_calendars_and_duplicates():
    s = datetime(2026, 10, 19, 12)
    e = datetime(2026, 10, 19, 13)
    rep = _report(
        [
            _ev("narada", s, e, calendar="Praca"),
            _ev("narada", s, e, calendar="Konto Google"),  # to samo zaproszenie drugi raz
            _ev("Święto", datetime(2026, 10, 19), datetime(2026, 10, 20), all_day=True, calendar="Święta"),
        ],
        exclude={"Święta"},
    )
    assert [i["title"] for i in rep["sections"][0]["items"]] == ["narada"]


def test_only_http_urls_are_links():
    s, e = datetime(2026, 10, 19, 12), datetime(2026, 10, 19, 13)
    rep = _report([_ev("a", s, e, url="https://meet.example/x"), _ev("b", s, e, url="message:%3Cabc%3E")])
    assert [i["url"] for i in rep["sections"][0]["items"]] == ["https://meet.example/x", ""]


def test_weekend_flag_and_section_count():
    rep = _report([], days=7)
    assert len(rep["sections"]) == 7
    assert [s["weekend"] for s in rep["sections"]] == [False] * 5 + [True, True]
