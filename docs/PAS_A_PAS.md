# Pas à pas : de zéro à ton premier résultat

## Le plus simple (Mac) : un double-clic, avec ton abonnement Claude Pro
1. Extrais le zip, installe Python 3.12 (python.org) si besoin.
2. Double-clique sur **`lancer-mac.command`**. Si macOS refuse (« développeur non identifié »), fais **clic droit, puis Ouvrir, puis Ouvrir**.
3. Laisse faire : installation, données, tests. À l'étape finale, appuie sur **Entrée** : le fichier utilise ton abonnement via Claude Code (il propose de l'installer avec la commande officielle d'Anthropic si besoin), puis ouvre une page web pour te connecter à ton compte Claude.
4. Il lance un essai de 3 questions, puis la mesure complète si tu tapes `1` (un passage, conseillé) ou `3`. Le rapport s'ouvre dans ton navigateur.

**À savoir sur l'abonnement**
- Le Pro ne donne pas de clé API, mais inclut Claude Code. Les limites d'usage sont **partagées** avec le chat Claude : une mesure complète (180 appels) peut atteindre la limite. Si c'est le cas, le passage est marqué « incomplet » ; relance le même fichier plus tard (après la réinitialisation de la limite) : il propose de **reprendre** et refait seulement les appels échoués.
- Claude Code choisit son modèle par défaut et la température n'est pas réglable : le rapport indique le modèle vu, et la méthodologie précise cette limite.
- Garde la variable `ANTHROPIC_API_KEY` non définie : sinon Claude Code facturerait l'API au lieu de l'abonnement (le projet la retire de lui-même).
- Le plan gratuit n'inclut pas Claude Code.
- Préfères-tu une clé API ? Tape **K** à l'étape finale et colle ta clé (créée sur console.anthropic.com, elle commence par `sk-ant-`).

Les étapes suivantes détaillent la méthode manuelle, par le Terminal.

## 1. Installer
Il te faut **Python 3.10 ou plus** (python.org) et **Git**.

**Windows (PowerShell)**
```powershell
cd analyste-ia-fiable
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```
**macOS / Linux**
```bash
cd analyste-ia-fiable
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
```

## 2. Construire les données et vérifier
```bash
python -m aia.cli generate
dbt build --project-dir dbt_project --profiles-dir dbt_project
python -m pytest -q
```
Attendu : 37 tests dbt réussis, 78 tests Python réussis. Rien n'est envoyé à une IA à cette étape.

## 3. Voir les pièges en action (sans IA)
```bash
python -m aia.cli naive
```

## 4. Obtenir une clé API
1. Crée un compte sur **console.anthropic.com**, ajoute un peu de crédit (quelques euros suffisent) et crée une clé dans « API keys ».
2. L'API se facture **séparément** de l'abonnement au chat Claude.
3. Ne mets jamais la clé dans un fichier du dépôt ni sur GitHub.

Définis-la dans ton terminal :
- Windows (PowerShell) : `$env:ANTHROPIC_API_KEY="sk-ant-..."`
- macOS / Linux : `export ANTHROPIC_API_KEY="sk-ant-..."`

## 5. Essai, puis mesure complète
```bash
python -m aia.cli eval --limit 3        # 3 questions : vérifie que tout marche
python -m aia.cli eval --runs 3         # mesure complète (3 passages)
```
Le rapport est écrit dans `results/run-AAAAMMJJ-HHMM/` : `rapport.md` (tableaux) et `rapport.html` (page à ouvrir dans le navigateur). Ouvre aussi quelques fiches « Question par question » pour comprendre **pourquoi** chaque condition échoue.

## 6. Publier
1. Crée un dépôt GitHub public, puis `git init`, `git add .`, `git commit`, `git push`. Le fichier `.gitignore` exclut déjà la base et les données générées.
2. Le `.gitignore` exclut `results/run-*/`. Pour publier un passage, copie son dossier sous un autre nom (par exemple `results/passage-1`).
3. Reporte les chiffres dans la section « Résultats » du README.
4. Envoie-moi `rapport.md` et je remplis la fiche projet de ton portfolio avec les vrais chiffres, et je peux publier la page de résultats.

## En cas de problème
- `ANTHROPIC_API_KEY n'est pas définie` : refais l'étape 4 dans le même terminal.
- Erreur de modèle : ajoute `--model <identifiant>` avec un modèle disponible sur ton compte.
- `warehouse.duckdb absent` : refais l'étape 2.
