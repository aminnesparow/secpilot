# SecPilot — Couche CI/CD & QA

Couche CI/CD du projet SecPilot : pré-détection SAST multi-outils, normalisation
des findings vers un format JSON pivot, et envoi à l'orchestrateur API_P pour
remédiation automatique par le moteur IA.

## Aperçu

Cette pipeline CI/CD :
1. Exécute les tests unitaires pour Python, JavaScript et Java (triple langage)
2. Lance une analyse SAST avec **plusieurs outils en parallèle** (Semgrep, CodeQL)
3. Normalise tous les findings vers un **format JSON pivot unifié**
4. Envoie le résultat à l'API_P SecPilot qui orchestre la remédiation LLM
5. Collecte les **métriques opérationnelles** (taux One-Shot, MTTR, PRs acceptées)

## Structure du projet

```
secpilot/
├── .github/workflows/     # Pipelines CI/CD (multi-SAST + Juice Shop)
├── schemas/               # Format JSON pivot unifié (finding.schema.json)
├── src/                   # Code source bugué (démonstration multi-langages)
│   ├── python/
│   ├── javascript/
│   └── java/
├── tests/                 # Tests unitaires qui reproduisent les bugs
├── contexts/              # Documentation du contexte métier (3 domaines)
├── scripts/               # Adapters SAST + collecteur de métriques
│   ├── sast_adapter.py            # Entrée unifiée (Semgrep/SonarQube/CodeQL)
│   ├── parse_semgrep_findings.py  # Parser SARIF Semgrep
│   ├── parse_sonarqube_findings.py
│   ├── parse_codeql_findings.py
│   ├── metrics_collector.py       # Collecte des KPI opérationnels
│   └── llm_fix_suggester.py       # Pont LLM (Ollama/Anthropic/OpenAI)
├── .semgrep.yml           # 20+ règles SAST métier (Python/JS/Java)
└── config/                # Configurations des frameworks de test
```

## Domaines métier

### E-Commerce
- **Règle critique** : Les prix ne peuvent pas être négatifs
- **Code** : `src/*/ecommerce/`

### Banque
- **Règle critique** : Refuser les virements si solde insuffisant
- **Code** : `src/*/banking/`

### Santé
- **Règle critique** : Les dosages ne doivent pas dépasser les limites maximales sûres
- **Code** : `src/*/healthcare/`

## Types de bugs

### Bugs classiques
Erreurs de programmation courantes :
- Troncature de division entière
- Erreurs off-by-one
- NullPointerException
- Comparaison de virgule flottante
- Coercition de type
- Sensibilité à la casse

### Bugs contextuels
Nécessitent la connaissance du domaine métier :
- Validation de prix négatif (e-commerce)
- Vérification du solde (banque)
- Application de dose maximale (santé)

## Installation

### Prérequis
- Python 3.11+
- Node.js 20+
- Java 17+
- Maven 3.9+

### Installation locale

```bash
# Cloner le dépôt
git clone https://github.com/votre-org/secpilot.git
cd secpilot

# Installer les dépendances Python
pip install -r requirements.txt

# Installer les dépendances JavaScript
npm install

# Compiler le projet Java
mvn -f config/pom.xml compile
```

## Configuration

### Variables GitHub

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `LLM_PROVIDER` | Provider LLM (`ollama`, `anthropic`, `openai`, `mock`) | `mock` |
| `OLLAMA_URL` | URL du serveur Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modèle Ollama à utiliser | `llama2` |

### Secrets GitHub

| Secret | Description |
|--------|-------------|
| `LLM_API_KEY` | Clé API pour Anthropic ou OpenAI |

## Exécution des tests localement

```bash
# Python
pytest tests/python/ -v -c config/pytest.ini

# JavaScript
npm test

# Java
mvn -f config/pom.xml test
```

## Pipeline CI/CD

La pipeline se déclenche sur :
- Push vers `main`, `develop`, ou `feature/*`
- Pull requests vers `main`

### Étapes de la pipeline
1. Exécution des tests en parallèle pour les trois langages
2. Si des tests échouent → déclenchement de l'analyse LLM
3. Génération des suggestions de correction
4. Post des suggestions en commentaire de PR (pour les pull requests)
5. Upload des suggestions comme artefact du workflow

## Intégration LLM

Le LLM reçoit :
- La sortie des tests échoués
- Le code source pertinent
- La documentation du contexte métier

Il retourne :
- Analyse de la cause racine
- Classification du bug (classique vs contextuel)
- Suggestions de code corrigé
- Conseils de prévention

### Providers supportés

- **Ollama** : Modèles locaux (llama2, codellama, etc.)
- **Anthropic** : API Anthropic
- **OpenAI** : GPT-4
- **Mock** : Provider de test (pas de vraie API)

## Multi-SAST & format JSON pivot

Le module SAST est conçu comme une couche d'adaptation : peu importe l'outil
SAST utilisé (Semgrep, SonarQube, CodeQL, ou n'importe quel autre émetteur
SARIF), la sortie est normalisée vers le format pivot
[`schemas/finding.schema.json`](schemas/finding.schema.json) avant ingestion
par l'API_P SecPilot.

### Usage

```bash
# Semgrep
semgrep scan --config=.semgrep.yml --sarif --output=report.sarif src/
python scripts/sast_adapter.py --source semgrep --input report.sarif --output findings.json

# SonarQube (export issues API)
python scripts/sast_adapter.py --source sonarqube --input issues.json --output findings.json

# CodeQL
codeql database analyze db.db --format=sarif-latest --output=report.sarif
python scripts/sast_adapter.py --source codeql --input report.sarif --output findings.json
```

### Pourquoi un format pivot ?

- **Interopérabilité** : n'importe quel SAST peut alimenter le pipeline IA
- **Routage intelligent** : les agrégats (`by_severity`, `by_domain`, `by_language`)
  permettent au dispatcher LLM de choisir le modèle le plus adapté
- **Évolutivité** : ajouter un nouveau SAST = ajouter un parser, sans toucher
  au reste de l'architecture

## Métriques opérationnelles

```bash
# Enregistrer un run
python scripts/metrics_collector.py record \
    --findings 41 --fixed 38 --one-shot 35 \
    --attempts 1.2 --duration 312.5 \
    --pr-created 35 --pr-rejected 3

# Voir l'agrégation
python scripts/metrics_collector.py summary

# Exporter pour le writeup
python scripts/metrics_collector.py export --output metrics.md
```

Les métriques sont persistées en JSONL dans `data/metrics.jsonl` pour
permettre l'agrégation temporelle et la démonstration de la valeur produit
(taux One-Shot, MTTR, ratio de PR acceptées).

## Auteurs

- **BOUREDJI Amine** — CI/CD & QA (pipeline multi-langages, règles Semgrep métier,
  adapters SAST, métriques)
- **MANSOURI Othmane** — Validation E2E (intégration OWASP Juice Shop, scan
  réel, envoi à l'API_P)

Dans le cadre du projet SecPilot — Mission 25/26 (M1D).

## Licence

MIT License
