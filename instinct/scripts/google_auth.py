"""Connecte votre compte Google (Gmail + Agenda) et affiche le jeton à mettre dans GOOGLE_REFRESH_TOKEN.

À lancer UNE fois, sur votre ordinateur (un navigateur s'ouvre) :

    export GOOGLE_CLIENT_ID=...       # identifiants OAuth « Application de bureau » (Google Cloud Console)
    export GOOGLE_CLIENT_SECRET=...
    python scripts/google_auth.py

Le jeton affiché donne accès à votre boîte mail et à votre agenda : gardez-le secret,
ne le collez jamais dans une conversation, et stockez-le uniquement dans les variables
d'environnement de la passerelle.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from gateway.google_tools import SCOPES  # noqa: E402


def main() -> None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Définissez GOOGLE_CLIENT_ID et GOOGLE_CLIENT_SECRET (voir README, étape Google).")
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=SCOPES,
    )
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        raise SystemExit("Google n'a pas renvoyé de jeton de rafraîchissement. Révoquez l'accès sur myaccount.google.com puis relancez.")
    print("\nAjoutez cette ligne aux variables d'environnement de la passerelle (et nulle part ailleurs) :\n")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
