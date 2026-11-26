# Bibliothèque de skills Claude Code

56 skills sélectionnés sur GitHub, installés dans `.claude/skills/`.
Claude Code les charge automatiquement dans ce dépôt : il choisit le bon skill selon la tâche, ou vous pouvez en appeler un avec `/nom-du-skill`.

## Sources

| Dépôt | Licence | Ce qu'on en a pris |
|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) (officiel Anthropic) | Apache 2.0 | frontend-design, webapp-testing, mcp-builder |
| [obra/superpowers](https://github.com/obra/superpowers) | MIT | Méthode de développement (plans, TDD, debug, revue de code) |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | MIT | Gestion de projet, produit, équipe tech, direction |
| [wshobson/agents](https://github.com/wshobson/agents) | MIT | Design UI, accessibilité, composition d'équipe |
| [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | MIT | Design web « anti-IA générique » |
| [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | MIT | Planification persistante sur fichiers |

Chaque skill garde son fichier de licence d'origine lorsqu'il en fournit un.

## 📋 Gestion de projet et produit (13)

| Skill | À quoi il sert |
|---|---|
| `planning-with-files` | Plan de travail persistant (`task_plan.md`, `findings.md`, `progress.md`) pour les tâches longues |
| `senior-pm` | Pilotage multi-chantiers : plans, rapports d'avancement, registre des risques |
| `scrum-master` | Sprints : vélocité, santé du sprint, rétrospectives, burndown |
| `agile-product-owner` | Backlog : user stories, critères d'acceptation, découpage d'epics |
| `product-manager-toolkit` | Priorisation RICE, synthèse d'entretiens clients, PRD, go-to-market |
| `product-discovery` | Valider une idée : hypothèses, sprints de discovery, adéquation problème/solution |
| `product-strategist` | Vision, roadmap, OKR trimestriels en cascade |
| `roadmap-communicator` | Récits de roadmap, notes de version, changelogs |
| `experiment-designer` | Tests A/B : hypothèses, taille d'échantillon, lecture des résultats |
| `jira-expert` | Jira : JQL, workflows, automatisations, tableaux de bord |
| `meeting-analyzer` | Analyse de transcriptions de réunions (Zoom, Otter, Granola…) |
| `team-communications` | Communication interne : points hebdo, rapports, FAQ, annonces |
| `decision-logger` | Journal des décisions et suivi de leur mise en œuvre |

## 💻 Développement (23)

**Méthode de travail (Superpowers)**

| Skill | À quoi il sert |
|---|---|
| `brainstorming` | Clarifier le besoin et la conception avant de coder |
| `writing-plans` | Transformer une spec en plan d'implémentation détaillé |
| `executing-plans` | Exécuter un plan étape par étape avec points de contrôle |
| `subagent-driven-development` | Exécuter un plan en déléguant les tâches à des sous-agents |
| `dispatching-parallel-agents` | Paralléliser des tâches indépendantes |
| `test-driven-development` | TDD : test rouge → code → test vert |
| `systematic-debugging` | Trouver la cause racine d'un bug avant de corriger |
| `verification-before-completion` | Prouver que ça marche avant de dire « c'est fini » |
| `requesting-code-review` / `receiving-code-review` | Demander une revue de code et traiter les retours avec rigueur |
| `using-git-worktrees` / `finishing-a-development-branch` | Isoler une branche de travail et la finaliser proprement (merge, PR) |

**Expertise technique**

| Skill | À quoi il sert |
|---|---|
| `senior-architect` | Choix d'architecture justifiés (monolithe ou microservices, base de données…) |
| `tech-stack-evaluator` | Comparer des frameworks et des stacks (score, coût total) |
| `senior-fullstack` | Démarrer ou auditer un projet complet (Next.js, FastAPI, Django…) |
| `senior-frontend` | React, Next.js, TypeScript, Tailwind |
| `senior-backend` | API REST et GraphQL, authentification, PostgreSQL, tests de charge |
| `senior-devops` | CI/CD, infrastructure as code, déploiements cloud |
| `senior-qa` | Tests Jest, React Testing Library, Playwright |
| `webapp-testing` | Tester une app web locale avec Playwright (captures, logs) |
| `code-reviewer` | Revue de PR, de diff ou de fichier |
| `incident-commander` | Gérer un incident de production et rédiger le post-mortem |
| `mcp-builder` | Créer des serveurs MCP (connecter Claude à des outils et API) |

## 🎨 Design (11)

| Skill | À quoi il sert |
|---|---|
| `hallmark` | Sites et pages qui ont l'air conçus par un designer, pas générés par une IA |
| `frontend-design` | Direction visuelle forte pour une nouvelle interface (officiel Anthropic) |
| `visual-design-foundations` | Typographie, couleurs, espacements, iconographie |
| `ui-design-system` / `design-system-patterns` | Design system : tokens, thèmes, documentation des composants |
| `interaction-design` | Micro-interactions, animations, transitions |
| `responsive-design` | Mises en page adaptatives (container queries, grid, typographie fluide) |
| `ux-researcher-designer` | Personas, parcours utilisateur, tests d'utilisabilité |
| `design-qa` | Contrôle qualité d'un écran avant livraison |
| `wcag-audit-patterns` | Audit d'accessibilité WCAG 2.2 |
| `apple-hig-expert` | Interfaces iOS et macOS conformes aux guidelines Apple |

## 👥 Gestion d'équipe et direction (9)

| Skill | À quoi il sert |
|---|---|
| `vpe-advisor` | Livraisons qui ralentissent, recrutement tech, organisation des équipes |
| `cto-advisor` | Dette technique, direction technique, passage à l'échelle de l'équipe |
| `chro-advisor` | RH : plans de recrutement, grilles de salaires, performance, rétention |
| `team-composition-analysis` | Structure d'équipe, plan d'embauche, répartition du capital |
| `culture-architect` | Définir des valeurs et les traduire en comportements concrets |
| `change-management` | Conduire un changement (réorganisation, pivot, nouvel outil) |
| `org-health-diagnostic` | Bilan de santé de l'organisation |
| `founder-coach` | Fondateur débordé : déléguer, éviter l'épuisement, passer au rôle de manager |
| `chief-of-staff` | Orienter une question vers le bon conseiller et coordonner les sujets transverses |

## Remarques

- **`planning-with-files`** déclare des hooks qui exécutent ses scripts locaux (`scripts/skill-hook.sh`) pendant qu'il est actif. Ils lisent et écrivent les fichiers de plan du projet, sans aucun envoi réseau.
- **`hallmark`** peut générer des images via l'API Together AI seulement si la variable `TOGETHER_API_KEY` est définie. Sinon, il n'utilise aucun réseau.
- Les autres scripts Python fournis (analyse de PR, changelog, scaffolding…) tournent en local et ne lancent que `git` ou `terraform`.
- Pour mettre à jour un skill, recopiez son dossier depuis le dépôt source indiqué plus haut.
