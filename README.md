# calendar-stickies

Karteczki na pulpit macOS ([Übersicht](https://tracesof.net/uebersicht/)):

- **Spotkania dziś/jutro** — lista; zakończone przygaszone, trwające ▶ pogrubione
- **Spotkania na tydzień** — poziomo, dzień obok dnia (7 kolumn, weekend lekko wyróżniony)
- **Zadania Google** — Google Tasks: zaległe / dziś / jutro / później / bez terminu

Wspólne dla wszystkich: przeciąganie myszą, ⟳ odśwież, ▾ zwiń, ✕ pinezka 📌,
wysokość zmieniasz chwytając dolną krawędź (dwuklik = auto), szerokość — prawą krawędź (treść się nie skaluje, tylko chowa; dwuklik = domyślna), 🎨 paleta 36 kolorów
(wybór zapamiętany per karteczka), a **bez sieci / przy błędzie** pokazują ostatnie
pobrane dane z dopiskiem 📴. Kropka przy spotkaniu ma kolor kalendarza.

## Kalendarz

Spotkania czytane są bezpośrednio z bazy kalendarza macOS przez **EventKit**
(`pyobjc-framework-EventKit`) — widać wszystko, co jest w aplikacji Kalendarz
(iCloud, Google, Exchange…), łącznie z wydarzeniami cyklicznymi i wielodniowymi.

```sh
git clone https://github.com/mpasternak/calendar-stickies.git
cd calendar-stickies
./install.sh                          # zakłada .venv, wgrywa karteczki
.venv/bin/python cal_events.py        # test w terminalu
.venv/bin/python cal_events.py --calendars   # nazwy kalendarzy
```

Potem ⌘R w Übersicht. Przy pierwszym odświeżeniu macOS zapyta, czy Übersicht może
korzystać z Kalendarzy — zgódź się (albo: Ustawienia systemowe → Prywatność i ochrona
→ Kalendarze → Übersicht).

Wykluczone kalendarze (święta, urodziny…): `~/.config/calendar-stickies/config.json`,
wzór w `config.example.json`. Kolor startowy: `THEME=zielony ./install.sh`.

## Google Tasks

Google nie udostępnia zadań przez CalDAV, więc nie ma ich ani w Przypomnieniach, ani
w EventKit — karteczka czyta je z **Google Tasks API** (tylko odczyt). Jednorazowo:

1. [Google Cloud Console](https://console.cloud.google.com/) → nowy projekt.
2. *APIs & Services → Library* → włącz **Google Tasks API**.
3. *OAuth consent screen* → typ **External**, dodaj swój adres jako użytkownika
   testowego, a potem **Publish app** (w trybie „Testing" Google unieważnia token
   po 7 dniach). Weryfikacja nie jest potrzebna do własnego użytku — przy logowaniu
   kliknij „Zaawansowane → przejdź do aplikacji".
4. *Credentials → Create credentials → OAuth client ID* → **Desktop app** → pobierz
   JSON i zapisz jako `~/.config/calendar-stickies/google-client.json`.
5. `.venv/bin/python gtasks.py auth` — otworzy przeglądarkę; token trafi do
   `~/.config/calendar-stickies/google-token.json` (uprawnienia 600).
6. `./install.sh` — teraz zainstaluje też karteczkę „Zadania Google".

## Testy

```sh
pip install pytest ruff
pytest -q && ruff check . && ruff format --check .
```

Logika (podział na dni, wydarzenia wielodniowe/nocne, grupowanie zadań) jest
testowana bez EventKit i bez sieci.

## Licencja

MIT
