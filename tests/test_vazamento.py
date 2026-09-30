"""Guarda contra vazamento de dados de cliente no repositório compartilhado.

Liste nomes proibidos (clientes, projetos, pessoas) em `.nomes-proibidos.txt` na raiz — um por linha.
Esse arquivo é ignorado pelo git (fica só na sua máquina). Sem ele, o teste é pulado.
"""
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
LISTA = RAIZ / ".nomes-proibidos.txt"
EXTENSOES_TEXTO = {".py", ".md", ".yaml", ".yml", ".j2", ".txt", ".csv", ".json", ".ps1", ".sh", ".toml", ".cfg"}


def _arquivos_do_repositorio():
    try:
        saida = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=RAIZ,
                               capture_output=True, text=True, check=True).stdout.splitlines()
        return [RAIZ / s for s in saida]
    except (OSError, subprocess.CalledProcessError):
        ignorar = {".git", ".venv", "__pycache__", ".pytest_cache"}
        return [p for p in RAIZ.rglob("*") if p.is_file() and not ignorar & set(p.parts)]


@pytest.mark.skipif(not LISTA.exists(), reason="sem .nomes-proibidos.txt local")
def test_nenhum_nome_proibido_nos_arquivos_versionados():
    nomes = [n.strip() for n in LISTA.read_text(encoding="utf-8").splitlines() if n.strip() and not n.startswith("#")]
    padrao = re.compile(r"(?<![\w-])(" + "|".join(re.escape(n) for n in nomes) + r")(?![\w-])", re.IGNORECASE)
    achados = []
    for arq in _arquivos_do_repositorio():
        if arq.suffix.lower() not in EXTENSOES_TEXTO or arq.name == LISTA.name or not arq.exists():
            continue
        for n, linha in enumerate(arq.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            m = padrao.search(linha)
            if m:
                achados.append(f"{arq.relative_to(RAIZ)}:{n}: '{m.group(1)}'")
    assert not achados, "Nomes proibidos encontrados:\n" + "\n".join(achados[:50])
