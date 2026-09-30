#!/usr/bin/env bash
# Instala a skill "analise-rfp-observabilidade" para uso pessoal no GitHub Copilot.
# Uso: scripts/instalar-skill.sh [destino]
set -euo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${1:-$HOME/.copilot/skills/analise-rfp-observabilidade}"

mkdir -p "$DESTINO"
cp -R "$KIT/.github/skills/analise-rfp-observabilidade/." "$DESTINO/"

echo "Skill instalada em: $DESTINO"
echo "Adicione ao seu shell (~/.bashrc ou ~/.zshrc):  export RFP_KIT_HOME=\"$KIT\""
echo "Dependências: python3 -m pip install -r \"$KIT/requirements.txt\""
