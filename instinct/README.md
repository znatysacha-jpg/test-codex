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
- `agents/instinct-perso/environment.yaml` : son conteneur (accès complet au web).
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
| Divulguer sa mémoire via une page piégée | Risque réduit mais non nul avec l'accès complet au web : l'agent traite les pages comme des données, et la plateforme évalue chaque action. Ne lui confiez pas de secret (il refuse de les mémoriser) |
| Être utilisé par quelqu'un d'autre | Seuls votre identifiant Telegram, votre numéro WhatsApp, le secret du connecteur et le jeton Siri sont acceptés |

## Ce que ça coûte

- **Agent** : Claude Opus 5.5 à 4 $ / 20 $ par million de jetons, plus 0,08 $ par heure de travail effectif. Pour un usage personnel quotidien, comptez environ 20 à 80 $ par mois selon l'intensité. Les tâches planifiées sont plafonnées à 2 $ chacune (`DEPLOYMENT_BUDGET_CENTS`). Pour plafonner aussi les conversations, réglez `SESSION_BUDGET_CENTS`.
- **Passerelle** : environ 7 $ par mois sur Render (plan Starter, toujours allumé, avec disque).
- Telegram, Google et le connecteur claude.ai sont gratuits.

---

## Installation (environ 30 minutes, une seule fois)

Vous créez 4 comptes ou clés, vous cliquez sur « Deploy », et la passerelle fait le reste : elle crée l'agent chez Anthropic, sa mémoire, ses tâches planifiées, et branche Telegram.

### 1. Les clés à préparer

| Clé | Où la créer |
|---|---|
| `ANTHROPIC_API_KEY` | https://platform.claude.com › Settings › API keys (ajoutez un moyen de paiement) |
| `TELEGRAM_BOT_TOKEN` | Dans Telegram, écrivez à **@BotFather** › `/newbot` |
| `OWNER_TELEGRAM_ID` | Dans Telegram, écrivez à **@userinfobot** : il répond votre numéro d'identifiant |
| `GITHUB_TOKEN` | GitHub › Settings › Developer settings › Fine-grained tokens : dépôt `test-codex` uniquement, **Contents : Read-only** (il apporte les skills) |
| `GOOGLE_CLIENT_ID` et `GOOGLE_CLIENT_SECRET` | Voir l'étape 2 |

### 2. Google (Gmail, Agenda, Contacts)

1. https://console.cloud.google.com › créez un projet.
2. « API et services » › activez **Gmail API**, **Google Calendar API** et **People API**.
3. « Écran de consentement OAuth » : type **Externe**, puis **Publier l'application** (état « En production »). En état « Test », Google coupe l'accès au bout de 7 jours. Google affichera un avertissement « application non vérifiée » : c'est normal pour une app personnelle, cliquez sur « Paramètres avancés » › « Continuer ».
4. « Identifiants » › Créer › ID client OAuth › **Application Web**. Ajoutez l'URI de redirection `https://<adresse-de-la-passerelle>/google/callback`. Vous connaîtrez l'adresse à l'étape 3 et pourrez revenir l'ajouter.

### 3. Déployer

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/znatysacha-jpg/test-codex)

1. Cliquez sur le bouton, connectez votre GitHub, puis collez les clés de l'étape 1. Les secrets techniques (`MCP_SECRET`, `SIRI_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`) sont générés automatiquement.
2. Si les skills ne sont pas encore sur `main` (pull request non fusionnée), mettez `GITHUB_BRANCH=claude/instinct-ia-project-rgw3vl`.
3. Attendez la fin du déploiement (environ 5 minutes). Render donne une adresse du type `https://instinct-perso-xxxx.onrender.com`. Ajoutez `…/google/callback` dans Google (étape 2.4) si ce n'est pas fait.
4. Vérifiez `https://<adresse>/health` : `"ok": true` signifie que l'agent est créé chez Anthropic.

### 4. Tout brancher depuis Telegram

Envoyez **`/start`** à votre bot. Il vous répond (et à vous seul) avec :
- l'adresse du **connecteur** à ajouter dans claude.ai (pour l'app iPhone) ;
- l'adresse et la clé pour le **raccourci Siri** ;
- un **lien pour connecter Google**, valable 30 minutes (ou plus tard avec `/google`, ou depuis l'app › Réglages › Connecter Google).

### 5. L'app iPhone

1. claude.ai › Réglages › **Connecteurs** › « Ajouter un connecteur personnalisé », nom **`Instinct perso`** (exactement), adresse reçue sur Telegram.
2. Ouvrez https://claude.ai/artifact/XJ1tgyuKw1UainZUMREg2n et autorisez le connecteur quand Claude le demande.
3. Sur l'iPhone : Partager › « Sur l'écran d'accueil ».

### 6. Siri

App Raccourcis › nouveau raccourci « Instinct » :
1. « Dicter le texte » (français).
2. « Obtenir le contenu de l'URL » : adresse `…/siri` reçue sur Telegram, méthode **POST**, en-tête `Authorization` = `Bearer …` (reçu sur Telegram), corps **JSON** avec `texte` = *Texte dicté*.
3. « Obtenir la valeur du dictionnaire », clé `reponse`.
4. « Énoncer le texte ».

### 7. Facultatif

- **Webhook Anthropic** : console Anthropic › Manage › Webhooks, adresse `…/anthropic/webhook`, événements `session.status_idled`, `deployment_run.succeeded` et `deployment_run.failed`. Copiez le secret `whsec_…` dans `ANTHROPIC_WEBHOOK_SIGNING_KEY` sur Render. Sans lui, les tâches planifiées arrivent avec 1 à 2 minutes de retard.
- **WhatsApp comme canal** : ⚠️ depuis le 15 janvier 2026, l'API WhatsApp Business interdit les assistants IA généralistes. Pour **écrire à vos contacts**, vous n'en avez pas besoin (carte « Ouvrir dans WhatsApp »). Sinon : app sur developers.facebook.com (produit WhatsApp), variables `WHATSAPP_*` et `OWNER_WHATSAPP_NUMBER`, webhook `…/whatsapp/webhook`.

### 8. Les premières minutes

Dites-lui votre nom, téléphone et e-mail pour les réservations, vos préférences (train ou avion, siège, quartiers, cuisine, allergies, budget), votre activité, vos clients cibles et votre équipe. Il les enregistre dans sa mémoire.

---

## Réglages utiles

| Pour… | Faire |
|---|---|
| Changer sa personnalité ou ses règles | Modifier `agents/instinct-perso/agent.md` et pousser : au redéploiement, la passerelle met l'agent à jour (nouvelle version) |
| Changer les horaires des tâches | Modifier `deployments/*.md` et pousser (mise à jour au redéploiement) |
| Limiter les sites que l'agent peut ouvrir | Il a accès à **tout le web** (réservations sur n'importe quel site). Pour le restreindre : réseau `limited` + `allowed_hosts` dans `environment.yaml` (voir l'historique git), puis redéployer |
| Repartir d'une conversation vierge | `/new` dans Telegram, ou Réglages › Nouvelle conversation dans l'app (la mémoire reste) |
| L'arrêter net | `/stop`, ou Réglages › Arrêter l'agent |
| Voir ce qu'il fait en direct | Console Anthropic › Sessions |

## Limites actuelles (à connaître)

- **Paiements** : jamais faits par l'agent, il s'arrête au lien de paiement.
- **Réservations de restaurant** : certains sites, comme TheFork, bloquent parfois les navigateurs automatiques. L'agent passe alors au plan B (lien, e-mail ou message WhatsApp) et vous le dit.
- **Messages vocaux** : pas encore compris sur Telegram et WhatsApp (utilisez la dictée du clavier ou Siri).
- **Appels téléphoniques** à votre place : pas encore (possible plus tard avec un service de voix IA).
- **WhatsApp** : l'agent prépare les messages pour vos contacts, il ne les envoie pas.

## Développement

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # 29 tests, sans réseau ni clé
uvicorn gateway.app:create_app --factory --reload
```
