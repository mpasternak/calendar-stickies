// AUTO-GENEROWANE przez install.sh z sticky.jsx — edytuj szablon, nie ten plik.
// Karteczka: __TITLE__
// Układ: __LAYOUT__ ("list" = dni pod sobą, "columns" = dni obok siebie).
//
// Skrypt zwraca JSON: { summary, generated_at, sections: [{ title, weekend?,
//   items: [{ time, end, title, sub?, color?, tip?, url?, dim?, now? }] }] }  albo  { error }.

import { run } from "uebersicht";

export const refreshFrequency = __REFRESH__;

export const command = `cd "__PROJECT_DIR__" && "__PYTHON__" __SCRIPT__ --json`;

export const className = `top: 0; left: 0;`;

const POS_KEY = "calpos-__SLUG__";
const UI_KEY = "calui-__SLUG__";
const LAST_KEY = "callast-__SLUG__"; // ostatnie udane dane — pokazywane, gdy skrypt zawiedzie (np. brak sieci)
const DEFAULT_POS = { x: __LEFT__, y: __TOP__ };
const LAYOUT = "__LAYOUT__";
const MIN_BODY = 48;
const DEFAULT_WIDTH = __WIDTH__;  // szerokość startowa; prawą krawędzią można ją zmienić
const MIN_WIDTH = 220;

// --- trwały stan UI (localStorage) -----------------------------------------
function loadUI() {
  try { return JSON.parse(localStorage.getItem(UI_KEY)) || {}; }
  catch (e) { return {}; } // brak/zepsuty wpis — startujemy z domyślnych
}
function saveUI(patch) {
  const next = { ...loadUI(), ...patch };
  try { localStorage.setItem(UI_KEY, JSON.stringify(next)); }
  catch (e) { /* tryb prywatny / brak miejsca — stan zostaje tylko w pamięci */ }
}

// --- ostatnie udane dane (fallback offline) ---------------------------------
function parseData(output) {
  try { const d = JSON.parse(output); return d && !d.error && d.sections ? d : null; }
  catch (e) { return null; } // nie-JSON (np. traceback) = brak świeżych danych
}
function loadLast() {
  try { return JSON.parse(localStorage.getItem(LAST_KEY)); }
  catch (e) { return null; } // brak/zepsuty wpis — po prostu nie mamy kopii
}
function saveLast(d) {
  try { localStorage.setItem(LAST_KEY, JSON.stringify(d)); }
  catch (e) { /* brak miejsca — kopia zostaje tylko w pamięci (state.last) */ }
}
// Wynik komendy: udane dane zapamiętujemy, przy błędzie zostaje poprzednia kopia.
function withResult(prev, output, error) {
  const d = error ? null : parseData(output);
  if (d) saveLast(d);
  return { ...prev, busy: false, output, error, last: d || prev.last };
}

// --- motywy kolorystyczne (🎨 w nagłówku otwiera paletę 6×6; wybór zapamiętany)
// Rząd 1: odcienie neutralne; dalej kolumna = barwa, rząd = ton (głęboki → pastelowy).
const NEUTRALS = [
  ["czarny", "rgba(0,0,0,0.88)", "#f0f0f0"],
  ["grafit", "rgba(28,28,30,0.84)", "#ececec"],
  ["łupek", "rgba(58,64,74,0.88)", "#eef1f5"],
  ["stal", "rgba(120,126,136,0.90)", "#ffffff"],
  ["perła", "rgba(222,224,228,0.94)", "#1d1d1f"],
  ["biały", "rgba(250,250,252,0.94)", "#1d1d1f"],
];
const HUES = [
  ["czerwony", 355], ["pomarańczowy", 26], ["żółty", 50], ["zielony", 145], ["niebieski", 215], ["fioletowy", 275],
];
// [nazwa tonu, nasycenie %, jasność %, krycie, kolor tekstu]
const TONES = [
  ["głęboki", 45, 14, 0.9, "#f4f4f4"],
  ["ciemny", 40, 24, 0.9, "#f4f4f4"],
  ["średni", 42, 38, 0.92, "#ffffff"],
  ["jasny", 60, 76, 0.95, "#1d1d1f"],
  ["pastelowy", 70, 90, 0.95, "#1d1d1f"],
];
const THEMES = {};
NEUTRALS.forEach(([name, bg, fg]) => { THEMES[name] = { bg, fg }; });
TONES.forEach(([tone, s, l, a, fg]) => HUES.forEach(([hue, h]) => {
  THEMES[`${hue} ${tone}`] = { bg: `hsla(${h}, ${s}%, ${l}%, ${a})`, fg };
}));
const THEME_NAMES = Object.keys(THEMES); // kolejność = rzędy palety 6×6
// Nazwy z poprzedniej, mniejszej palety → najbliższy odpowiednik.
const THEME_ALIASES = {
  ciemny: "grafit", granat: "niebieski głęboki", niebieski: "niebieski ciemny", morski: "zielony głęboki",
  zielony: "zielony ciemny", oliwka: "żółty głęboki", "brąz": "pomarańczowy głęboki", bordo: "czerwony głęboki",
  "śliwka": "fioletowy głęboki", fiolet: "fioletowy ciemny", karteczka: "żółty pastelowy",
  "mięta": "zielony pastelowy", "błękit": "niebieski pastelowy", "róż": "czerwony pastelowy", jasny: "biały",
};
const DEFAULT_THEME = "__THEME__";
const resolveTheme = (name) => (THEMES[name] ? name : THEME_ALIASES[name]);
const themeOf = (name) => THEMES[resolveTheme(name)] || THEMES[resolveTheme(DEFAULT_THEME)] || THEMES.grafit;
// Linie/tła pomocnicze liczone z koloru tekstu — pasują do każdego motywu.
const mix = (pct) => `color-mix(in srgb, currentColor ${pct}%, transparent)`;

// Paleta 6×6 pod przyciskiem 🎨 (pozycja względem korzenia karteczki).
const pickerBox = {
  position: "absolute", top: 30, right: 10, zIndex: 10, padding: 6, borderRadius: 8,
  display: "grid", gridTemplateColumns: "repeat(6, 18px)", gap: 4,
  boxShadow: "0 6px 18px rgba(0,0,0,0.45)", border: "1px solid " + mix(20), cursor: "default",
};
function themePicker(current, onPick) {
  const cur = resolveTheme(current);
  return (
    <div style={{ ...pickerBox, background: themeOf(current).bg }} data-nodrag="1">
      {THEME_NAMES.map((name) => (
        <span key={name} title={name} data-nodrag="1" onClick={() => onPick(name)}
              style={{ width: 18, height: 18, borderRadius: 4, cursor: "pointer", background: THEMES[name].bg,
                       boxShadow: name === cur ? "0 0 0 2px " + THEMES[name].fg + ", 0 0 0 3px rgba(0,0,0,0.5)"
                                              : "inset 0 0 0 1px rgba(127,127,127,0.5)" }} />
      ))}
    </div>
  );
}

// --- stan widgetu -----------------------------------------------------------
const _ui = loadUI();
export const initialState = {
  output: "",
  error: null,
  busy: false,
  last: loadLast(),
  collapsed: !!_ui.collapsed,
  hidden: !!_ui.hidden,
  height: typeof _ui.height === "number" ? _ui.height : null,
  width: typeof _ui.width === "number" ? _ui.width : null,
  theme: resolveTheme(_ui.theme) || DEFAULT_THEME,
};

export const updateState = (event, prev) => {
  switch (event.type) {
    case "CAL/SET":       return { ...prev, ...event.patch };
    case "CAL/BUSY":      return { ...prev, busy: true };
    case "CAL/REFRESHED": return withResult(prev, event.output, null);
    case "CAL/ERROR":     return withResult(prev, "", event.error);
    default:
      if ("output" in event || "error" in event) {
        return withResult(prev, event.output, event.error);
      }
      return prev;
  }
};

// --- akcje ------------------------------------------------------------------
function setUI(dispatch, patch) {
  saveUI(patch);
  dispatch({ type: "CAL/SET", patch });
}
function refreshNow(dispatch) {
  dispatch({ type: "CAL/BUSY" });
  run(command)
    .then((output) => dispatch({ type: "CAL/REFRESHED", output }))
    .catch((err) => dispatch({ type: "CAL/ERROR", error: String(err) }));
}

// --- wyciąganie na wierzch: wciśnięta karteczka idzie nad pozostałe -------
// Wszystkie widgety Übersicht leżą na jednej stronie i dzielą localStorage, więc
// wspólny licznik "sticky-z-top" daje każdej wciśniętej karteczce najwyższy
// z-index. Własny zapisujemy pod Z_KEY — kolejność przeżywa odświeżenie.
const Z_KEY = POS_KEY + ":z";
function initRaise(el) {
  let z = 0;
  try { z = parseInt(localStorage.getItem(Z_KEY), 10) || 0; }
  catch (e) { z = 0; } // brak localStorage — kolejność tylko do odświeżenia
  if (z) el.style.zIndex = String(z);
  el.addEventListener("mousedown", () => {
    let top = 0;
    try { top = parseInt(localStorage.getItem("sticky-z-top"), 10) || 0; }
    catch (e) { top = 0; } // jw. — liczymy od zera
    if (top && String(top) === el.style.zIndex) return; // już jest na wierzchu
    el.style.zIndex = String(top + 1);
    try {
      localStorage.setItem("sticky-z-top", String(top + 1));
      localStorage.setItem(Z_KEY, String(top + 1));
    } catch (e) { /* brak miejsca — kolejność zostaje tylko do odświeżenia */ }
  }, true); // capture: działa też przy kliknięciu w przycisk / link
}

// --- przeciąganie pozycji (+ „tapnięcie" przywraca pinezkę) ----------------
function initDrag(el, onTap) {
  if (!el) return;
  if (onTap !== undefined) el.__calTap = onTap;
  if (el.__calInit) return;
  el.__calInit = true;
  initRaise(el);
  let pos;
  try { pos = JSON.parse(localStorage.getItem(POS_KEY)); } catch (e) { pos = null; }
  if (!pos) pos = { ...DEFAULT_POS };
  const apply = () => { el.style.left = pos.x + "px"; el.style.top = pos.y + "px"; };
  apply();
  let drag = false, sx = 0, sy = 0, ox = 0, oy = 0;
  el.addEventListener("mousedown", (e) => {
    if (e.target.closest("a")) return;
    if (e.target.closest("[data-nodrag]")) return;
    drag = true; el.__calMoved = false;
    sx = e.clientX; sy = e.clientY; ox = pos.x; oy = pos.y;
    el.style.cursor = "grabbing";
    e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!drag) return;
    pos.x = ox + (e.clientX - sx);
    pos.y = oy + (e.clientY - sy);
    if (Math.abs(e.clientX - sx) + Math.abs(e.clientY - sy) > 4) el.__calMoved = true;
    apply();
  });
  window.addEventListener("mouseup", () => {
    if (!drag) return;
    drag = false;
    el.style.cursor = "grab";
    localStorage.setItem(POS_KEY, JSON.stringify(pos));
    if (!el.__calMoved && el.__calTap) el.__calTap();
  });
}

// --- zmiana wysokości listy od dołu ----------------------------------------
let bodyEl = null;
const bodyRef = (el) => { if (el) bodyEl = el; };
function startResize(e, dispatch) {
  e.preventDefault();
  const root = e.currentTarget ? e.currentTarget.parentElement : null;
  const lockTop = root ? root.style.top : "";
  const lockLeft = root ? root.style.left : "";
  const pin = () => {
    if (!root) return;
    if (lockTop) root.style.top = lockTop;
    if (lockLeft) root.style.left = lockLeft;
  };
  const startY = e.clientY;
  const startH = bodyEl ? bodyEl.offsetHeight : 0;
  let lastH = startH, moved = false;
  if (bodyEl) bodyEl.style.overflowY = "auto";
  const move = (ev) => {
    moved = true;
    lastH = Math.max(MIN_BODY, startH + (ev.clientY - startY));
    if (bodyEl) bodyEl.style.maxHeight = lastH + "px";
    pin();
  };
  const up = () => {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    pin();
    if (moved) setUI(dispatch, { height: lastH });
  };
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
}

// --- zmiana szerokości od prawej krawędzi ----------------------------------
function startWidthResize(e, dispatch) {
  e.preventDefault();
  // Jak przy wysokości: lewy-górny róg ZABLOKOWANY, rośnie tylko prawa krawędź.
  const root = e.currentTarget ? e.currentTarget.parentElement : null;
  if (!root) return;
  const lockTop = root.style.top, lockLeft = root.style.left;
  const startX = e.clientX;
  const startW = parseFloat(getComputedStyle(root).width) || DEFAULT_WIDTH;
  let lastW = startW, moved = false;
  const move = (ev) => {
    moved = true;
    lastW = Math.max(MIN_WIDTH, Math.round(startW + (ev.clientX - startX)));
    root.style.width = lastW + "px";
    root.style.top = lockTop;
    root.style.left = lockLeft;
  };
  const up = () => {
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", up);
    if (moved) setUI(dispatch, { width: lastW }); // czysty klik nie zmienia rozmiaru
  };
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", up);
}

// --- style ------------------------------------------------------------------
const rootStyle = {
  position: "fixed", width: DEFAULT_WIDTH + "px", pointerEvents: "auto", cursor: "grab",
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  border: "1px solid " + mix(12), borderRadius: "10px",
  boxShadow: "0 8px 24px rgba(0,0,0,0.35)", padding: "12px 14px",
  fontSize: "12px", lineHeight: 1.45,
};
const pinStyle = {
  position: "fixed", pointerEvents: "auto", cursor: "grab",
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  border: "1px solid " + mix(12), borderRadius: "8px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.28)", padding: "5px 10px",
  fontSize: "12px", fontWeight: 700, whiteSpace: "nowrap", userSelect: "none",
};
const hdr = { borderLeft: "4px solid __ACCENT__", paddingLeft: 8, marginBottom: 8 };
const hdrRow = { display: "flex", alignItems: "center", gap: 8 };
const title = {
  fontWeight: 700, fontSize: 14, letterSpacing: 0.3,
  flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
};
const sub = { fontSize: 11, opacity: 0.7 };
const ctlWrap = { display: "flex", alignItems: "center", gap: 9, flex: "0 0 auto" };
const ctl = { cursor: "pointer", opacity: 0.6, fontSize: 16, lineHeight: 1, userSelect: "none" };
const row = {
  display: "block", textDecoration: "none", color: "inherit",
  padding: "2px 0", borderTop: "1px solid " + mix(8),
};
const line = { display: "flex", gap: 6, whiteSpace: "nowrap" };
const nameC = { flex: 1, overflow: "hidden", textOverflow: "ellipsis" };
const num = { fontVariantNumeric: "tabular-nums", opacity: 0.6 };
const prob = { fontSize: 11, opacity: 0.75, paddingLeft: 20, whiteSpace: "nowrap",
               overflow: "hidden", textOverflow: "ellipsis" };
// Uchwyt zmiany wysokości: niewidoczny pas przy dolnej krawędzi (wchodzi w dolny
// padding karteczki); widać go tylko po najechaniu, kursor ↕ podpowiada chwyt.
const handle = { height: 8, margin: "2px 0 -10px", borderRadius: 4, cursor: "ns-resize", background: "transparent" };
const HANDLE_HOVER = mix(10);
// Uchwyt szerokości: niewidoczny pas wzdłuż prawej krawędzi, kursor ↔.
const sideHandle = { position: "absolute", top: 10, bottom: 10, right: -4, width: 8, borderRadius: 4,
                     cursor: "ew-resize", background: "transparent" };

const secHdr = { fontSize: 10, fontWeight: 700, opacity: 0.55, letterSpacing: 0.4, margin: "8px 0 1px" };
const col = { flex: "1 1 0", minWidth: 0, padding: "0 6px", borderLeft: "1px solid " + mix(8) };
const colHdr = { fontSize: 11, fontWeight: 700, opacity: 0.75, marginBottom: 3, whiteSpace: "nowrap" };
const dot = { width: 7, height: 7, borderRadius: 4, flex: "0 0 auto", marginTop: 5 };
const timeC = { ...num, flex: "0 0 auto", minWidth: 34 };
const empty = { fontSize: 11, opacity: 0.35 };

function itemRow(it, i, wrap) {
  const content = (
    <div style={{ ...line, alignItems: "flex-start", opacity: it.dim ? 0.4 : 1, fontWeight: it.now ? 700 : 400 }}>
      <span style={{ ...dot, background: it.color || mix(40) }} />
      {it.time ? <span style={timeC}>{it.time}</span> : null}
      <span style={wrap ? { ...nameC, whiteSpace: "normal", wordBreak: "break-word" } : nameC}>
        {it.now ? "▶ " : ""}{it.title}
      </span>
    </div>
  );
  return it.url
    ? <a style={row} href={it.url} title={it.tip || it.title} key={i}>{content}</a>
    : <div style={row} title={it.tip || it.title} key={i}>{content}</div>;
}

// Dni pod sobą (dziś/jutro, zadania) albo obok siebie (tydzień).
function renderSections(sections) {
  if (LAYOUT === "columns") {
    return (
      <div style={{ display: "flex", margin: "0 -6px" }}>
        {sections.map((s, i) => (
          <div style={{ ...col, borderLeft: i ? col.borderLeft : "none",
                        background: s.weekend ? mix(4) : "none" }} key={s.title}>
            <div style={colHdr}>{s.title}</div>
            {s.items.length ? s.items.map((it, j) => itemRow(it, j, true)) : <div style={empty}>—</div>}
          </div>
        ))}
      </div>
    );
  }
  return sections.map((s) => (
    <div key={s.title}>
      <div style={secHdr}>{s.title}</div>
      {s.items.length ? s.items.map((it, j) => itemRow(it, j, false)) : <div style={empty}>nic</div>}
    </div>
  ));
}

// --- render -----------------------------------------------------------------
export const render = (state, dispatch) => {
  const { output, error, busy, collapsed, hidden, height, width, last, theme, picker } = state;
  const T = themeOf(theme);
  const paint = { background: T.bg, color: T.fg };

  if (hidden) {
    return (
      <div style={{ ...pinStyle, ...paint }} ref={(el) => initDrag(el, () => setUI(dispatch, { hidden: false }))}>
        📌 __TITLE__
      </div>
    );
  }

  // Świeże dane, a gdy skrypt zawiódł — ostatnia zapamiętana kopia.
  const fresh = error ? null : parseData(output);
  let parseErr = null;
  if (!error && output && !fresh) {
    let j = null;
    try { j = JSON.parse(output); }
    catch (e) { j = null; } // skrypt wypisał nie-JSON (np. traceback) — pokażemy surowy tekst
    parseErr = j && j.error ? j.error : output.slice(0, 200);
  }
  // Z tracebacku/komunikatu zostaw ostatnią niepustą linię (sedno błędu).
  const errText = error ? String(error).trim().split("\n").filter(Boolean).pop() || "?" : parseErr;
  const d = fresh || last;
  const stale = !fresh && !!d && !!errText;

  const controls = (
    <span style={ctlWrap}>
      <span style={{ ...ctl, fontSize: 13 }} data-nodrag="1" title={`Kolor: ${theme}`}
            onClick={() => dispatch({ type: "CAL/SET", patch: { picker: !picker } })}>🎨</span>
      <span style={ctl} data-nodrag="1" title="Odśwież teraz"
            onClick={() => refreshNow(dispatch)}>{busy ? "⏳" : "⟳"}</span>
      <span style={ctl} data-nodrag="1" title={collapsed ? "Rozwiń" : "Zwiń"}
            onClick={() => setUI(dispatch, { collapsed: !collapsed })}>{collapsed ? "▸" : "▾"}</span>
      <span style={ctl} data-nodrag="1" title="Ukryj (zostanie pinezka)"
            onClick={() => setUI(dispatch, { hidden: true })}>✕</span>
    </span>
  );

  const summary = d
    ? <span>{stale ? "📴 " : ""}{d.summary}</span>
    : <span>{errText ? "⚠️ błąd" : "—"}</span>;

  if (collapsed) {
    return (
      <div style={{ ...rootStyle, ...paint, width: "auto", minWidth: 260, padding: "8px 14px" }} ref={(el) => initDrag(el, null)}>
        {picker && themePicker(theme, (name) => setUI(dispatch, { theme: name, picker: false }))}
        <div style={{ ...hdr, marginBottom: 0, ...hdrRow }}>
          <span style={title}>__TITLE__</span>
          <span style={{ ...sub, flex: "0 0 auto" }}>{summary}</span>
          {controls}
        </div>
      </div>
    );
  }

  return (
    <div style={{ ...rootStyle, ...paint, width: (width || DEFAULT_WIDTH) + "px" }} ref={(el) => initDrag(el, null)}>
        {picker && themePicker(theme, (name) => setUI(dispatch, { theme: name, picker: false }))}
      <div style={hdr}>
        <div style={hdrRow}>
          <div style={title}>__TITLE__</div>
          {controls}
        </div>
        <div style={sub}>{summary}</div>
      </div>

      <div ref={bodyRef}
           style={{ maxHeight: height ? height + "px" : "none",
                    overflowY: height ? "auto" : "visible", overflowX: "clip" }}>
        {stale && (
          <div style={{ ...sub, marginBottom: 4 }} title={String(error || parseErr)}>
            📴 nie udało się odświeżyć — dane z {d.generated_at ? d.generated_at.slice(0, 16).replace("T", " ") : "?"}
          </div>
        )}
        {!d && errText && <div style={sub} title={String(error || parseErr)}>⚠️ błąd: {errText}</div>}
        {!d && !errText && <div style={sub}>wczytuję…</div>}
        {/* Treść ma stałą szerokość (domyślną): zmiana szerokości karteczki tylko
            odsłania / chowa jej prawą część, zamiast ją skalować. */}
        {d && <div style={{ width: DEFAULT_WIDTH }}>{renderSections(d.sections)}</div>}
        {d && d.generated_at && (
          <div style={{ ...sub, marginTop: 8, textAlign: "right" }}>{d.generated_at.slice(11, 16)}</div>
        )}
      </div>

      <div style={handle} data-nodrag="1"
           onMouseEnter={(e) => { e.currentTarget.style.background = HANDLE_HOVER; }}
           onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
           title="Przeciągnij = zmień wysokość · dwuklik = auto"
           onMouseDown={(e) => startResize(e, dispatch)}
           onDoubleClick={() => {
             setUI(dispatch, { height: null });
             if (bodyEl) { bodyEl.style.maxHeight = "none"; bodyEl.style.overflowY = "visible"; }
           }} />

      <div style={sideHandle} data-nodrag="1"
           onMouseEnter={(e) => { e.currentTarget.style.background = HANDLE_HOVER; }}
           onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
           title="Przeciągnij = zmień szerokość · dwuklik = domyślna"
           onMouseDown={(e) => startWidthResize(e, dispatch)}
           onDoubleClick={(e) => {
             setUI(dispatch, { width: null });
             e.currentTarget.parentElement.style.width = DEFAULT_WIDTH + "px";
           }} />
    </div>
  );
};
