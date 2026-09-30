from rfpkit import util
from rfpkit.config import KB_DIR
from rfpkit.gates import REGRAS
from rfpkit.kb import KB


def test_kb_sem_erros_de_esquema():
    erros = [msg for nivel, msg in KB().validar() if nivel == "ERRO"]
    assert erros == []


def test_toda_ficha_cobre_as_categorias_de_produto():
    kb = KB()
    produto = {c["id"] for c in kb.categorias_produto}
    assert len(produto) == 15
    for fid, forn in kb.fornecedores.items():
        assert set(forn["notas_base"]) == produto, fid


def test_azure_monitor_sempre_disponivel_na_kb():
    assert "azure-monitor" in KB().fornecedores


def test_biblioteca_de_gates_documenta_todas_as_regras():
    doc = util.ler_yaml(KB_DIR / "gates-biblioteca.yaml")
    assert set(doc["regras"]) == set(REGRAS)


def test_gartner_ids_sem_quadrante_duplicado():
    kb = KB()
    for edicao in kb.gartner["edicoes"]:
        vistos = [i for ids in edicao["quadrantes"].values() for i in (ids or [])]
        assert len(vistos) == len(set(vistos)), edicao["ano"]


def test_cases_e_arquiteturas_publicos_na_kb():
    kb = KB()
    ref = kb.referencia("REF-AZ-002")
    assert ref["tipo"] == "case" and ref["fornecedor"] == "azure-monitor" and ref["url"].startswith("https://")
    assert {r["tipo"] for r in kb.referencia_por_id.values()} == {"case", "arquitetura"}
    assert not any("relacao" in r for r in kb.referencia_por_id.values())   # relação com cliente fica no estudo


def test_evidencias_com_alegacao_tem_citacoes_em_lista():
    kb = KB()
    for ev in kb.evidencia_por_id.values():
        if ev.get("alegacao"):
            assert isinstance(ev.get("citacoes"), list) and ev["citacoes"], ev["id"]
