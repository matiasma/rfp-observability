"""Evidências do estudo: dossiês por fornecedor (retrato da KB), Gartner, registro de alegações, biblioteca de
evidências do proponente, pente-fino automático e cases/arquiteturas de referência (KB + relação com o edital)."""
import json

import pytest
from docx import Document

import kit
from rfpkit import evidencias, respostas
from rfpkit.config import Projeto
from rfpkit.kb import KB


def _evid(pasta):
    return pasta / "_analise-rfp" / "00-projeto" / "evidencias"


def _registro(pasta, texto):
    (pasta / "_analise-rfp" / "02-analise" / "registro-evidencias.yaml").write_text(texto, encoding="utf-8")


def test_dossies_do_estudo_neutro(cliente_exemplo):
    assert kit.main(["tudo", str(cliente_exemplo)]) == 0
    pasta = _evid(cliente_exemplo)
    nomes = {p.name for p in pasta.iterdir()}
    assert {"indice.md", "gartner-mq.md", "registro-evidencias.md", "dossie-azure-monitor.md",
            "dossie-datadog.md"} <= nomes
    assert not any(n.startswith("biblioteca-") for n in nomes)            # só no modo proponente

    gartner = (pasta / "gartner-mq.md").read_text(encoding="utf-8")
    assert "| Azure Monitor | obrigatório | Desafiante |" in gartner
    assert "## Gate G1" in gartner and "mudou de nome" in gartner

    azure = (pasta / "dossie-azure-monitor.md").read_text(encoding="utf-8")
    assert "| G2 |" in azure and "INDEFINIDO" in azure
    assert "## Fatos da KB" in azure and "| integracoes_nativas | — | AUSENTE |" in azure
    assert "## Notas por categoria (peso do edital)" in azure
    assert "## Biblioteca de evidências" in azure and "EV-AZ-044" in azure
    assert "## Cases e arquiteturas de referência" in azure and "REF-AZ-002" in azure
    assert "EV-0002" in azure                                              # alegação do registro com fornecedor

    indice = (pasta / "indice.md").read_text(encoding="utf-8")
    assert "[dossie-datadog.md](dossie-datadog.md)" in indice and "alegações no registro: 2" in indice


def test_dossies_e_pente_fino_proponente(cliente_proponente, rede_falsa):
    assert kit.main(["tudo", str(cliente_proponente), "--urls"]) == 0
    pasta = _evid(cliente_proponente)
    biblioteca = (pasta / "biblioteca-azure-monitor.md").read_text(encoding="utf-8")
    assert "| EV-AZ-045 |" in biblioteca and "RF-04" in biblioteca
    assert "Visual Studio App Center is scheduled for retirement" in biblioteca       # citações literais
    registro = (pasta / "registro-evidencias.md").read_text(encoding="utf-8")
    assert "EV-0003" in registro and "edital: Matriz-Requisitos-Exemplo.xlsx" in registro
    assert "| OK |" in registro                                            # checagem da URL herdada da KB

    analise = cliente_proponente / "_analise-rfp" / "02-analise"
    pf = json.loads((analise / "pente-fino-automatico.json").read_text(encoding="utf-8"))
    assert pf["resumo"]["total_itens"] == 15
    sinais = {i["id"]: i["flags"] for i in pf["itens_sinalizados"]}
    assert "url_generica" in sinais["RF-07"]                               # .../copilot/overview
    assert "RF-04" not in sinais                                           # página específica não é genérica

    memorial = Document(str(cliente_proponente / "_analise-rfp" / "03-entregas" /
                            "Memorial-Tecnico-Azure-Monitor-exemplo-prop.docx"))
    titulos = [p.text for p in memorial.paragraphs if p.style.name.startswith("Heading")]
    assert {"6.1 Casos de clientes (publicados)", "6.2 Arquiteturas de referência oficiais"} <= set(titulos)
    texto = "\n".join(c.text for t in memorial.tables for row in t.rows for c in row.cells)
    assert "Idever" in texto and "Picos sazonais de demanda" in texto


def test_registro_invalido(cliente_exemplo):
    _registro(cliente_exemplo, """
- id: EV-0001
  alegacao: "a"
  fonte: "https://exemplo.com/doc"
  data_acesso: 2020-01-01
  confianca: talvez
- id: EV-0001
  alegacao: "b"
  fonte: "edital: TR item 1"
- id: EV-0002
  kb: EV-XX-999
- id: EV-0003
  alegacao: "sem fonte"
""")
    msgs = evidencias.validar_registro(Projeto(cliente_exemplo), KB())
    texto = "\n".join(f"{n} {m}" for n, m in msgs)
    assert "ERRO EV-0001: id repetido" in texto
    assert "ERRO EV-0002: evidência EV-XX-999 não existe" in texto
    assert "ERRO EV-0003: sem 'fonte'" in texto
    assert "AVISO EV-0001: sem citação literal" in texto
    assert "AVISO EV-0001: fonte acessada em 2020-01-01" in texto
    assert "AVISO EV-0001: confiança 'talvez'" in texto


def test_registro_herda_da_kb(cliente_exemplo):
    _registro(cliente_exemplo, "- id: EV-0001\n  kb: EV-AZ-045\n  confianca: alta\n")
    item = evidencias.carregar_registro(Projeto(cliente_exemplo), KB())[0]
    assert item["fonte"] == "https://learn.microsoft.com/en-us/appcenter/retirement"
    assert item["fornecedor"] == "azure-monitor" and item["citacoes"] and item["alegacao"]
    assert evidencias.validar_registro(Projeto(cliente_exemplo), KB()) == []


def test_case_da_kb_resolvido_e_inexistente(cliente_proponente):
    caminho = cliente_proponente / "_analise-rfp" / "02-analise" / "cases-referencia.yaml"
    caminho.write_text('- kb: REF-AZ-002\n  relacao: "par de setor"\n- kb: REF-XX-999\n', encoding="utf-8")
    proj = Projeto(cliente_proponente)
    refs = evidencias.referencias_do_estudo(proj, KB())
    assert refs[0]["organizacao"] == "Idever" and refs[0]["relacao"] == "par de setor" and refs[0]["url"]
    assert any(n == "ERRO" and "REF-XX-999" in m for n, m in evidencias.validar_referencias(proj, KB()))


@pytest.mark.parametrize("url,generica", [
    ("https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/overview", True),
    ("https://azure.microsoft.com/en-us/products/monitor", True),
    ("https://docs.datadoghq.com/integrations/", True),
    ("https://learn.microsoft.com/en-us/appcenter/retirement", False),
    ("https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-overview", False),
])
def test_url_generica(url, generica):
    assert respostas.url_generica(url) is generica


def test_pente_fino_reuso_de_url_e_justificativa_curta(cliente_proponente):
    proj = Projeto(cliente_proponente)
    proj.cfg["respostas"]["pente_fino"] = {"reuso_url": 2, "justificativa_min": 10}
    pf = respostas.pente_fino(proj, KB())
    sinais = {i["id"]: i["flags"] for i in pf["itens_sinalizados"]}
    assert "reuso_url=2" in sinais["RF-02"] and "reuso_url=2" in sinais["RF-05"]   # EV-AZ-001 em dois itens
    assert pf["resumo"].get("justificativa_curta", 0) == 0
    assert pf["top_urls_reuso"][0][1] == 2

    proj.cfg["respostas"]["pente_fino"] = {"reuso_url": 5, "justificativa_min": 150}
    pf = respostas.pente_fino(proj, KB())
    curtas = {i["id"] for i in pf["itens_sinalizados"] if "justificativa_curta" in i["flags"]}
    assert "RF-11" in curtas and "RF-04" not in curtas                     # negativa não entra na regra


def test_tudo_sem_init_da_mensagem_e_nao_traceback(tmp_path, capsys):
    assert kit.main(["tudo", str(tmp_path / "sem-init")]) == 2
    assert "Rode primeiro: python kit.py init" in capsys.readouterr().out


def test_registro_e_cases_malformados_viram_erro_de_validacao(cliente_proponente):
    analise = cliente_proponente / "_analise-rfp" / "02-analise"
    (analise / "registro-evidencias.yaml").write_text(
        "- kb: EV-AZ-045\n- EV-AZ-046\n- id: EV-0009\n  alegacao: x\n  fonte: https://learn.microsoft.com/x\n"
        "  data_acesso: 29/09/2026\n  citacoes: \"trecho\"\n", encoding="utf-8")
    (analise / "cases-referencia.yaml").write_text(
        "- REF-AZ-002\n- organizacao: Sem esquema\n  url: customers.microsoft.com/story/1\n"
        "  resultados: \"resultado único\"\n", encoding="utf-8")
    assert kit.main(["tudo", str(cliente_proponente)]) == 1              # ERRO de validação, sem traceback
    validacao = (analise / "validacao.md").read_text(encoding="utf-8")
    for trecho in ("alegação sem id", "não é uma alegação", "data_acesso data '29/09/2026' inválida",
                   "'citacoes' deve ser lista", "não é um case", "sem URL pública válida"):
        assert trecho in validacao, trecho
    assert (cliente_proponente / "_analise-rfp" / "00-projeto" / "evidencias" / "indice.md").exists()
    from rfpkit import urls
    proj = Projeto(cliente_proponente)
    assert urls.alvos_do_estudo(proj, KB())                                # ignora itens malformados
    assert evidencias.referencias_do_estudo(proj, KB())[0]["resultados"] == ["resultado único"]


def test_url_sem_esquema_nao_derruba_a_verificacao():
    from rfpkit import urls
    r = urls.verificar_varias({"www.exemplo.com/pagina": {"palavras": [], "usos": ["RF-01"]}})[0]
    assert r["situacao"] == "QUEBRADA" and r["erro"] == "ValueError"
