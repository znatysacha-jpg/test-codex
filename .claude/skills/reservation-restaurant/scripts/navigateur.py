#!/usr/bin/env python3
"""Navigateur pilotable étape par étape (Chromium via Playwright), pour l'agent personnel.

Un petit serveur local garde le navigateur ouvert entre deux commandes :

    python navigateur.py demarrer                 # installe si besoin et lance le navigateur
    python navigateur.py aller https://...        # ouvre une page
    python navigateur.py voir                     # texte de la page + éléments numérotés [12] bouton « Réserver »
    python navigateur.py cliquer 12               # clique sur l'élément 12
    python navigateur.py remplir 7 "Dupont"       # écrit dans un champ
    python navigateur.py choisir 9 "4 personnes"  # choisit dans une liste déroulante
    python navigateur.py touche Enter
    python navigateur.py capture                  # capture d'écran -> /tmp/navigateur/capture.png (à lire avec l'outil read)
    python navigateur.py arreter

Les numéros changent après chaque action : relancez « voir » avant de cliquer.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("NAVIGATEUR_PORT", "8765"))
WORKDIR = "/tmp/navigateur"
MAX_TEXT = 6000

COLLECT_JS = r"""
(prefix) => {
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=link], [role=option], [role=tab], [role=checkbox], [role=radio], [onclick], [tabindex]:not([tabindex="-1"])';
  const out = [];
  let n = 0;
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none') continue;
    const id = prefix + (n++);
    el.setAttribute('data-ia', id);
    let label = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('name') || '').trim().replace(/\s+/g, ' ');
    const tag = el.tagName.toLowerCase();
    let kind = tag === 'a' ? 'lien' : tag === 'select' ? 'liste' : (tag === 'input' || tag === 'textarea') ? ('champ ' + (el.type || 'texte')) : 'bouton';
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') kind += ' (désactivé)';
    if (tag === 'select') label = (el.getAttribute('aria-label') || el.getAttribute('name') || el.id || '') + ' : ' + Array.from(el.options).slice(0, 15).map(o => o.text.trim()).join(' | ');
    out.push({id, kind, label: label.slice(0, 120)});
  }
  return out;
}
"""


# ---------------------------------------------------------------------------- serveur
def serve() -> None:
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        executable_path=os.environ.get("NAVIGATEUR_CHROMIUM") or None,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        locale="fr-FR",
        timezone_id="Europe/Paris",
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    )
    page = context.new_page()
    state = {"page": page}

    def frames():
        return [f for f in state["page"].frames if not f.is_detached()]

    def locate(eid: str):
        for f in frames():
            loc = f.locator(f'[data-ia="{eid}"]')
            if loc.count():
                return loc.first
        raise RuntimeError(f"élément {eid} introuvable : relancez « voir »")

    def act(cmd: str, args: list[str]) -> dict:
        p = state["page"]
        if cmd == "aller":
            p.goto(args[0], wait_until="domcontentloaded", timeout=45000)
            p.wait_for_timeout(1500)
            return {"url": p.url, "titre": p.title()}
        if cmd == "voir":
            elements = []
            for i, f in enumerate(frames()):
                try:
                    elements += f.evaluate(COLLECT_JS, f"{i}-")
                except Exception:
                    continue
            text = p.inner_text("body")[:MAX_TEXT] if p.query_selector("body") else ""
            return {"url": p.url, "titre": p.title(), "texte": text, "elements": elements}
        if cmd == "cliquer":
            locate(args[0]).click(timeout=15000)
            p.wait_for_timeout(1500)
            if len(p.context.pages) > 1 and p.context.pages[-1] is not p:
                state["page"] = p.context.pages[-1]  # un nouvel onglet s'est ouvert
            return {"ok": True, "url": state["page"].url}
        if cmd == "remplir":
            loc = locate(args[0])
            loc.fill(args[1], timeout=15000)
            return {"ok": True}
        if cmd == "choisir":
            locate(args[0]).select_option(label=args[1], timeout=15000)
            p.wait_for_timeout(800)
            return {"ok": True}
        if cmd == "touche":
            p.keyboard.press(args[0])
            p.wait_for_timeout(1000)
            return {"ok": True}
        if cmd == "defiler":
            p.mouse.wheel(0, 800)
            p.wait_for_timeout(600)
            return {"ok": True}
        if cmd == "capture":
            path = os.path.join(WORKDIR, "capture.png")
            p.screenshot(path=path, full_page=False)
            return {"fichier": path}
        if cmd == "attendre":
            p.wait_for_timeout(int(float(args[0] if args else 2) * 1000))
            return {"ok": True}
        raise RuntimeError(f"commande inconnue : {cmd}")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
            if body.get("cmd") == "arreter":
                self._reply({"ok": True})
                browser.close()
                pw.stop()
                os._exit(0)
            try:
                result = act(body.get("cmd", ""), body.get("args", []))
            except Exception as e:
                result = {"erreur": f"{type(e).__name__} : {e}"}
            self._reply(result)

        def _reply(self, data: dict) -> None:
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a):
            pass

    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


# ---------------------------------------------------------------------------- client
def call(cmd: str, args: list[str]) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}",
        data=json.dumps({"cmd": cmd, "args": args}).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def running() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}", timeout=2)
    except Exception as e:  # le serveur ne répond qu'en POST : une erreur HTTP prouve qu'il tourne
        return "HTTP Error" in str(e)
    return True


def install() -> None:
    if os.environ.get("NAVIGATEUR_SANS_INSTALL"):
        return
    import importlib.util

    if importlib.util.find_spec("playwright") is None:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "playwright"], check=True)
    if subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"]).returncode != 0:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def start() -> None:
    os.makedirs(WORKDIR, exist_ok=True)
    if running():
        print(json.dumps({"ok": True, "deja_lance": True}))
        return
    install()
    log = open(os.path.join(WORKDIR, "serveur.log"), "a")
    subprocess.Popen([sys.executable, __file__, "_serveur"], stdout=log, stderr=log, start_new_session=True)
    for _ in range(60):
        time.sleep(1)
        if running():
            print(json.dumps({"ok": True}))
            return
    print(json.dumps({"erreur": "le navigateur n'a pas démarré, voir /tmp/navigateur/serveur.log"}))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "_serveur":
        serve()
    elif cmd == "demarrer":
        start()
    else:
        if not running():
            start()
        result = call(cmd, args)
        if cmd == "voir" and "elements" in result:
            print(f"{result['titre']} — {result['url']}\n")
            print(result["texte"])
            print("\nÉléments :")
            for e in result["elements"]:
                print(f"[{e['id']}] {e['kind']} « {e['label']} »")
        else:
            print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
