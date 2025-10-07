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

Le script fonctionne aussi bien en mode interactif (par défaut) qu'en mode non
interactif pour vos tests automatisés et exporte les résultats dans un fichier
Excel (`.xlsx`) contenant les colonnes **Nom**, **Prénom**, **Email**, **Numéro
de téléphone**, **Arrondissement** et **Âge**.

#### Mode interactif

Lancez simplement le script sans arguments. Il vous guidera étape par étape :

```bash
python3 scraper_bot.py
```

1. **Source des URL** : choisissez de coller directement les URL (séparées par
   des espaces ou des virgules) ou d'indiquer un fichier texte les contenant.
2. **Localisations** : saisissez une ou plusieurs villes/régions séparées par
   des virgules (ex. `Paris,Lyon`).
3. **Âge minimum** : entrez un nombre ou laissez vide pour ignorer la borne
   basse.
4. **Âge maximum** : entrez un nombre ou laissez vide pour ignorer la borne
   haute.

#### Mode non interactif

Pour éviter toute invite (utile en script ou pour des tests automatisés),
fournissez les filtres directement en paramètres et activez le drapeau
`--non-interactive` :

```bash
python3 scraper_bot.py \
    --urls https://example.com https://example.org \
    --locations Paris Lyon \
    --min-age 25 --max-age 40 \
    --non-interactive
```

Si vous ne fournissez pas d'options de filtrage supplémentaires en mode
non-interactif, le script ne filtrera ni par localisation ni par âge.

#### Mode automatique via fichier de configuration

Pour lancer le bot sans aucune intervention (simplement exécuter le script et
récupérer le fichier Excel final), créez un fichier `scraper_config.json` dans
le même dossier que `scraper_bot.py` :

```json
{
  "urls": ["https://example.com", "https://example.org"],
  "locations": ["Paris", "Lyon"],
  "min_age": 25,
  "max_age": 45,
  "output": "mes-leads.xlsx"
}
```

Au prochain lancement (`python3 scraper_bot.py`), la configuration sera chargée
automatiquement et le script n'affichera aucune question avant de générer le
fichier d'export. Vous pouvez également spécifier un autre fichier de
configuration avec `--config mon_fichier.json`. Les clés disponibles sont :

- `urls`: liste d'URL à visiter (ou chaîne unique).
- `input_file`: chemin d'un fichier texte listant les URL.
- `output`: destination du fichier généré.
- `timeout`: délai maximal par page (en secondes).
- `locations`: liste (ou chaîne avec virgules) de mots-clés de localisation.
- `min_age` / `max_age`: bornes d'âge à respecter.
- `non_interactive` / `auto`: booléen permettant de forcer (ou non) l'absence
  d'invite.

#### Lecture depuis un fichier

Vous pouvez également charger une liste d'URL à partir d'un fichier texte (une
URL par ligne) :

```bash
python3 scraper_bot.py --input-file urls.txt
```

### Options principales

- `--urls`: une ou plusieurs URL à analyser.
- `--input-file`: fichier texte contenant des URL (exclusif avec `--urls`).
- `--output`: chemin du fichier généré (par défaut `leads.xlsx`).
- `--timeout`: délai maximal en secondes pour récupérer chaque page (10s par défaut).
- `--locations`: mots-clés de localisation à rechercher (mode non interactif).
- `--min-age` / `--max-age`: bornes d'âge à respecter (mode non interactif).
- `--non-interactive`: exécute le script sans questions (utilise les options ou aucun filtre). Nécessite `--urls` ou `--input-file`.
- `--config`: fichier JSON de configuration (par défaut `scraper_config.json` si présent).

Seules les pages contenant à la fois au moins un mot-clé de localisation fourni
et une mention d'âge dans l'intervalle indiqué seront conservées. Le fichier
Excel généré propose autant de lignes que de contacts détectés et tente de
remplir les informations de nom/prénom (via les champs identifiés sur la page ou
en déduisant les parties d'adresse e-mail), ainsi que les numéros de téléphone,
arrondissements et âges trouvés.

Chaque contact est enregistré même si une seule information est disponible sur
la page (par exemple uniquement un numéro de téléphone ou uniquement un
arrondissement). Les autres champs resteront simplement vides dans l'export,
ce qui vous permet de capitaliser sur toute donnée utile rencontrée.

> 💡 Astuce : si vous souhaitez conserver un fichier CSV, indiquez simplement une
> sortie avec l'extension `.csv` (ex. `--output leads.csv`).

### Conseils

- Respectez les conditions d'utilisation et la législation locale avant de
  scraper un site web.
- Adaptez les URL ciblées et combinez les résultats avec vos outils de
  prospection habituels pour créer des campagnes pertinentes.
