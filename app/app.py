"""Uptime Platform v2: sprawdza dostępność stron i zapisuje wyniki w PostgreSQL."""

import html
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from flask import Flask, jsonify
from psycopg.rows import dict_row

# --- Config ---
SITES = [
    "https://www.google.com",
    "https://github.com",
    "https://www.wikipedia.org",
    "https://nie-istnieje-taka-strona-12345.pl",
]
INTERVAL = 60   # co ile sekund sprawdzać
TIMEOUT = 10    # ile sekund czekać na odpowiedź strony

# Dane logowania do bazy (PGHOST, PGUSER, PGPASSWORD...) biblioteka psycopg
# czyta sama ze zmiennych środowiskowych, które ustawia systemd (/etc/uptime/uptime.env).

# --- Baza danych ---
SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id          BIGSERIAL   PRIMARY KEY,
    url         TEXT        NOT NULL,
    checked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_code INTEGER,
    up          BOOLEAN     NOT NULL,
    response_ms INTEGER
);
CREATE INDEX IF NOT EXISTS checks_url_time ON checks (url, checked_at DESC);
"""

# Ostatni wynik każdej strony + procent dostępności z ostatnich 24 godzin.
SUMMARY_SQL = """
SELECT l.url, l.up, l.status_code, l.response_ms,
       to_char(l.checked_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') AS checked,
       s.uptime_24h, s.checks_24h
FROM (
    SELECT DISTINCT ON (url) url, up, status_code, response_ms, checked_at
    FROM checks
    WHERE url = ANY(%(sites)s)
    ORDER BY url, checked_at DESC
) AS l
JOIN (
    SELECT url,
           round(100.0 * avg(up::int), 2) AS uptime_24h,
           count(*) AS checks_24h
    FROM checks
    WHERE checked_at > now() - interval '24 hours'
    GROUP BY url
) AS s USING (url)
ORDER BY l.url;
"""

app = Flask(__name__)


def db():
    """Nowe połączenie z bazą; wyniki zapytań jako słowniki."""
    return psycopg.connect(connect_timeout=5, row_factory=dict_row)


def check(url):
    """Wysyła zapytanie do strony i zwraca wynik sprawdzenia."""
    start = time.monotonic()
    try:
        req = Request(url, headers={"User-Agent": "uptime-platform/0.2"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.status
    except HTTPError as e:      # errory np. 404, 405, 500
        code = e.code
    except (URLError, OSError):  # brak odpowiedzi: zła domena, timeout, brak sieci
        code = None
    ms = round((time.monotonic() - start) * 1000)
    return {
        "url": url,
        "status_code": code,
        "up": code is not None and code < 400,
        "response_ms": ms if code is not None else None,
    }


def save(result):
    """Zapisuje jedno sprawdzenie w tabeli checks."""
    with db() as conn:  # wyjście z bloku zatwierdza transakcję (commit)
        conn.execute(
            "INSERT INTO checks (url, status_code, up, response_ms) "
            "VALUES (%(url)s, %(status_code)s, %(up)s, %(response_ms)s)",
            result,
        )


def checker_loop():
    """Działa w tle: tworzy tabelę (raz), potem co INTERVAL sekund sprawdza strony."""
    schema_ready = False
    while True:
        try:
            if not schema_ready:
                with db() as conn:
                    conn.execute(SCHEMA)
                schema_ready = True
            for url in SITES:
                save(check(url))
        except psycopg.Error as e:
            # baza niedostępna: zapisz błąd w logu i spróbuj w następnym cyklu
            print(f"Błąd bazy danych: {e}", flush=True)
        time.sleep(INTERVAL)


threading.Thread(target=checker_loop, daemon=True).start()


def summary():
    """Ostatnie wyniki i dostępność 24 h prosto z bazy."""
    with db() as conn:
        return conn.execute(SUMMARY_SQL, {"sites": SITES}).fetchall()


@app.route("/")
def index():
    """Strona główna: tabela ze stanem stron i dostępnością z 24 godzin."""
    try:
        rows = summary()
    except psycopg.Error:
        return "<h1>Uptime Platform</h1><p>Brak połączenia z bazą danych.</p>", 503
    lines = []
    for r in rows:
        state = "działa" if r["up"] else "nie działa"
        color = "#1a7f37" if r["up"] else "#cf222e"
        code = r["status_code"] if r["status_code"] is not None else "brak odpowiedzi"
        ms = f'{r["response_ms"]} ms' if r["response_ms"] is not None else "-"
        lines.append(
            f'<tr><td>{html.escape(r["url"])}</td>'
            f'<td style="color:{color};font-weight:600">{state}</td>'
            f"<td>{code}</td><td>{ms}</td>"
            f'<td>{r["uptime_24h"]}%</td><td>{r["checks_24h"]}</td>'
            f'<td>{r["checked"]} UTC</td></tr>'
        )
    body = "".join(lines) or '<tr><td colspan="7">Pierwsze sprawdzenie w toku, odśwież za chwilę.</td></tr>'
    return f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8"><title>Uptime Platform</title>
<meta http-equiv="refresh" content="30">
<style>
 body {{ font-family: system-ui, sans-serif; margin: 40px; color: #1f2328; }}
 table {{ border-collapse: collapse; }}
 th, td {{ border-bottom: 1px solid #d0d7de; padding: 8px 16px; text-align: left; }}
 th {{ background: #f6f8fa; }}
</style></head><body>
<h1>Uptime Platform</h1>
<p>Sprawdzanie co {INTERVAL} s, wyniki zapisywane w PostgreSQL. Strona odświeża się sama co 30 s.</p>
<table><tr><th>Strona</th><th>Stan</th><th>Kod</th><th>Czas odpowiedzi</th>
<th>Dostępność 24 h</th><th>Sprawdzeń 24 h</th><th>Ostatnie sprawdzenie</th></tr>
{body}</table></body></html>"""


@app.route("/api/status")
def api_status():
    """Te same dane w formacie JSON, dla innych programów."""
    try:
        rows = summary()
    except psycopg.Error:
        return jsonify({"error": "database unavailable"}), 503
    for r in rows:
        r["uptime_24h"] = float(r["uptime_24h"])
    return jsonify(rows)


@app.route("/health")
def health():
    """Aplikacja żyje i ma połączenie z bazą."""
    try:
        with db() as conn:
            conn.execute("SELECT 1")
        return "ok\n"
    except psycopg.Error:
        return "database unavailable\n", 503