import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "exemplos" / "cliente-exemplo"))

ENTRADAS_ANALISE = ("rfp.yaml", "02-analise/narrativa.md", "02-analise/eixos.yaml", "02-analise/ajustes-notas.yaml",
                    "02-analise/gates-override.yaml", "02-analise/classificacao-manual.csv",
                    "02-analise/registro-evidencias.yaml", "02-analise/duvidas.yaml")
ENTRADAS_PROPONENTE = ENTRADAS_ANALISE + ("02-analise/respostas.json", "02-analise/cases-referencia.yaml",
                                          "02-analise/esforco-poc.yaml", "02-analise/custo.yaml",
                                          "02-analise/revisao-requisitos.json")


def _copiar_exemplo(nome: str, destino: Path, entradas) -> Path:
    import gerar_exemplo

    gerar_exemplo.gerar(destino)
    origem = RAIZ / "exemplos" / nome / "_analise-rfp"
    for rel in entradas:
        alvo = destino / "_analise-rfp" / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem / rel, alvo)
    return destino


@pytest.fixture
def cliente_exemplo(tmp_path) -> Path:
    """Cópia isolada do cliente fictício (modo neutro): documentos gerados + entradas de análise versionadas."""
    return _copiar_exemplo("cliente-exemplo", tmp_path / "cliente-exemplo", ENTRADAS_ANALISE)


@pytest.fixture
def cliente_proponente(tmp_path) -> Path:
    """Cópia isolada do cliente fictício no modo proponente (respostas e dúvidas preenchidas)."""
    return _copiar_exemplo("cliente-exemplo-proponente", tmp_path / "cliente-proponente", ENTRADAS_PROPONENTE)


class _Rede:
    """URLs simuladas: 'add(url)' marca a URL como quebrada (404); 'texto_mudou' guarda as URLs cuja página não tem
    mais as citações literais."""

    def __init__(self):
        self.quebradas, self.texto_mudou = set(), set()

    def add(self, url):
        self.quebradas.add(url)


@pytest.fixture
def rede_falsa(monkeypatch):
    """Substitui o HTTP real: toda URL responde 200 com todas as palavras-chave e citações literais da KB e dos
    registros dos exemplos, exceto as quebradas (404) e as de 'texto_mudou' (página sem as citações)."""
    import html as html_lib

    from rfpkit import urls, util
    from rfpkit.kb import KB

    kb = KB()
    itens = list(kb.evidencia_por_id.values()) + list(kb.referencia_por_id.values())
    palavras = " ".join(p for ev in itens for p in ev.get("palavras_chave") or []) + " data collection methods"
    citacoes = [c for ev in kb.evidencia_por_id.values() for c in urls.citacoes_da_evidencia(ev)]
    for reg in RAIZ.glob("exemplos/*/_analise-rfp/02-analise/registro-evidencias.yaml"):
        for e in util.ler_yaml(reg, []) or []:
            citacoes += [c for c in (e.get("citacoes") or []) if isinstance(c, str)]
    corpo = html_lib.escape(" ".join(citacoes))
    rede = _Rede()

    def buscar(url, timeout=25):
        if url in rede.quebradas:
            return {"status": 404, "final": url, "html": "", "erro": "HTTP 404"}
        extra = "" if url in rede.texto_mudou else corpo
        return {"status": 200, "final": url, "html": f"<title>ok</title><p>{palavras}</p><p>{extra}</p>", "erro": ""}

    monkeypatch.setattr(urls, "buscar", buscar)
    return rede
