"""Gravação cirúrgica da planilha do cliente e leitura de dropdowns (inclusive a extensão x14 do Excel 2010+)."""
import json
import zipfile

import pytest
from lxml import etree
from openpyxl import Workbook, load_workbook

import kit
from rfpkit import planilhas
from rfpkit.respostas import nivel

NS = planilhas.NS
X14_URI = "{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}"


def _planilha_x14(caminho, mesclar=False):
    """Matriz com dropdown cuja lista está em OUTRA aba, gravado como o Excel 2010+ grava (extLst/x14), uma parte
    EMF extra no pacote (que o openpyxl descartaria) e, opcionalmente, a coluna de resposta mesclada."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Requisitos"
    ws.append(["ID", "Requisito", "Autoavaliação", "Observações"])
    ws.append(["R-1", "Monitorar filas de mensageria.", "", ""])
    ws.append(["R-2", "Monitorar jobs agendados de integração.", "", ""])
    ws.append(["R-3", "Monitorar certificados digitais a vencer.", "", ""])
    if mesclar:
        ws.merge_cells("C3:C4")
    listas = wb.create_sheet("Listas D'Água")
    for i, v in enumerate(["Não Atende", "Atende Parcialmente", "Atende Totalmente"], start=1):
        listas.cell(row=i, column=1, value=v)
    wb.save(caminho)
    with zipfile.ZipFile(caminho) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    parte = "xl/worksheets/sheet1.xml"
    raiz = etree.fromstring(partes[parte])
    ext_lst = etree.SubElement(raiz, f"{{{NS}}}extLst")
    ext = etree.SubElement(ext_lst, f"{{{NS}}}ext", uri=X14_URI, nsmap={"x14": planilhas.NS_X14})
    dvs = etree.SubElement(ext, f"{{{planilhas.NS_X14}}}dataValidations", count="1", nsmap={"xm": planilhas.NS_XM})
    dv = etree.SubElement(dvs, f"{{{planilhas.NS_X14}}}dataValidation", type="list", allowBlank="1")
    etree.SubElement(etree.SubElement(dv, f"{{{planilhas.NS_X14}}}formula1"), f"{{{planilhas.NS_XM}}}f").text = \
        "'Listas D''Água'!$A$1:$A$3"
    etree.SubElement(dv, f"{{{planilhas.NS_XM}}}sqref").text = "C2:C3"
    partes[parte] = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
    partes["xl/media/logo-legado.emf"] = b"EMF-FICTICIO" * 50
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in partes.items():
            z.writestr(nome, dados)
    return caminho


def _cliente(tmp_path, mesclar=False):
    pasta = tmp_path / "cliente"
    pasta.mkdir()
    _planilha_x14(pasta / "matriz.xlsx", mesclar)
    assert kit.main(["init", str(pasta), "--modo", "proponente", "--proponente", "azure-monitor", "--nao-assistida"]) == 0
    assert kit.main(["rtm", str(pasta)]) == 0
    assert kit.main(["respostas", str(pasta)]) == 0
    return pasta


def _responder(pasta, respostas: dict):
    caminho = pasta / "_analise-rfp" / "02-analise" / "respostas.json"
    itens = json.loads(caminho.read_text(encoding="utf-8"))
    for r in itens:
        if r["id"] in respostas:
            r.update(respostas[r["id"]])
    caminho.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    return itens


def test_dropdown_x14_de_outra_aba_e_pacote_preservado(tmp_path):
    pasta = _cliente(tmp_path)
    itens = _responder(pasta, {
        "R-1": {"resposta": "atende totalmente", "justificativa": "Filas monitoradas."},
        "R-3": {"resposta": "Não Atende", "justificativa": "Sem suporte nativo."},   # linha 4: fora do dropdown original
    })
    assert itens[0]["escala"] == ["Não Atende", "Atende Parcialmente", "Atende Totalmente"]
    assert kit.main(["respostas", str(pasta)]) == 0
    copia = pasta / "_analise-rfp" / "03-entregas" / "matriz - RESPONDIDA Azure Monitor.xlsx"
    ws = load_workbook(copia)["Requisitos"]
    assert ws["C2"].value == "Atende Totalmente" and ws["C4"].value == "Não Atende"
    dvs = planilhas.validacoes(copia)["Requisitos"]
    assert dvs and dvs[0]["x14"] and planilhas._cobre(dvs[0]["sqref"], "C4")       # x14 mantido e estendido
    assert planilhas.comparar_pacotes(pasta / "matriz.xlsx", copia, ["xl/worksheets/sheet1.xml"]) == []
    with zipfile.ZipFile(copia) as z:
        assert z.read("xl/media/logo-legado.emf") == b"EMF-FICTICIO" * 50
    verificacao = (pasta / "_analise-rfp" / "02-analise" / "verificacao-planilhas.md").read_text(encoding="utf-8")
    assert "divergentes: 0" in verificacao and "valor fora da lista: 0" in verificacao


def test_coluna_de_resposta_mesclada_nao_quebra(tmp_path):
    pasta = _cliente(tmp_path, mesclar=True)
    _responder(pasta, {
        "R-2": {"resposta": "Atende Parcialmente", "justificativa": "Via alertas de log."},
        "R-3": {"resposta": "Atende Totalmente", "justificativa": "Nativo."},          # mesma célula mesclada C3:C4
    })
    assert kit.main(["respostas", str(pasta)]) == 0
    copia = pasta / "_analise-rfp" / "03-entregas" / "matriz - RESPONDIDA Azure Monitor.xlsx"
    assert load_workbook(copia)["Requisitos"]["C3"].value == "Atende Parcialmente"
    verificacao = (pasta / "_analise-rfp" / "02-analise" / "verificacao-planilhas.md").read_text(encoding="utf-8")
    assert "CONFLITOS" in verificacao


def test_errata_nao_cola_resposta_em_outro_requisito(tmp_path):
    pasta = tmp_path / "cliente"
    pasta.mkdir()
    wb = Workbook()
    ws = wb.active
    ws.append(["Requisito", "Módulo", "Resposta"])
    ws.append(["Monitorar filas de mensageria.", "Infra", ""])
    ws.append(["Monitorar mainframe z/OS.", "Infra", ""])
    wb.save(pasta / "matriz.xlsx")
    assert kit.main(["init", str(pasta), "--modo", "proponente", "--proponente", "azure-monitor", "--nao-assistida"]) == 0
    assert kit.main(["rtm", str(pasta)]) == 0
    assert kit.main(["respostas", str(pasta)]) == 0
    _responder(pasta, {"M-0002": {"resposta": "Não atende", "justificativa": "Sem suporte a z/OS."}})
    ws.insert_rows(2)                                                                # errata: linha nova no meio
    ws["A2"], ws["B2"] = "Dashboards customizáveis.", "Visualização"
    wb.save(pasta / "matriz.xlsx")
    assert kit.main(["rtm", str(pasta)]) == 0
    assert kit.main(["respostas", str(pasta)]) == 0
    itens = {r["requisito"]: r for r in json.loads(
        (pasta / "_analise-rfp" / "02-analise" / "respostas.json").read_text(encoding="utf-8"))}
    assert itens["Dashboards customizáveis."]["resposta"] == ""
    assert itens["Monitorar mainframe z/OS."]["resposta"] == "Não atende"


@pytest.mark.parametrize("valor,escala,esperado", [
    ("Atende Totalmente", ["Não Atende", "Atende Parcialmente", "Atende Totalmente"], "pleno"),
    ("Atende", ["Selecione", "Atende", "Atende Parcialmente", "Não Atende"], "pleno"),
    ("Não Aplicável", ["Sim", "Não", "Não Aplicável"], "na"),
    ("Se propõe a desenvolver", ["Atende Plenamente", "Se propõe a desenvolver"], "parcial"),
    ("Atendido por Extensão", ["Atendido Nativamente", "Atendido por Extensão"], "parcial"),
    ("Selecione", ["Selecione", "Sim", "Não"], ""),
])
def test_nivel_da_resposta(valor, escala, esperado):
    assert nivel(valor, escala) == esperado


def test_url_redirecionada_exige_conferencia(monkeypatch):
    from rfpkit import urls
    monkeypatch.setattr(urls, "buscar", lambda url, timeout=25: {
        "status": 200, "final": "https://learn.microsoft.com/en-us/azure/azure-monitor/overview",
        "html": "<title>Visão geral</title> opentelemetry", "erro": ""})
    r = urls.verificar("https://learn.microsoft.com/en-us/azure/azure-monitor/app/pagina-aposentada", ["opentelemetry"])
    assert not r["ok"] and r["redirecionada_para"].endswith("/overview") and r["situacao"] == "REDIRECIONADA"


@pytest.mark.parametrize("status,situacao", [(403, "BLOQUEADA"), (429, "BLOQUEADA"), (404, "QUEBRADA"), (500, "QUEBRADA")])
def test_url_bloqueada_por_robo_e_inconclusiva(monkeypatch, status, situacao):
    from rfpkit import urls
    monkeypatch.setattr(urls, "buscar", lambda url, timeout=25: {"status": status, "final": url, "html": "",
                                                                 "erro": f"HTTP {status}"})
    assert urls.verificar("https://docs.exemplo.com/pagina", ["x"])["situacao"] == situacao


def test_pagina_montada_por_javascript_e_inconclusiva(monkeypatch):
    """Evidência marcada 'verificacao: navegador': 200 sem o texto (SPA) não derruba o status na KB."""
    from rfpkit import urls
    from rfpkit.kb import KB
    monkeypatch.setattr(urls, "buscar", lambda url, timeout=25: {"status": 200, "final": url,
                                                                 "html": "<title>App</title>", "erro": ""})
    assert urls.verificar("https://app.exemplo.com/terms", ["as is"], navegador=True)["situacao"] == "NAVEGADOR"
    assert urls.verificar("https://app.exemplo.com/terms", ["as is"])["situacao"] == "SEM_PALAVRAS"
    kb = KB()
    alvos = urls.alvos_da_kb(kb, "azure-monitor")
    clarity = alvos["https://clarity.microsoft.com/terms"]
    assert clarity["navegador"] and {"EV-AZ-040", "EV-AZ-041", "EV-AZ-042"} <= set(clarity["usos"])
    antes = kb.evidencia("EV-AZ-040")["status"]
    r = urls.verificar("https://clarity.microsoft.com/terms", clarity["palavras"], navegador=True)
    for bib in list(kb.bibliotecas.values()) + list(kb.cases.values()):   # qualquer gravação falharia: KB real intocada
        bib["_arquivo"] = None
    assert urls.atualizar_bibliotecas(kb, [r]) == 0 and kb.evidencia("EV-AZ-040")["status"] == antes
