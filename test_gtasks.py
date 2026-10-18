"""Testy grupowania zadań Google Tasks (bez sieci)."""

from datetime import date, datetime

import gtasks as gt

TODAY = date(2026, 10, 19)
NOW = datetime(2026, 10, 19, 10, 0)


def _t(title, due=None, **kw):
    t = {"title": title, "list": "Moje zadania", "color": "#e0a84f", "status": "needsAction"}
    if due:
        t["due"] = f"{due}T00:00:00.000Z"
    t.update(kw)
    return t


def test_due_date_ignores_time_part():
    assert gt.due_date(_t("a", "2026-10-19")) == TODAY
    assert gt.due_date(_t("a")) is None


def test_groups_in_order_with_counts():
    rep = gt.build_report(
        [
            _t("bez terminu"),
            _t("później", "2026-10-30"),
            _t("jutro", "2026-10-20"),
            _t("dziś", "2026-10-19"),
            _t("zaległe", "2026-10-01"),
        ],
        TODAY,
        NOW,
    )
    assert [s["title"] for s in rep["sections"]] == [
        "Zaległe (1)",
        "Dziś (1)",
        "Jutro (1)",
        "Później (1)",
        "Bez terminu (1)",
    ]
    assert rep["summary"] == "1 zaległe · 1 na dziś · razem 5"


def test_dates_shown_only_where_useful_and_overdue_bold():
    rep = gt.build_report([_t("z", "2026-10-01"), _t("d", "2026-10-19"), _t("p", "2026-11-05")], TODAY, NOW)
    by = {s["title"].split(" (")[0]: s["items"][0] for s in rep["sections"]}
    assert by["Zaległe"]["time"] == "1.10" and by["Zaległe"]["now"] is True
    assert by["Dziś"]["time"] == ""
    assert by["Później"]["time"] == "5.11"


def test_subtask_marker_and_link():
    rep = gt.build_report([_t("pod", parent="X", webViewLink="https://tasks.google.com/task/1")], TODAY, NOW)
    it = rep["sections"][0]["items"][0]
    assert it["title"] == "↳ pod"
    assert it["url"] == "https://tasks.google.com/task/1"


def test_empty():
    rep = gt.build_report([], TODAY, NOW)
    assert rep["sections"] == [] and rep["summary"] == "brak zadań 🎉"
