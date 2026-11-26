"""Crée ou met à jour l'agent chez Anthropic depuis votre ordinateur.

Facultatif : la passerelle le fait toute seule à chaque démarrage (AUTO_PROVISION=1).

    python scripts/provision.py --dry-run   # affiche ce qui serait fait
    python scripts/provision.py             # applique

Variables lues : ANTHROPIC_API_KEY, GITHUB_REPO_URL, GITHUB_TOKEN, GITHUB_BRANCH,
DEPLOYMENT_BUDGET_CENTS, STATE_PATH (state.json par défaut), et pour brancher Telegram :
TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, PUBLIC_BASE_URL.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gateway.config import STATE_FILE, load_settings  # noqa: E402
from gateway.provisioning import load_state, plan, sync  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="n'appelle pas l'API, affiche seulement le plan")
    parser.add_argument("--skip-deployments", action="store_true", help="ne touche pas aux tâches planifiées")
    args = parser.parse_args()
    state_path = Path(os.environ.get("STATE_PATH") or STATE_FILE)

    if args.dry_run:
        print("Plan :")
        for line in plan(load_state(state_path)):
            print("  " + line)
        return

    import anthropic

    state = sync(
        anthropic.Anthropic(),
        state_path,
        repo_url=os.environ.get("GITHUB_REPO_URL", ""),
        repo_token=os.environ.get("GITHUB_TOKEN", ""),
        branch=os.environ.get("GITHUB_BRANCH", "main"),
        deployment_budget_cents=int(os.environ.get("DEPLOYMENT_BUDGET_CENTS", "200") or 0),
        skip_deployments=args.skip_deployments,
    )

    settings = load_settings()
    if settings.telegram_enabled and settings.public_base_url:
        from gateway.channels import Telegram

        result = Telegram(settings).set_webhook(f"{settings.public_base_url}/telegram/webhook")
        print(f"Webhook Telegram : {'OK' if result.get('ok') else result}")

    print("\nIdentifiants (aussi dans", state_path, ") :")
    for key in ("agent_id", "environment_id", "memory_store_id"):
        print(f"  {key.upper()}={state[key]}")


if __name__ == "__main__":
    main()
