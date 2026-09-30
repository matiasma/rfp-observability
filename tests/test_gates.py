import datetime as dt

import pytest

from rfpkit import util
from rfpkit.gates import REGRAS, Contexto
from rfpkit.kb import KB

DATA = dt.date(2026, 9, 29)


@pytest.fixture
def kb(tmp_path):
    """KB mínima e isolada para testar as regras sem depender do conteúdo real."""
    (tmp_path / "fornecedores").mkdir()
    util.gravar_yaml(tmp_path / "taxonomia.yaml", {"categorias": []})
    util.gravar_yaml(tmp_path / "gartner-mq.yaml", {"edicoes": [
        {"ano": 2024, "data_publicacao": "2024-08-12", "titulo": "Magic Quadrant for Observability Platforms",
         "quadrantes": {"lider": ["alfa", "beta"], "desafiante": ["gama"]}},
        {"ano": 2025, "data_publicacao": "2025-07-07", "titulo": "Magic Quadrant for Observability Platforms",
         "quadrantes": {"lider": ["alfa", "beta"], "desafiante": ["gama"]}},
        {"ano": 2026, "data_publicacao": "2026-07-13", "titulo": "Magic Quadrant for Observability Platforms",
         "quadrantes": {"lider": ["alfa"], "desafiante": ["beta", "gama"]}},
        {"ano": 2027, "data_publicacao": "2027-07-10", "titulo": "Magic Quadrant for Observability Platforms",
         "quadrantes": {"lider": ["gama"]}},
    ]})

    def fato(valor, verificado="2026-09-01", **extra):
        return {"valor": valor, "fonte": "https://exemplo", "verificado_em": verificado, **extra}

    util.gravar_yaml(tmp_path / "fornecedores" / "alfa.yaml", {"id": "alfa", "nome": "Alfa", "ttl_dias": 180, "fatos": {
        "integracoes_nativas": fato(1000, qualificador="mais de"),
        "sla_disponibilidade_pct": fato(99.8),
        "suporte_ptbr": fato("NAO_DOCUMENTADO"),
        "retencao_metricas_meses": fato(15),
        "retencao_metricas_integral": fato("PARCIAL"),
        "so_suportados": fato(["linux", "windows"]),
        "certificacoes": fato(["SOC2 Type II", "ISO 27001", "PCI DSS"]),
    }, "notas_base": {}})
    util.gravar_yaml(tmp_path / "fornecedores" / "beta.yaml", {"id": "beta", "nome": "Beta", "ttl_dias": 180, "fatos": {
        "integracoes_nativas": fato(1000),
        "sla_disponibilidade_pct": fato(99.5, verificado="2025-01-01"),
        "suporte_ptbr": fato("SIM"),
    }, "notas_base": {}})
    return KB(tmp_path)


def avaliar(kb, regra, fid, **params):
    return REGRAS[regra](Contexto(kb, DATA), fid, params)[:2]


def test_gartner_ultimos_3_anos_ignora_edicao_futura(kb):
    assert avaliar(kb, "gartner_lider", "alfa", anos=3)[0] == "PASSA"
    veredito, just = avaliar(kb, "gartner_lider", "beta", anos=3)
    assert veredito == "NAO" and "2026: Desafiante" in just
    assert avaliar(kb, "gartner_lider", "gama", anos=3)[0] == "NAO"


def test_gartner_nao_consecutivo(kb):
    assert avaliar(kb, "gartner_lider", "beta", anos=2, consecutivos=False)[0] == "PASSA"


def test_gartner_sinaliza_nome_antigo_do_mq(kb):
    _, just = avaliar(kb, "gartner_lider", "alfa", anos=3, _clausula="Líder no MQ de APM and Observability")
    assert "nome antigo" in just


def test_integracoes_estrito_aceita_mais_de_n(kb):
    assert avaliar(kb, "integracoes_min", "alfa", min=1000, estrito=True)[0] == "PASSA"
    assert avaliar(kb, "integracoes_min", "beta", min=1000, estrito=True)[0] == "NAO"
    assert avaliar(kb, "integracoes_min", "beta", min=1000, estrito=False)[0] == "PASSA"


def test_fato_vencido_fica_indefinido(kb):
    veredito, just = avaliar(kb, "sla_min", "beta", pct=99.0)
    assert veredito == "INDEFINIDO" and "vencido" in just


def test_fato_ausente_fica_indefinido(kb):
    assert avaliar(kb, "opentelemetry", "alfa")[0] == "INDEFINIDO"
    assert avaliar(kb, "sla_min", "inexistente", pct=99.0)[0] == "INDEFINIDO"


def test_enum_nao_documentado_vira_risco(kb):
    assert avaliar(kb, "suporte_ptbr", "alfa")[0] == "RISCO"
    assert avaliar(kb, "suporte_ptbr", "beta")[0] == "PASSA"


def test_retencao_integral(kb):
    assert avaliar(kb, "retencao_metricas_min", "alfa", meses=13)[0] == "PASSA"
    assert avaliar(kb, "retencao_metricas_min", "alfa", meses=15, integral=True)[0] == "RISCO"
    assert avaliar(kb, "retencao_metricas_min", "alfa", meses=24)[0] == "NAO"


def test_so_suportados(kb):
    veredito, just = avaliar(kb, "so_suportados", "alfa", so=["linux", "aix"])
    assert veredito == "NAO" and "aix" in just


def test_certificacoes_normaliza_grafia(kb):
    assert avaliar(kb, "certificacoes", "alfa", lista=["SOC2", "ISO27001", "PCI-DSS"])[0] == "PASSA"
    assert avaliar(kb, "certificacoes", "alfa", lista=["FedRAMP"])[0] == "NAO"


def test_regra_generica(kb):
    assert avaliar(kb, "fato", "alfa", fato="sla_disponibilidade_pct", operador=">=", valor=99.8)[0] == "PASSA"


def test_kb_status_nao_lista_fatos_sem_evidencia_por_padrao(kb):
    # fatos ausentes só importam quando um edital depende deles (o estudo acusa o gate INDEFINIDO)
    padrao = kb.status(DATA)
    assert all(l["status"] != "AUSENTE" for l in padrao)
    assert any(l["status"] == "VENCIDO" and l["fornecedor"] == "beta" for l in padrao)
    assert any(l["status"] == "AUSENTE" for l in kb.status(DATA, incluir_ausentes=True))
