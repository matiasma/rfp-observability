"""Modo proponente: pacote completo de submissão (planilha oficial respondida, anexo de dúvidas, memorial e sumário,
validação de URLs) e verificações de qualidade das respostas."""
import json

from docx import Document
from openpyxl import load_workbook

import kit


def _analise(pasta):
    return pasta / "_analise-rfp"


def _validacao(pasta) -> str:
    return (_analise(pasta) / "02-analise" / "validacao.md").read_text(encoding="utf-8")


def _editar_respostas(pasta, alteracoes: dict):
    caminho = _analise(pasta) / "02-analise" / "respostas.json"
    respostas = json.loads(caminho.read_text(encoding="utf-8"))
    for r in respostas:
        if r["id"] in alteracoes:
            r.update(alteracoes[r["id"]])
    caminho.write_text(json.dumps(respostas, ensure_ascii=False), encoding="utf-8")


def test_pacote_completo_de_submissao(cliente_proponente, rede_falsa):
    assert kit.main(["tudo", str(cliente_proponente), "--urls"]) == 0
    entregas = _analise(cliente_proponente) / "03-entregas"
    nomes = {p.name for p in entregas.iterdir()}
    assert {"Matriz-Requisitos-Exemplo - RESPONDIDA Azure Monitor.xlsx", "matriz-respostas-exemplo-prop.xlsx",
            "duvidas-exemplo-prop.xlsx", "Anexo-Duvidas-Exemplo - PREENCHIDO.xlsx",
            "Sumario-Executivo-exemplo-prop.docx", "Memorial-Tecnico-Azure-Monitor-exemplo-prop.docx",
            "relatorio-exemplo-prop.html"} <= nomes
    assert "| ERRO |" not in _validacao(cliente_proponente)

    ws = load_workbook(entregas / "Matriz-Requisitos-Exemplo - RESPONDIDA Azure Monitor.xlsx")["Requisitos Funcionais"]
    assert ws["F4"].value.endswith("Ref.: https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-map")
    assert "[Método: Configuração.] [Comprovação em POC.]" in ws["F15"].value

    duvidas = load_workbook(entregas / "Anexo-Duvidas-Exemplo - PREENCHIDO.xlsx")["Dúvidas"]
    assert duvidas["A3"].value == "DUV-001" and duvidas["E3"].value.startswith("Para o RF-04")
    assert duvidas["G3"].value == "PENDENTE"                               # coluna do cliente intocada

    memorial = Document(str(entregas / "Memorial-Tecnico-Azure-Monitor-exemplo-prop.docx"))
    titulos = [p.text for p in memorial.paragraphs if p.style.name.startswith("Heading")]
    assert {"5. Respostas por requisito", "Anexo A — Evidências oficiais", "4. Arquitetura da solução"} <= set(titulos)
    texto = "\n".join(c.text for t in memorial.tables for row in t.rows for c in row.cells)
    assert "EV-AZ-002" in texto and "https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-map" in texto

    html = (entregas / "relatorio-exemplo-prop.html").read_text(encoding="utf-8")
    assert "Aderência do Azure Monitor — respostas ao edital" in html and "⟨?⟩" not in html
    csv_urls = (_analise(cliente_proponente) / "02-analise" / "validacao-urls.csv").read_text(encoding="utf-8-sig")
    assert "app-map" in csv_urls


def test_url_quebrada_vira_erro(cliente_proponente, rede_falsa):
    rede_falsa.add("https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-map")
    assert kit.main(["tudo", str(cliente_proponente), "--urls"]) == 1
    assert "URL inacessível (404)" in _validacao(cliente_proponente)


def test_pente_fino_automatico(cliente_proponente):
    _editar_respostas(cliente_proponente, {
        "RF-01": {"evidencias": ["EV-AZ-999"]},
        "RF-02": {"justificativa": "Solução líder de mercado, melhor do mercado em correlação."},
        "RF-03": {"resposta": "Sim"},
        "RF-08": {"evidencias": []},
    })
    assert kit.main(["tudo", str(cliente_proponente)]) == 1
    v = _validacao(cliente_proponente)
    assert "EV-AZ-999 não existe" in v                                     # ERRO
    assert "fora da escala" in v                                           # ERRO
    assert "linguagem de marketing" in v                                   # AVISO
    assert "RF-08: 'Atende Plenamente' sem evidência" in v                 # AVISO


def test_duvidas_com_numeracao_nao_contigua(cliente_proponente):
    caminho = _analise(cliente_proponente) / "02-analise" / "duvidas.yaml"
    caminho.write_text(caminho.read_text(encoding="utf-8").replace("DUV-002", "DUV-007"), encoding="utf-8")
    assert kit.main(["tudo", str(cliente_proponente)]) == 0
    assert "numeração não contígua" in _validacao(cliente_proponente)


def test_modo_neutro_gera_sumario_sem_memorial(cliente_exemplo):
    assert kit.main(["tudo", str(cliente_exemplo)]) == 0
    entregas = _analise(cliente_exemplo) / "03-entregas"
    assert (entregas / "Sumario-Executivo-exemplo.docx").exists()
    assert not list(entregas.glob("Memorial-*.docx"))
    sumario = Document(str(entregas / "Sumario-Executivo-exemplo.docx"))
    assert "Scorecard" in [p.text for p in sumario.paragraphs if p.style.name.startswith("Heading")]
