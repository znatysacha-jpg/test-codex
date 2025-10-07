# test-codex

Premier dépôt pour tests ChatGPT

## Bot de scraping pour génération de leads

Ce dépôt contient désormais un script `scraper_bot.py` qui permet de récupérer
les adresses e-mail et numéros de téléphone présents sur des pages web afin de
constituer une base de prospects.

### Prérequis

Le script utilise uniquement la bibliothèque standard de Python (version 3.8 ou
plus récente recommandée) et ne nécessite aucune installation additionnelle.

### Utilisation

Pour lancer le bot avec l'invite interactive, placez-vous dans le dossier du
projet et exécutez :

```bash
python3 scraper_bot.py
```

Le script vous posera successivement trois questions :

1. **Localisations** : saisissez une ou plusieurs villes/régions séparées par
   des virgules (ex. `Paris,Lyon`).
2. **Âge minimum** : entrez un nombre ou laissez vide pour ignorer la borne
   basse.
3. **Âge maximum** : entrez un nombre ou laissez vide pour ignorer la borne
   haute.

Après ces réponses, choisissez l'une des méthodes suivantes pour fournir les
URL à analyser.

Vous pouvez fournir les URL directement en ligne de commande :

```bash
python scraper_bot.py --urls https://example.com https://example.org --output leads.csv
```

Ou charger une liste d'URL à partir d'un fichier texte (une URL par ligne) :

```bash
python scraper_bot.py --input-file urls.txt
```

Les options disponibles :

- `--urls`: une ou plusieurs URL à analyser.
- `--input-file`: fichier texte contenant des URL (exclusif avec `--urls`).
- `--output`: chemin du fichier CSV généré (par défaut `leads.csv`).
- `--timeout`: délai maximal en secondes pour récupérer chaque page (10s par défaut).

Lors de l'exécution, le script vous demandera également :

- une liste de mots-clés de localisation (séparés par des virgules) qui doivent
  apparaître dans la page pour que les contacts soient retenus ;
- un âge minimum et/ou maximum à rechercher dans le contenu de la page.

Seules les pages contenant à la fois au moins un mot-clé de localisation fourni
et une mention d'âge dans l'intervalle indiqué seront conservées. Le fichier CSV
généré contient trois colonnes (`url`, `email`, `phone`). Chaque contact détecté
sur une page filtrée est exporté sur une ligne distincte.

### Conseils

- Respectez les conditions d'utilisation et la législation locale avant de
  scraper un site web.
- Adaptez les URL ciblées et combinez les résultats avec vos outils de
  prospection habituels pour créer des campagnes pertinentes.
