"""Uptime Platform v1: sprawdza dostępność stron i pokazuje wyniki."""

import html
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify

# --- Config ---
SITES = [
    "https://www.google.com",
    "https://github.com",
    "https://www.wikipedia.org",
    "https://nie-istnieje-taka-strona-12345.pl",
]
INTERVAL = 60
TIMEOUT = 10

app = Flask(__name__)
results = {}             # ostatni wynik dla każdej strony (na razie w pamięci)
lock = threading.Lock()  # chroni "results" przed jednoczesnym zapisem i odczytem


def check(url):
    """Wysyła zapytanie do strony i zwraca wynik sprawdzenia."""
    start = time.monotonic()
    try:
        req = Request(url, headers={"User-Agent": "uptime-platform/0.1"})
        with urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.status
    except HTTPError as e:      # errory 405, 500
        code = e.code
    except (URLError, OSError):  # brak odpowiedzi: zła domena, timeout, brak sieci
        code = None
    ms = round((time.monotonic() - start) * 1000)
    return {
        "url": url,
        "status": code,
        "up": code is not None and code < 400,
        "ms": ms if code is not None else None,
        "checked": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


def checker_loop():
    """Działa w tle: sprawdza wszystkie strony co INTERVAL sekund."""
    while True:
        for url in SITES:
            result = check(url)
            with lock:
                results[url] = result
        time.sleep(INTERVAL)


threading.Thread(target=checker_loop, daemon=True).start()


@app.route("/")
def index():
    """Strona główna: tabela ze stanem stron."""
    with lock:
        rows = list(results.values())
    lines = []
    for r in rows:
        state = "działa" if r["up"] else "nie działa"
        color = "#1a7f37" if r["up"] else "#cf222e"
        code = r["status"] if r["status"] is not None else "brak odpowiedzi"
        ms = f'{r["ms"]} ms' if r["ms"] is not None else "-"
        lines.append(
            f'<tr><td>{html.escape(r["url"])}</td>'
            f'<td style="color:{color};font-weight:600">{state}</td>'
            f"<td>{code}</td><td>{ms}</td><td>{r['checked']}</td></tr>"
        )
    body = "".join(lines) or '<tr><td colspan="5">Pierwsze sprawdzenie w toku, odśwież za chwilę.</td></tr>'
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
<p>Sprawdzanie co {INTERVAL} s. Strona odświeża się sama co 30 s.</p>
<table><tr><th>Strona</th><th>Stan</th><th>Kod</th><th>Czas odpowiedzi</th><th>Ostatnie sprawdzenie</th></tr>
{body}</table></body></html>"""


@app.route("/api/status")
def api_status():
    """Te same dane w formacie JSON, dla innych programów."""
    with lock:
        return jsonify(list(results.values()))


@app.route("/health")
def health():
    """Prosty test, czy aplikacja żyje."""
    return "ok"