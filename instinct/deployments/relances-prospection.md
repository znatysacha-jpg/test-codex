---
name: Relances de prospection
schedule: {type: cron, expression: "17 16 * * 1-5", timezone: Europe/Paris}
---
[Tâche planifiée] Relances de prospection.

1. Lis crm/pipeline.md et les fiches des prospects concernés.
2. Pour chaque prospect dont la prochaine action est due aujourd'hui ou en retard : vérifie dans Gmail s'il a répondu (gmail_search sur son adresse ou son entreprise).
3. S'il a répondu : mets à jour sa fiche et le pipeline, résume sa réponse.
4. Sinon : prépare une relance courte et personnalisée en brouillon (gmail_draft), jamais d'envoi. Mets à jour la date de prochaine action.
5. Envoie UN message de synthèse : réponses reçues, brouillons préparés, prospects à abandonner.
