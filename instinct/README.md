# Instinct perso

Votre agent personnel, sur le modèle d'Instinct. Vous lui parlez depuis une **app iPhone** (un artefact claude.ai), **Siri**, **Telegram** ou **WhatsApp**. Il travaille pour vous :

- **E-mails** : il lit, trie, résume, prépare des brouillons, envoie (après votre accord).
- **Agenda et contacts** : créneaux, rendez-vous (après votre accord), recherche de numéros.
- **Messages WhatsApp** : il rédige le message dans votre style, et l'app ouvre WhatsApp avec le texte prêt. Vous appuyez sur Envoyer.
- **Restaurants** : il **réserve pour de vrai** avec un navigateur, et vous demande « Je confirme ? » avant le clic final.
- **Hôtels, trains, avions, achats** : il cherche, compare et vous présente les meilleures options avec le lien de réservation. Vous payez.
- **Recherches web, prospection B2B (RGPD), projets, équipe** : avec les 148 skills du dépôt.
- **Proactif** : briefing du matin, relances de prospection et revue de la semaine, envoyés automatiquement.
- **Mémoire durable** : ce qu'il apprend sur vous, vos contacts, vos prospects et vos projets.

## Comment c'est construit

```
 iPhone : app artefact ─┐      Siri (Raccourci) ─┐     Telegram / WhatsApp ─┐
                        │ connecteur claude.ai    │ POST /siri              │ webhooks
                        ▼                         ▼                         ▼
              ┌─────────────────── passerelle (ce dossier, gateway/) ───────────────────┐
              │ historique · validations à boutons · Gmail/Agenda/Contacts (jetons ici) │
              └──────────────────────────────┬──────────────────────────────────────────┘
                                             │ API Claude Managed Agents
                                             ▼
              ┌──────────────── agent hébergé par Anthropic ────────────────────────────┐
              │ Claude Opus 5.5 · recherche web · navigateur · fichiers Excel/Word/PDF  │
              │ mémoire durable · 148 skills (dossier .claude/skills du dépôt)          │
              │ tâches planifiées : briefing 7h43, relances 16h17, revue vendredi 17h07 │
              └─────────────────────────────────────────────────────────────────────────┘
```

- `agents/instinct-perso/agent.md` : la personnalité, les règles et les outils de l'agent.
- `agents/instinct-perso/environment.yaml` : son conteneur et les sites qu'il peut joindre.
- `deployments/` : les tâches automatiques. `memory_seed/` : sa mémoire de départ.
- `gateway/` : la passerelle (FastAPI). `app/index.html` : l'app iPhone.
- `../.claude/skills/reservation-restaurant/` : le savoir-faire de réservation et son navigateur.

## Sécurité : ce que l'agent ne fait jamais seul

| Action | Garde-fou |
|---|---|
| Envoyer un e-mail, créer un rendez-vous | Bloqué **dans le code** de la passerelle jusqu'à votre « oui » |
| Confirmer une réservation, tout engagement | L'agent doit vous demander (bouton « Valider ») ; contrôle automatique de la plateforme en plus |
| Envoyer un WhatsApp | Impossible techniquement : c'est vous qui appuyez sur Envoyer |
| Payer | Jamais. Il s'arrête à la page de paiement et vous envoie le lien |
| Obéir à un e-mail ou une page web | Interdit : le contenu externe est traité comme une donnée |
| Lire vos mots de passe Google | Impossible : les jetons Google restent dans la passerelle, jamais dans le conteneur de l'agent |
| Être utilisé par quelqu'un d'autre | Seuls votre identifiant Telegram, votre numéro WhatsApp, le secret du connecteur et le jeton Siri sont acceptés |

## Ce que ça coûte

- **Agent** : Claude Opus 5.5 à 4 $ / 20 $ par million de jetons, plus 0,08 $ par heure de travail effectif. Pour un usage personnel quotidien, comptez environ 20 à 80 $ par mois selon l'intensité. Les tâches planifiées sont plafonnées à 2 $ chacune (`DEPLOYMENT_BUDGET_CENTS`). Pour plafonner aussi les conversations, réglez `SESSION_BUDGET_CENTS`.
- **Passerelle** : environ 7 $ par mois sur Render (plan Starter, toujours allumé, avec disque).
- Telegram, Google et le connecteur claude.ai sont gratuits.

---

## Installation (environ 45 minutes, une seule fois)

### 1. Clé Anthropic

Sur https://platform.claude.com, créez une clé API (Settings › API keys) et ajoutez un moyen de paiement.

### 2. Accès au dépôt (pour les skills)

Sur GitHub › Settings › Developer settings › Fine-grained tokens : créez un jeton limité au dépôt `test-codex`, avec la permission **Contents : Read-only**. Ce sera `GITHUB_TOKEN`.

Les skills doivent être sur la branche indiquée par `GITHUB_BRANCH` : fusionnez la pull request, ou mettez temporairement `GITHUB_BRANCH=claude/instinct-ia-project-rgw3vl`.

### 3. Google (Gmail, Agenda, Contacts)

1. https://console.cloud.google.com › créez un projet.
2. « API et services » › activez **Gmail API**, **Google Calendar API** et **People API**.
3. « Écran de consentement OAuth » : type Externe, ajoutez votre adresse comme utilisateur test.
4. « Identifiants » › Créer › ID client OAuth › **Application de bureau** : notez l'ID et le secret.
5. Sur votre ordinateur :
   ```bash
   cd instinct
   pip install -r requirements.txt
   export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=...
   python scripts/google_auth.py
   ```
   Un navigateur s'ouvre. Acceptez, puis copiez la ligne `GOOGLE_REFRESH_TOKEN=...` affichée.

### 4. Créer l'agent chez Anthropic

```bash
export ANTHROPIC_API_KEY=... GITHUB_REPO_URL=https://github.com/znatysacha-jpg/test-codex GITHUB_TOKEN=...
python scripts/provision.py --dry-run   # vérifie
python scripts/provision.py             # crée l'agent, son conteneur, sa mémoire et les 3 tâches planifiées
```

Gardez les trois lignes `AGENT_ID`, `ENVIRONMENT_ID` et `MEMORY_STORE_ID` affichées à la fin.

### 5. Telegram (recommandé pour les notifications)

1. Dans Telegram, écrivez à **@BotFather** › `/newbot` › notez le jeton (`TELEGRAM_BOT_TOKEN`).
2. Écrivez à **@userinfobot** pour connaître votre identifiant (`OWNER_TELEGRAM_ID`).

### 6. Déployer la passerelle sur Render

1. https://render.com › New › **Blueprint** › choisissez ce dépôt. Render lit `instinct/render.yaml`.
2. Remplissez les variables demandées (voir `.env.example`). Render génère automatiquement **`MCP_SECRET`** et **`SIRI_TOKEN`** : vous les retrouverez dans l'onglet Environment.
3. Une fois en ligne, notez l'adresse (`https://instinct-perso-xxxx.onrender.com`) et vérifiez `…/health`.
4. Branchez Telegram : relancez `PUBLIC_BASE_URL=https://… TELEGRAM_BOT_TOKEN=… TELEGRAM_WEBHOOK_SECRET=… python scripts/provision.py --skip-deployments`, avec le même `TELEGRAM_WEBHOOK_SECRET` que sur Render.

### 7. Webhook Anthropic (pour les tâches planifiées)

Console Anthropic › Manage › **Webhooks** › ajoutez `https://<passerelle>/anthropic/webhook` avec les événements `session.status_idled`, `deployment_run.succeeded` et `deployment_run.failed`. Copiez le secret `whsec_…` dans `ANTHROPIC_WEBHOOK_SIGNING_KEY` sur Render.

Sans webhook, tout fonctionne quand même, mais les tâches planifiées arrivent avec 1 à 2 minutes de retard (la passerelle vérifie toutes les 90 secondes).

### 8. L'app iPhone

1. claude.ai › Réglages › **Connecteurs** › « Ajouter un connecteur personnalisé » :
   - nom : **`Instinct perso`** (exactement ce nom),
   - URL : `https://<passerelle>/mcp/<MCP_SECRET>/`.
2. Ouvrez l'app : https://claude.ai/artifact/XJ1tgyuKw1UainZUMREg2n, puis autorisez le connecteur quand Claude le demande.
3. Sur l'iPhone, ouvrez ce lien dans l'app Claude ou dans Safari, puis Partager › « Sur l'écran d'accueil ».

### 9. Siri

Dans l'app Raccourcis :
1. Nouveau raccourci « Instinct ».
2. « Dicter le texte » (français).
3. « Obtenir le contenu de l'URL » : `https://<passerelle>/siri`, méthode **POST**, en-tête `Authorization` = `Bearer <SIRI_TOKEN>`, corps **JSON** avec le champ `texte` = *Texte dicté*.
4. « Obtenir la valeur du dictionnaire » pour la clé `reponse`.
5. « Énoncer le texte ».

Dites « Dis Siri, Instinct », puis votre demande. Siri lit la première réponse. Les validations et les cartes arrivent dans l'app et sur Telegram.

### 10. WhatsApp comme canal (optionnel, à vos risques)

⚠️ Depuis le 15 janvier 2026, les conditions de l'API WhatsApp Business **interdisent les assistants IA généralistes**, et un message envoyé plus de 24 h après votre dernier message exige un modèle validé par Meta. Pour **écrire à vos contacts**, vous n'en avez pas besoin : l'outil « message WhatsApp prêt » marche sans. Pour parler à l'agent *par* WhatsApp quand même : créez une app sur developers.facebook.com (produit WhatsApp), renseignez `WHATSAPP_*` et `OWNER_WHATSAPP_NUMBER`, puis déclarez le webhook `https://<passerelle>/whatsapp/webhook` avec le `WHATSAPP_VERIFY_TOKEN`.

### 11. Les premières minutes

Dites-lui :
- « Je m'appelle …, mon téléphone pour les réservations est …, mon e-mail est … » (il l'enregistre dans sa mémoire).
- Vos préférences : train ou avion, siège, quartiers, cuisine, allergies, budget.
- Votre activité, vos clients cibles, votre équipe.

---

## Réglages utiles

| Pour… | Faire |
|---|---|
| Changer sa personnalité ou ses règles | Modifier `agents/instinct-perso/agent.md`, puis `python scripts/provision.py` (crée une nouvelle version) |
| Changer les horaires des tâches | Modifier `deployments/*.md`, puis `python scripts/provision.py` |
| Qu'il réserve sur **n'importe quel** site | Dans `environment.yaml`, remplacer le réseau par `{type: unrestricted}`. Plus capable, mais une page piégée pourrait alors pousser l'agent à envoyer le contenu de sa mémoire vers un site inconnu. Vos jetons Google et GitHub, eux, ne sont jamais exposés |
| Repartir d'une conversation vierge | `/new` dans Telegram, ou Réglages › Nouvelle conversation dans l'app (la mémoire reste) |
| L'arrêter net | `/stop`, ou Réglages › Arrêter l'agent |
| Voir ce qu'il fait en direct | Console Anthropic › Sessions |

## Limites actuelles (à connaître)

- **Paiements** : jamais faits par l'agent, il s'arrête au lien de paiement.
- **Réservations de restaurant** : certains sites, comme TheFork, bloquent parfois les navigateurs automatiques. L'agent passe alors au plan B (lien, e-mail ou message WhatsApp) et vous le dit. Le site propre d'un restaurant n'est joignable qu'en réseau `unrestricted`.
- **Messages vocaux** : pas encore compris sur Telegram et WhatsApp (utilisez la dictée du clavier ou Siri).
- **Appels téléphoniques** à votre place : pas encore (possible plus tard avec un service de voix IA).
- **WhatsApp** : l'agent prépare les messages pour vos contacts, il ne les envoie pas.

## Développement

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # 26 tests, sans réseau ni clé
uvicorn gateway.app:create_app --factory --reload
```
