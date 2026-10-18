#!/usr/bin/env bash
# Zakłada .venv (pyobjc-framework-EventKit), generuje karteczki z szablonu sticky.jsx
# i wgrywa je do Übersicht. Po zmianie szablonu: ./install.sh, potem ⌘R.
#
# Kolor startowy karteczek (potem zmieniasz 🎨 na karteczce):
#   grafit czarny granat niebieski morski zielony oliwka brąz bordo śliwka fiolet
#   karteczka mięta błękit róż jasny
#   THEME=zielony ./install.sh
#
# Karteczka Google Tasks instaluje się tylko, gdy jest już autoryzacja
# (python gtasks.py auth — patrz README).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/Library/Application Support/Übersicht/widgets"
THEME="${THEME:-granat}"

if [ ! -d "$DEST" ]; then
  echo "Nie znaleziono katalogu Übersicht: $DEST"
  exit 1
fi

# --- środowisko Pythona ---------------------------------------------------------
if [ ! -x "$SRC/.venv/bin/python" ]; then
  echo "Zakładam .venv…"
  if command -v uv >/dev/null; then
    uv venv -q "$SRC/.venv"
  else
    python3 -m venv "$SRC/.venv"
  fi
fi
PY="$SRC/.venv/bin/python"
if ! "$PY" -c "import EventKit" 2>/dev/null; then
  echo "Instaluję pyobjc-framework-EventKit…"
  if command -v uv >/dev/null; then
    uv pip install -q --python "$PY" pyobjc-framework-EventKit
  else
    "$PY" -m pip install -q pyobjc-framework-EventKit
  fi
fi

esc() { printf '%s' "$1" | sed -e 's/[&|\\]/\\&/g'; }

# widget SLUG TYTUŁ "SKRYPT ARGUMENTY" UKŁAD SZEROKOŚĆ ODŚWIEŻANIE_MS LEFT TOP AKCENT
widget() {
  sed -e "s|__PROJECT_DIR__|$(esc "$SRC")|g" -e "s|__PYTHON__|$(esc "$PY")|g" \
      -e "s|__SLUG__|$1|g" -e "s|__TITLE__|$(esc "$2")|g" -e "s|__SCRIPT__|$(esc "$3")|g" \
      -e "s|__LAYOUT__|$4|g" -e "s|__WIDTH__|$5|g" -e "s|__REFRESH__|$6|g" \
      -e "s|__LEFT__|$7|g" -e "s|__TOP__|$8|g" -e "s|__ACCENT__|$(esc "$9")|g" \
      -e "s|__THEME__|$(esc "$THEME")|g" \
      "$SRC/sticky.jsx" > "$DEST/calendar-$1.jsx"
  echo "  calendar-$1.jsx  ($2)"
}

echo "Instaluję karteczki do Übersicht:"
widget today "Spotkania dziś/jutro" "cal_events.py --days 2" list    340  300000 1600 40  "#4f9be0"
widget week  "Spotkania na tydzień" "cal_events.py --days 7" columns 1120 600000 1600 520 "#4f9be0"
if [ -f "${GTASKS_TOKEN:-$HOME/.config/calendar-stickies/google-token.json}" ]; then
  widget tasks "Zadania Google" "gtasks.py" list 340 600000 1960 40 "#e0a84f"
else
  echo "  (pomijam Zadania Google — najpierw: $PY gtasks.py auth)"
fi
echo "Gotowe. Odśwież Übersicht (⌘R). Przy pierwszym razie macOS zapyta o dostęp do Kalendarzy."
