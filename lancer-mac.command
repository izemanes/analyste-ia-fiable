#!/bin/bash
# Double-clique sur ce fichier : il installe, vérifie, puis lance l'évaluation.
cd "$(dirname "$0")" || exit 1
set -o pipefail

fail() { echo; echo "PROBLÈME : $1"; echo "Copie ce message et envoie-le à Claude."; read -r -p "Appuie sur Entrée pour fermer." _ ; exit 1; }

echo "=== Analyste IA fiable ==="
PY=""; WANT=""
for c in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys;print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
    case "$v" in 3.10|3.11|3.12|3.13) PY="$c"; WANT="$v"; break ;; esac
  fi
done
[ -n "$PY" ] || fail "Aucun Python compatible (3.10 à 3.13) trouvé. Installe Python 3.12 depuis python.org, puis relance ce fichier."
echo "Python utilisé : $($PY --version)"

echo; echo "[1/5] Préparation de l'environnement (la première fois, compte quelques minutes)..."
# On refait l'environnement s'il vient d'une autre version de Python ou d'une installation interrompue.
if [ -d .venv ] && [ "$(cat .venv/.install_ok 2>/dev/null)" != "$WANT" ]; then
  echo "Ancien environnement détecté : je le refais proprement."
  rm -rf .venv
fi
[ -d .venv ] || "$PY" -m venv .venv || fail "Impossible de créer l'environnement Python."
source .venv/bin/activate || fail "Impossible d'activer l'environnement."
pip install -q -r requirements.txt && pip install -q -e . || fail "L'installation des outils a échoué (connexion internet ?)."
echo "$WANT" > .venv/.install_ok

echo; echo "[2/5] Génération des données fictives..."
python -m aia.cli generate || fail "La génération des données a échoué."

echo; echo "[3/5] Construction et tests des modèles dbt..."
dbt build --project-dir dbt_project --profiles-dir dbt_project | tail -3 || fail "dbt a échoué."

echo; echo "[4/5] Vérification du projet (aucune IA utilisée, c'est gratuit)..."
python -m pytest -q || fail "Les tests ont échoué."
echo; echo "✅ Tout fonctionne chez toi."

echo; echo "[5/5] Mesure sur une vraie IA"
export PATH="$HOME/.local/bin:$PATH"
PROVIDER=""
if [ -n "$ANTHROPIC_API_KEY" ]; then
  PROVIDER="api"
  echo "Clé API détectée : elle sera utilisée (facturation API)."
else
  echo "Cette étape utilise ton abonnement Claude (Pro ou Max), sans clé API."
  read -r -p "Appuie sur Entrée pour continuer (ou tape K si tu préfères une clé API) : " CH
  if [ "$CH" = "K" ] || [ "$CH" = "k" ]; then
    read -r -s -p "Colle ta clé API ici (elle commence par sk-ant-) : " KEY; echo
    if [ -n "$KEY" ]; then export ANTHROPIC_API_KEY="$KEY"; PROVIDER="api"; fi
  else
    if ! command -v claude >/dev/null 2>&1; then
      echo "Claude Code (inclus dans ton abonnement) n'est pas installé sur ce Mac."
      read -r -p "L'installer maintenant, avec la méthode officielle d'Anthropic ? [O/n] " I
      if [ "$I" = "n" ] || [ "$I" = "N" ]; then
        echo "D'accord. Relance ce fichier quand Claude Code sera installé."
        read -r -p "Appuie sur Entrée pour fermer." _ ; exit 0
      fi
      curl -fsSL https://claude.ai/install.sh | bash || fail "L'installation de Claude Code a échoué."
      export PATH="$HOME/.local/bin:$PATH"
    fi
    command -v claude >/dev/null 2>&1 || fail "Claude Code est introuvable après l'installation. Ferme et rouvre le Terminal, puis relance ce fichier."
    if ! claude auth status 2>/dev/null | grep -q '"loggedIn": true'; then
      echo "Connexion à ton compte Claude : une page web va s'ouvrir, connecte-toi avec le compte qui a l'abonnement Pro."
      claude auth login || fail "La connexion à ton compte Claude a échoué."
    fi
    PROVIDER="claude-code"
  fi
fi
[ -n "$PROVIDER" ] || { echo "Rien n'est lancé. Relance ce fichier quand tu seras prêt."; read -r -p "Appuie sur Entrée pour fermer." _ ; exit 0; }
EOPT=()
if [ "$PROVIDER" = "claude-code" ]; then EOPT=(--provider claude-code --workers 2); fi

# Un passage précédent interrompu (limite d'usage atteinte) ? On propose de le reprendre sans tout refaire.
LASTMETA=$(ls -t results/run-*/meta.json 2>/dev/null | head -1)
if [ -n "$LASTMETA" ] && python -c "import json,sys; sys.exit(0 if json.load(open('$LASTMETA')).get('api_errors',0) > 0 else 1)"; then
  echo; echo "Un passage précédent est resté incomplet ($(dirname "$LASTMETA"))."
  read -r -p "Le reprendre (seuls les appels échoués sont refaits) ? [O/n] " RS
  if [ "$RS" != "n" ] && [ "$RS" != "N" ]; then
    python -m aia.cli eval --resume "${EOPT[@]}"
    RC=$?
    LAST=$(dirname "$LASTMETA")
    [ -f "$LAST/rapport.html" ] && open "$LAST/rapport.html"
    if [ "$RC" = "2" ]; then echo; echo "Encore incomplet : attends la réinitialisation de ta limite (quelques heures) puis relance ce fichier."; fi
    read -r -p "Terminé. Appuie sur Entrée pour fermer." _ ; exit 0
  fi
fi

echo; echo "Essai sur 3 questions..."
python -m aia.cli eval --limit 3 "${EOPT[@]}" || fail "L'essai a échoué (connexion à Claude, limite d'usage ou clé invalide)."
read -r -p "L'essai a marché. Lancer la mesure complète (60 questions × 3 conditions) ? [1 = un passage conseillé, 3 = trois passages, Entrée = rien] " R
case "$R" in
  1|3)
    python -m aia.cli eval --runs "$R" "${EOPT[@]}"
    RC=$?
    if [ "$RC" = "2" ]; then
      echo; echo "Passage incomplet (limite d'usage atteinte ?). Relance ce fichier plus tard : il proposera de reprendre là où ça s'est arrêté."
    elif [ "$RC" != "0" ]; then
      fail "La mesure complète a échoué."
    fi ;;
esac

LAST=$(ls -td results/run-* 2>/dev/null | head -1)
[ -n "$LAST" ] && [ -f "$LAST/rapport.html" ] && open "$LAST/rapport.html"
echo; echo "Rapport dans : $LAST"
read -r -p "Terminé. Appuie sur Entrée pour fermer." _
