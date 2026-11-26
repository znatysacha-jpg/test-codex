# Bibliothèque de skills Claude Code

**147 skills** sélectionnés parmi les dépôts les plus populaires de GitHub, installés dans `.claude/skills/`.
Claude Code les charge automatiquement dans ce dépôt : il choisit le bon skill selon la tâche, ou vous pouvez en appeler un avec `/nom-du-skill`.

## Sources (classées par popularité)

| Dépôt | ⭐ | Licence | Domaine |
|---|---|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills) | 333k | MIT | Dev : conception, debug, prototypage |
| [obra/superpowers](https://github.com/obra/superpowers) | 327k | MIT | Dev : méthode complète (plans, TDD, revue de code) |
| [anthropics/skills](https://github.com/anthropics/skills) | 201k | Apache 2.0 | Officiel Anthropic : design front, tests web, MCP |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | 154k | MIT | Design UI/UX, design system, marque |
| [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 122k | MIT | Design de sites « niveau pro » |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 121k | MIT | Dev : ingénierie de production |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | 117k | Apache 2.0 | Design : critique, audit, finitions |
| [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | 61k | MIT | Design web « anti-IA générique » |
| [wshobson/agents](https://github.com/wshobson/agents) | 43k | MIT | Design UI, accessibilité, équipe |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | 31k | MIT | Gestion de projet, produit, tech, direction |
| [phuryn/pm-skills](https://github.com/phuryn/pm-skills) | 28k | MIT | Product management |
| [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 28k | MIT | Planification persistante |
| [automazeio/ccpm](https://github.com/automazeio/ccpm) | 8k | MIT | Gestion de projet avec GitHub Issues |
| [RefoundAI/lenny-skills](https://github.com/RefoundAI/lenny-skills) | 1,5k | MIT | Produit et leadership (Lenny's Podcast) |
| [manager-dot-dev/manager-skills](https://github.com/manager-dot-dev/manager-skills) | 124 | MIT | Management d'équipe tech |
| [jcesarperez/claude-em](https://github.com/jcesarperez/claude-em) | 95 | MIT | Stratégie et vision (cadre de Will Larson) |

Chaque dossier de skill contient le fichier de licence de son dépôt d'origine.

---

## 📋 Gestion de projet et produit (42)

**Pilotage de projet**

| Skill | À quoi il sert |
|---|---|
| `planning-with-files` | Plan de travail persistant (`task_plan.md`, `findings.md`, `progress.md`) pour les tâches longues |
| `ccpm` | Chaîne complète PRD → epic → GitHub Issues → agents en parallèle → livraison |
| `senior-pm` | Pilotage multi-chantiers : rapports d'avancement, registre des risques, capacité |
| `scrum-master` | Sprints : vélocité, santé du sprint, burndown |
| `sprint-plan` | Préparer un sprint : capacité, choix des stories, dépendances |
| `retro` | Animer une rétrospective avec des actions, des responsables et des échéances |
| `pre-mortem` | Identifier ce qui pourrait faire échouer un lancement |
| `stakeholder-map` | Cartographier les parties prenantes et prévoir la communication avec chacune |
| `jira-expert` | Jira : JQL, workflows, automatisations |
| `meeting-analyzer` / `summarize-meeting` | Analyser et résumer des réunions |
| `team-communications` | Points hebdo, rapports, annonces internes |
| `decision-logger` | Journal des décisions |
| `planning-cadence` | Rythme de planification (annuel, trimestriel, hebdo) |
| `shipping-velocity` | Livrer plus vite sans perdre en qualité |

**Product management**

| Skill | À quoi il sert |
|---|---|
| `create-prd` | Rédiger un PRD (document d'exigences produit) |
| `user-stories` / `agile-product-owner` | User stories, critères d'acceptation, backlog |
| `prioritization-frameworks` / `prioritize-features` | RICE, ICE, Kano, MoSCoW… et priorisation du backlog |
| `product-manager-toolkit` | Boîte à outils du PM (RICE, entretiens, go-to-market) |
| `product-vision` / `product-strategist` | Vision produit, roadmap, OKR |
| `outcome-roadmap` / `roadmap-communicator` | Roadmap orientée résultats, notes de version |
| `brainstorm-okrs` | Définir des OKR d'équipe |
| `north-star-metric` | Choisir la métrique « étoile du nord » |
| `product-discovery` / `continuous-discovery` / `opportunity-solution-tree` | Discovery produit (méthode de Teresa Torres) |
| `interview-script` / `summarize-interview` | Préparer et synthétiser des entretiens clients |
| `user-personas` / `customer-journey-map` | Personas et parcours client |
| `competitor-analysis` / `market-sizing` | Analyse concurrentielle, taille de marché (TAM, SAM, SOM) |
| `lean-canvas` / `value-proposition` / `pricing-strategy` | Modèle économique, proposition de valeur, prix |
| `experiment-designer` | Tests A/B |
| `measuring-pmf` | Mesurer l'adéquation produit-marché |
| `product-taste` | Développer son jugement produit |

## 💻 Développement (44)

**Méthode de travail**

| Skill | À quoi il sert |
|---|---|
| `brainstorming` / `idea-refine` / `grill-me` | Clarifier et challenger une idée avant de coder |
| `spec-driven-development` | Écrire la spec avant le code |
| `writing-plans` / `planning-and-task-breakdown` | Découper le travail en tâches |
| `executing-plans` / `incremental-implementation` | Avancer par petites étapes vérifiables |
| `subagent-driven-development` / `dispatching-parallel-agents` | Faire travailler plusieurs agents en parallèle |
| `test-driven-development` | TDD : test rouge → code → test vert |
| `systematic-debugging` / `diagnosing-bugs` | Trouver la cause racine d'un bug |
| `verification-before-completion` | Prouver que ça marche avant de dire « fini » |
| `requesting-code-review` / `receiving-code-review` / `code-reviewer` | Revue de code |
| `using-git-worktrees` / `finishing-a-development-branch` / `git-workflow-and-versioning` | Git : branches, commits, versions, PR |
| `handoff` / `context-engineering` | Transmettre le contexte entre sessions et bien configurer l'agent |
| `prototype` | Prototype jetable pour tester une idée |

**Architecture et qualité**

| Skill | À quoi il sert |
|---|---|
| `senior-architect` / `codebase-design` / `improve-codebase-architecture` | Architecture, modules, refonte |
| `domain-modeling` | Modèle métier, glossaire, ADR |
| `api-and-interface-design` | Concevoir des API stables |
| `tech-stack-evaluator` | Comparer des technos |
| `code-simplification` | Simplifier du code sans changer son comportement |
| `documentation-and-adrs` | Documentation et décisions d'architecture |
| `security-and-hardening` | Sécurité (OWASP, RGPD, dépendances) |
| `performance-optimization` | Performance (Core Web Vitals, requêtes N+1…) |
| `observability-and-instrumentation` | Logs, métriques, traces, alertes |

**Expertise technique**

| Skill | À quoi il sert |
|---|---|
| `senior-fullstack` / `senior-frontend` / `senior-backend` / `frontend-ui-engineering` | Développement full-stack, front, back |
| `senior-devops` / `shipping-and-launch` | CI/CD, déploiement, checklist de mise en production |
| `senior-qa` / `webapp-testing` | Tests (Jest, Playwright) |
| `incident-commander` | Gestion d'incident et post-mortem |
| `mcp-builder` | Créer des serveurs MCP |

## 🎨 Design (17)

| Skill | À quoi il sert |
|---|---|
| `ui-ux-pro-max` | Intelligence design UI/UX (web, mobile, desktop) avec base de styles, palettes, polices |
| `impeccable` | Concevoir, critiquer, auditer et peaufiner une interface |
| `design-taste-frontend` | Sites vitrines de niveau professionnel (avec vérification dans le navigateur) |
| `hallmark` | Pages qui ont l'air conçues par un designer, pas générées par une IA |
| `frontend-design` | Direction visuelle forte (officiel Anthropic) |
| `visual-design-foundations` | Typographie, couleurs, espacements |
| `design-system` / `ui-design-system` / `design-system-patterns` | Design systems et tokens |
| `ui-styling` | Interfaces avec shadcn/ui et Tailwind |
| `brand` | Identité de marque, ton, charte |
| `interaction-design` | Micro-interactions et animations |
| `responsive-design` | Mises en page adaptatives |
| `ux-researcher-designer` | Personas, parcours, tests d'utilisabilité |
| `design-qa` | Contrôle qualité avant livraison |
| `wcag-audit-patterns` | Audit d'accessibilité |
| `apple-hig-expert` | Guidelines Apple (iOS, macOS) |

## 👥 Gestion d’équipe et leadership (44)

**Management au quotidien** (manager-skills, à initialiser avec `em-context`)

| Skill | À quoi il sert |
|---|---|
| `em-context` | **À lancer en premier** : décrire votre équipe, votre organisation et vos priorités |
| `1on1s` | Préparer et réussir ses entretiens individuels |
| `feedback` | Donner et recevoir du feedback (méthode SBI) |
| `delegation` | Arrêter d'être le goulot d'étranglement |
| `performance-reviews` | Évaluations, sous-performance, plan d'amélioration (PIP) |
| `career-development` | Accompagner l'évolution de carrière |
| `engineer-motivation` / `managing-high-performers` | Motivation et gestion des meilleurs profils |
| `retaining-developers` | Éviter les départs |
| `team-health` / `shadow-work` | Santé de l'équipe et travail invisible |
| `meetings` | Moins de réunions, des réunions plus utiles |
| `difficult-situations` | Situations délicates (licenciement, comportement inapproprié…) |
| `managing-up` / `influence` / `managing-yourself` | Gérer son manager, influencer, se gérer soi-même |
| `developer-productivity` | Mesurer la productivité (DORA, DevEx) |
| `knowledge-sharing` / `written-communication` | Partage de connaissances et communication écrite |
| `management-transitions` | Premier poste de manager, reprise d'une équipe |
| `team-composition` / `working-with-pm` | Composition d'équipe, binôme avec le PM |

**Recrutement et organisation**

| Skill | À quoi il sert |
|---|---|
| `hiring` / `interviewing-evaluating-candidates` | Processus de recrutement et entretiens |
| `team-composition-analysis` | Plan d'embauche et structure d'équipe (startup) |
| `founding-exec-team` | Cofondateurs et premières embauches de direction |
| `org-design` | Structure d'organisation produit et tech |
| `chro-advisor` | RH : salaires, rétention, performance |

**Culture et direction**

| Skill | À quoi il sert |
|---|---|
| `team-culture` / `culture-architect` | Construire la culture d'équipe |
| `fixing-underperforming-teams` | Redresser une équipe en difficulté |
| `coaching-development` | Passer d'exécutant à coach |
| `engineering-health` | Santé de l'ingénierie, dette technique |
| `change-management` | Conduire un changement |
| `high-stakes-decisions` | Prendre des décisions à fort enjeu |
| `stakeholder-alignment` / `executive-communication` | Aligner les parties prenantes et communiquer avec la direction |
| `write-strategy` / `write-vision` | Rédiger stratégie et vision (cadre de Will Larson) |
| `vpe-advisor` / `cto-advisor` / `chief-of-staff` | Conseils de VP Engineering, CTO, chief of staff |
| `org-health-diagnostic` / `founder-coach` | Santé de l'organisation et coaching de fondateur |

---

## Ce qui n'a pas été retenu, et pourquoi

- **deanpeters/Product-Manager-Skills** (8k ⭐) : licence CC BY-NC-SA, qui **interdit l'usage commercial**.
- **garrytan/gstack** (143k ⭐) : ses skills dépendent de ses propres outils (navigateur, binaires) et ne fonctionnent pas seuls.
- **vercel-labs/agent-skills** (35k ⭐) : pas de licence déclarée.
- **affaan-m/ECC**, **EveryInc/compound-engineering-plugin** : ce sont des systèmes complets (harnais et plugin) plutôt que des skills à piocher.

## Remarques techniques

- **`planning-with-files`** et **`design-taste-frontend`** déclarent des hooks qui exécutent leurs scripts locaux pendant qu'ils sont actifs (gestion du plan, contrôle qualité du design). Ces hooks n'envoient rien sur le réseau.
- **`hallmark`** ne génère des images via l'API Together AI que si la variable `TOGETHER_API_KEY` est définie.
- **`design-system`** peut télécharger des photos libres depuis Pexels pour des slides.
- **`design-taste-frontend`** a besoin de Node 22+ et de Chrome/Chromium.
- Pour mettre à jour un skill, recopiez son dossier depuis le dépôt source.
