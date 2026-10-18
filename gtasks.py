#!/usr/bin/env python3
"""Zadania z Google Tasks — dla karteczki Übersicht.

Google nie udostępnia zadań przez CalDAV (więc nie ma ich ani w Przypomnieniach,
ani w EventKit) — czytamy je z Google Tasks API (tylko odczyt).

Jednorazowo:
    1. Google Cloud Console → nowy projekt → włącz „Google Tasks API",
       ekran zgody OAuth (typ: zewnętrzny, opublikuj — patrz README),
       Dane logowania → Identyfikator klienta OAuth → „Aplikacja komputerowa"
       → pobierz JSON jako ~/.config/calendar-stickies/google-client.json
    2. python gtasks.py auth     # otworzy przeglądarkę, zapisze token

Potem:
    python gtasks.py             # tekst (test w terminalu)
    python gtasks.py --json      # JSON dla widgetu

Tylko biblioteka standardowa.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import logging
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger("gtasks")

CONF_DIR = Path("~/.config/calendar-stickies").expanduser()
CLIENT = Path(os.environ.get("GTASKS_CLIENT", CONF_DIR / "google-client.json")).expanduser()
TOKEN = Path(os.environ.get("GTASKS_TOKEN", CONF_DIR / "google-token.json")).expanduser()
SCOPE = "https://www.googleapis.com/auth/tasks.readonly"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
API = "https://tasks.googleapis.com/tasks/v1"
TIMEOUT = 15
# Kolory list (kropka przy zadaniu) — kolejne listy dostają kolejne kolory.
PALETTE = ["#e0a84f", "#4f9be0", "#5fc28a", "#c27ae0", "#e06a6a", "#4fd0d0", "#b0b04f"]


class AuthError(RuntimeError):
    """Brak / nieważna autoryzacja — trzeba uruchomić `gtasks.py auth`."""


# --- OAuth (aplikacja komputerowa: przekierowanie na 127.0.0.1 + PKCE) --------------


def _client() -> dict:
    try:
        data = json.loads(CLIENT.read_text())
    except FileNotFoundError as e:
        raise AuthError(f"Brak {CLIENT} — pobierz JSON klienta OAuth z Google Cloud (README)") from e
    return data.get("installed") or data.get("web") or data


def _post(url: str, fields: dict) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _save_token(tok: dict) -> None:
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.touch(mode=0o600, exist_ok=True)
    os.chmod(TOKEN, 0o600)  # refresh token = dostęp do zadań; tylko dla właściciela
    TOKEN.write_text(json.dumps(tok))


def authorize() -> None:
    """Interaktywne logowanie w przeglądarce; zapisuje refresh token."""
    client = _client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — nazwa wymagana przez BaseHTTPRequestHandler
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            ok = "code" in result and result.get("state") == state
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "Gotowe — możesz zamknąć tę kartę." if ok else "Logowanie nie powiodło się — wróć do terminala."
            self.wfile.write(f"<h3>{msg}</h3>".encode())

        def log_message(self, format, *args):  # noqa: A002 — bez logów serwera w terminalu
            return

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}/"
    url = (
        AUTH_URI
        + "?"
        + urllib.parse.urlencode(
            {
                "client_id": client["client_id"],
                "redirect_uri": redirect,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )
    print(f"Otwieram przeglądarkę. Jeśli się nie otworzy, wejdź na:\n{url}\n")
    webbrowser.open(url)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()
    if "error" in result or result.get("state") != state:
        raise AuthError(f"Logowanie przerwane: {result.get('error', 'zły parametr state')}")

    tok = _post(
        client.get("token_uri", TOKEN_URI),
        {
            "code": result["code"],
            "client_id": client["client_id"],
            "client_secret": client.get("client_secret", ""),
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
    )
    if "refresh_token" not in tok:
        raise AuthError("Google nie zwrócił refresh tokenu — usuń dostęp aplikacji w koncie Google i spróbuj ponownie")
    tok["expires_at"] = time.time() + tok.get("expires_in", 3600) - 60
    _save_token(tok)
    print(f"Zapisano token: {TOKEN}")


def access_token() -> str:
    try:
        tok = json.loads(TOKEN.read_text())
    except FileNotFoundError as e:
        raise AuthError("Brak autoryzacji — uruchom: python gtasks.py auth") from e
    if tok.get("access_token") and tok.get("expires_at", 0) > time.time():
        return tok["access_token"]
    client = _client()
    try:
        fresh = _post(
            client.get("token_uri", TOKEN_URI),
            {
                "client_id": client["client_id"],
                "client_secret": client.get("client_secret", ""),
                "refresh_token": tok["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise AuthError("Token Google wygasł lub cofnięto dostęp — uruchom: python gtasks.py auth") from e
        raise
    tok.update(access_token=fresh["access_token"], expires_at=time.time() + fresh.get("expires_in", 3600) - 60)
    _save_token(tok)
    return tok["access_token"]


# --- Tasks API --------------------------------------------------------------------------


def _api_get(path: str, token: str, params: dict | None = None) -> dict:
    url = f"{API}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _paged(path: str, token: str, params: dict) -> list[dict]:
    items, page = [], None
    while True:
        data = _api_get(path, token, {**params, **({"pageToken": page} if page else {})})
        items += data.get("items", [])
        page = data.get("nextPageToken")
        if not page:
            return items


def fetch_tasks() -> list[dict]:
    """Nieukończone zadania ze wszystkich list (każde z nazwą i kolorem listy)."""
    token = access_token()
    out = []
    lists = _paged("/users/@me/lists", token, {"maxResults": 100})
    for i, tl in enumerate(lists):
        color = PALETTE[i % len(PALETTE)]
        params = {"showCompleted": "false", "showHidden": "false", "maxResults": 100}
        for t in _paged(f"/lists/{urllib.parse.quote(tl['id'])}/tasks", token, params):
            if t.get("status") == "completed" or not (t.get("title") or "").strip():
                continue
            out.append({**t, "list": tl.get("title", ""), "color": color})
    return out


# --- raport (czysta logika — testowana bez sieci) --------------------------------------


def due_date(t: dict) -> date | None:
    """Termin zadania. API trzyma sam dzień (godzina zawsze 00:00Z) — bierzemy datę z napisu."""
    due = t.get("due")
    return date.fromisoformat(due[:10]) if due else None


def build_report(tasks: list[dict], today: date, now: datetime) -> dict:
    groups = {"Zaległe": [], "Dziś": [], "Jutro": [], "Później": [], "Bez terminu": []}
    for t in tasks:
        d = due_date(t)
        if d is None:
            key = "Bez terminu"
        elif d < today:
            key = "Zaległe"
        elif d == today:
            key = "Dziś"
        elif d == today + timedelta(days=1):
            key = "Jutro"
        else:
            key = "Później"
        groups[key].append((d, t))
    sections = []
    for name, items in groups.items():
        if not items:
            continue
        items.sort(key=lambda x: (x[0] or date.max, x[1].get("position", ""), x[1]["title"].lower()))
        rows = []
        for d, t in items:
            notes = (t.get("notes") or "").strip()
            tip = t["title"].strip() + (f"\n{notes[:300]}" if notes else "") + f"\n🗂 {t['list']}"
            show_date = name in ("Zaległe", "Później") and d is not None
            rows.append(
                {
                    "time": f"{d.day}.{d.month:02d}" if show_date else "",
                    "end": "",
                    "title": ("↳ " if t.get("parent") else "") + t["title"].strip(),
                    "sub": t["list"],
                    "color": t["color"],
                    "tip": tip,
                    "url": t.get("webViewLink", ""),
                    "dim": False,
                    "now": name == "Zaległe",  # pogrubienie = zaległe
                }
            )
        sections.append({"title": f"{name} ({len(rows)})", "items": rows})
    n_over, n_today = len(groups["Zaległe"]), len(groups["Dziś"])
    summary = f"{n_over} zaległe · {n_today} na dziś · razem {len(tasks)}" if tasks else "brak zadań 🎉"
    return {
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "summary": summary,
        "sections": sections,
    }


def _text(rep: dict) -> str:
    lines = [rep["summary"], ""]
    for s in rep["sections"]:
        lines.append(f"— {s['title']} —")
        lines += [f"   {it['time']:>5}  {it['title']}   [{it['sub']}]" for it in s["items"]]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Zadania z Google Tasks (tylko odczyt).")
    ap.add_argument("cmd", nargs="?", choices=["auth"], help="auth = zaloguj się do Google (jednorazowo)")
    ap.add_argument("--json", action="store_true", help="wyjście JSON (dla widgetu Übersicht)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(message)s")

    if a.cmd == "auth":
        try:
            authorize()
        except (AuthError, OSError, KeyError, ValueError) as exc:
            log.error("Autoryzacja nie powiodła się: %s", exc)
            return 1
        return 0
    try:
        now = datetime.now()
        rep = build_report(fetch_tasks(), now.date(), now)
    except (AuthError, OSError, KeyError, ValueError) as exc:
        # Brak sieci / wygasły token / zły JSON — krótki komunikat; widget pokaże
        # wtedy ostatnie zapamiętane dane (a przy AuthError — co zrobić).
        log.error("Nie udało się pobrać zadań: %s", exc)
        if a.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(rep, ensure_ascii=False) if a.json else _text(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
