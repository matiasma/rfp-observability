"""Paridade com os entregáveis dos estudos de referência: análises internas (eliminatórios, ranking com duas lentes,
sensibilidade, cenários de gate e battlecards, dúvidas internas, maturidade dos cases, esforço × custo), índice de
entregas, relatório executivo em HTML, abas de decisão no comparativo e QA da extração."""
import json

import pytest
from docx import Document
from openpyxl import load_workbook

import kit
from rfpkit import esforco_custo, ranking
from rfpkit.config import Projeto
from rfpkit.kb import KB


def _a(pasta, *partes):
    return pasta.joinpath("_analise-rfp", *partes)


def test_analises_internas_e_indice_modo_neutro(cliente_exemplo):
    assert kit.main(["tudo", str(cliente_exemplo)]) == 0
    analise = _a(cliente_exemplo, "02-analise")
    elim = (analise / "eliminatorios.md").read_text(encoding="utf-8")
    assert "### 1.2 Qual gate elimina quem" in elim and "### 1.4 Leituras do gate" in elim
    assert "### 1.6 Dúvidas que podem reabrir um gate" in elim and "DUV-01" in elim
    assert "## 2. Requisitos eliminatórios do edital" in elim and "nota ≤ 0,5" in elim
    rk = (analise / "ranking.md").read_text(encoding="utf-8")
    for secao in ("## 4. Duas lentes", "## 5. Sensibilidade", "## 6. Recomendação por cenário de gate"):
        assert secao in rk, secao
    assert "Battlecards" not in rk                                         # só no modo proponente
    assert "resposta_desejada" not in (analise / "duvidas-interna.md").read_text(encoding="utf-8")
    assert "Resolve o G2 INDEFINIDO" in (analise / "duvidas-interna.md").read_text(encoding="utf-8")

    entregas = _a(cliente_exemplo, "03-entregas")
    indice = (entregas / "README-ENTREGAS.md").read_text(encoding="utf-8")
    assert "## 1. Peças para decisão (cliente)" in indice and "`relatorio-exemplo.html`" in indice
    assert "[`eliminatorios.md`](../02-analise/eliminatorios.md)" in indice and "**Gate estrito:**" in indice
    executivo = (entregas / "relatorio-executivo-exemplo.html").read_text(encoding="utf-8")
    assert "<table>" in executivo and "Sensibilidade" in executivo and "relatorio-exemplo.html" in executivo
    wb = load_workbook(entregas / "comparativo-exemplo.xlsx", read_only=True)
    assert {"Sensibilidade", "Cenários de gate"} <= set(wb.sheetnames)
    assert not {"Esforço PoC", "Custo"} & set(wb.sheetnames)               # sem entradas, sem abas
    html = (entregas / "relatorio-exemplo.html").read_text(encoding="utf-8")
    assert 'id="sens"' in html and 'id="cenarios"' in html and 'class="kpis"' in html and 'id="custo"' not in html


def test_esforco_custo_battlecards_e_maturidade_proponente(cliente_proponente, rede_falsa):
    assert kit.main(["tudo", str(cliente_proponente), "--urls"]) == 0
    analise = _a(cliente_proponente, "02-analise")
    ec_md = (analise / "esforco-custo.md").read_text(encoding="utf-8")
    assert "| Azure Monitor | 18–29 | 24 |" in ec_md and "ILUSTRATIVO" in ec_md
    assert "| Datadog | US$ 8,7k | US$ 104,2k | host + sessão |" in ec_md
    assert "## 4. Cruzamento esforço × custo" in ec_md
    rk = (analise / "ranking.md").read_text(encoding="utf-8")
    assert "## 8. Battlecards — concorrentes × Azure Monitor" in rk and "Mais forte que o Azure Monitor em" in rk
    cases = (analise / "cases-referencia-maturidade.md").read_text(encoding="utf-8")
    assert "| 1 | Idever |" in cases and "**7,0**" in cases
    entregas = _a(cliente_proponente, "03-entregas")
    wb = load_workbook(entregas / "comparativo-exemplo-prop.xlsx", read_only=True)
    assert {"Sensibilidade", "Esforço PoC", "Custo"} <= set(wb.sheetnames)
    indice = (entregas / "README-ENTREGAS.md").read_text(encoding="utf-8")
    assert "## 1. Peças para submissão ao cliente" in indice
    cliente = indice.split("## 2.")[0]
    assert "RESPONDIDA" in cliente and "relatorio-exemplo-prop.html" not in cliente   # relatório competitivo é interno
    memorial = Document(str(entregas / "Memorial-Tecnico-Azure-Monitor-exemplo-prop.docx"))
    titulos = [p.text for p in memorial.paragraphs if p.style.name.startswith("Heading")]
    assert "6. Maturidade da solução — casos de referência" in titulos and "7. Diferenciais" in titulos
    texto = "\n".join(c.text for t in memorial.tables for row in t.rows for c in row.cells)
    assert "Aderência (0–10)" in texto and "7,0" in texto
    html = (entregas / "relatorio-exemplo-prop.html").read_text(encoding="utf-8")
    assert 'id="esforco"' in html and 'id="custo"' in html and 'id="battle"' in html and 'id="cruz"' in html


def test_sensibilidade_e_cenarios_de_gate():
    linhas = [
        {"fornecedor": "a", "nome": "A", "aderencia_pct": 90.0, "aderencia_5": 4.5, "risco": 3, "esforco": 3, "custo": 1,
         "estrategico": 3, "nota_final": 3.13, "status_gate": "REPROVA"},
        {"fornecedor": "b", "nome": "B", "aderencia_pct": 70.0, "aderencia_5": 3.5, "risco": 3, "esforco": 3, "custo": 5,
         "estrategico": 3, "nota_final": 3.63, "status_gate": "PASSA"},
    ]
    eixos = {"aderencia": 35, "risco": 20, "esforco": 15, "custo": 20, "estrategico": 10}
    s = ranking.sensibilidade(linhas, eixos)
    so_ader = next(c for c in s["cenarios"] if c["cenario"] == "Só aderência ao edital")
    assert so_ader["ordem"][0] == "a" and so_ader["primeiro_elegivel"] == "b"
    assert s["robusto"] == "b" and s["robusto_elegivel"] == "b" and not s["estavel"]
    assert abs(sum(ranking._redistribuir(eixos, "custo", 20).values()) - 100) < 0.5
    lentes = ranking.lentes(linhas)
    assert lentes["lider_aderencia"] == "a" and lentes["lider_nota"] == "b" and not lentes["coincidem"]
    gates = {"gates": [{"id": "G1", "eliminatorio": True}],
             "fornecedores": {"a": {"gates": [{"gate": "G1", "veredito": "NAO", "eliminatorio": True}]},
                              "b": {"gates": [{"gate": "G1", "veredito": "PASSA", "eliminatorio": True}]}}}
    cen = ranking.cenarios_gate([linhas[0], linhas[1]], gates)
    assert cen[0]["melhor"] == "b" and cen[1]["cenario"] == "G1 flexibilizado" and cen[1]["melhor"] == "a"
    assert cen[1]["passam_a_elegiveis"] == ["a"] and cen[-1]["cenario"].startswith("Todos")


def test_validacao_de_esforco_e_custo(cliente_proponente):
    analise = _a(cliente_proponente, "02-analise")
    (analise / "custo.yaml").write_text(
        "moeda: USD\nfornecedores:\n  datadog:\n    componentes:\n"
        "      - {item: Infra, quantidade: 10, preco_unitario: 15}\n"
        "      - {item: Logs, valor: [5, 2], fonte: 'https://x.y/p', verificado_em: 2020-01-01}\n"
        "  azure-monitor:\n    componentes:\n      - {item: Logs, valor: 100000, fonte: 'https://x.y/a', "
        "verificado_em: 2026-09-01}\n", encoding="utf-8")
    (analise / "esforco-poc.yaml").write_text(
        "frentes:\n  - {id: F1, nome: Setup, dias: {datadog: [3, 1], azure-monitor: [1, 2], fornecedor-x: 2}}\n"
        "risco:\n  datadog: {nivel: altissimo}\n", encoding="utf-8")
    assert kit.main(["tudo", str(cliente_proponente)]) == 1
    val = (analise / "validacao.md").read_text(encoding="utf-8")
    for trecho in ("custo.yaml: datadog × Infra: preço sem fonte oficial", "mínimo maior que o máximo",
                   "verificado em 2020-01-01", "fornecedor 'fornecedor-x' sem ficha na KB", "fora de baixo/medio/alto",
                   "eixo custo: datadog tem custo menor que azure-monitor mas nota menor"):
        assert trecho in val, trecho


def test_extracao_registra_qa_e_ocr_simulado(tmp_path, monkeypatch):
    """PDF com página sem texto: QA registra a página; com OCR (Tesseract simulado) registra texto e confiança."""
    import sys
    import types

    import fitz
    from rfpkit import extracao
    pdf = tmp_path / "edital.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Item 1. A solucao devera coletar metricas de hosts e containers.")
    doc.new_page()                                                          # página "escaneada" (sem texto)
    doc.save(str(pdf))
    md, stats = extracao.pdf_para_markdown(pdf)
    assert stats["paginas_sem_texto_lista"] == [2] and stats["paginas_ocr"] == []
    falso = types.SimpleNamespace(
        pytesseract=types.SimpleNamespace(tesseract_cmd=""), Output=types.SimpleNamespace(DICT="dict"),
        image_to_string=lambda img, lang: "Texto reconhecido pelo OCR da pagina dois",
        image_to_data=lambda img, lang, output_type: {"conf": ["90", "80", "-1"]})
    monkeypatch.setitem(sys.modules, "pytesseract", falso)
    md, stats = extracao.pdf_para_markdown(pdf, ocr=True, dir_imagens=tmp_path / "imagens")
    assert stats["paginas_ocr"] == [2] and stats["ocr_confianca"] == {2: 85.0} and stats["paginas_sem_texto_lista"] == []
    assert "Texto reconhecido pelo OCR" in md and (tmp_path / "imagens" / "edital__p002.png").exists()


def test_qa_da_extracao_vira_aviso(cliente_exemplo):
    assert kit.main(["extrair", str(cliente_exemplo)]) in (0, None)
    qa = json.loads(_a(cliente_exemplo, "01-extracao", "extracao-qa.json").read_text(encoding="utf-8"))
    assert {q["arquivo"] for q in qa} >= {"TR-Exemplo-Observabilidade.docx", "Matriz-Requisitos-Exemplo.xlsx"}
    qa.append({"arquivo": "Anexo-escaneado.pdf", "tipo": "pdf", "paginas_sem_texto_lista": [1, 2]})
    _a(cliente_exemplo, "01-extracao", "extracao-qa.json").write_text(json.dumps(qa), encoding="utf-8")
    from rfpkit.validacao import validar
    kit.main(["rtm", str(cliente_exemplo)]); kit.main(["pesos", str(cliente_exemplo)]); kit.main(["ranking", str(cliente_exemplo)])
    msgs = [p["mensagem"] for p in validar(Projeto(cliente_exemplo), KB())]
    assert any("Anexo-escaneado.pdf: 2 página(s) sem texto" in m for m in msgs)


@pytest.mark.parametrize("valor,esperado", [(5, (5, 5)), ([1, 2], (1, 2)), ("3,5", (3.5, 3.5))])
def test_faixas(valor, esperado):
    assert esforco_custo._faixa(valor) == esperado


def test_entradas_malformadas_de_esforco_custo_e_duvidas_nao_derrubam_o_tudo(cliente_proponente):
    analise = _a(cliente_proponente, "02-analise")
    (analise / "esforco-poc.yaml").write_text(
        "frentes:\n  - {id: F1, nome: Setup, dias: [1, 2]}\n  - {id: F2, nome: Web, dias: {datadog: []}}\n"
        "  - {id: F3, nome: Mobile, dias: {datadog: [1, 2], azure-monitor: [3, 4]}}\n"
        "risco: {datadog: baixo, azure-monitor: alto}\n", encoding="utf-8")
    (analise / "custo.yaml").write_text(
        "ilustrativo: true\nfornecedores:\n  datadog:\n    componentes:\n      - {item: A, valor: []}\n"
        "      - {item: B, valor: 100, fonte: ['https://a.b/1', 'https://a.b/2']}\n", encoding="utf-8")
    duv = (analise / "duvidas.yaml").read_text(encoding="utf-8")
    duv = duv.replace("  prioridade: Média\n  status: PENDENTE", "  prioridade: Média\n  status: RETIRADA", 1)
    duv += "- id: DUV-004\n  pergunta: 'x?'\n  gates: [{G1: 'pode reabrir'}]\n"
    (analise / "duvidas.yaml").write_text(duv, encoding="utf-8")
    assert kit.main(["tudo", str(cliente_proponente)]) == 1                 # ERROs na validação, sem traceback
    val = (analise / "validacao.md").read_text(encoding="utf-8")
    for trecho in ("frente F1: 'dias' deve ser um mapa", "faixa deve ter 2 valores", "informe quantidade",
                   "'fonte' deve ser uma URL (texto)", "'gates' deve ser lista de ids", "status RETIRADA"):
        assert trecho in val, trecho
    resumo = esforco_custo.resumo_esforco(Projeto(cliente_proponente))
    assert resumo["fornecedores"]["datadog"]["risco"] == "baixo"            # nível sem motivo é aceito
    enviadas = load_workbook(_a(cliente_proponente, "03-entregas", "duvidas-exemplo-prop.xlsx"))["Dúvidas"]
    assert "DUV-002" not in [c.value for c in enviadas["A"]]                 # RETIRADA não vai para o cliente
    html = _a(cliente_proponente, "03-entregas", "relatorio-exemplo-prop.html").read_text(encoding="utf-8")
    assert "https://a.b/1; https://a.b/2" in html


def test_sumario_do_proponente_sem_respostas_nao_leva_scorecard_de_concorrentes(cliente_proponente):
    _a(cliente_proponente, "02-analise", "respostas.json").unlink()
    assert kit.main(["tudo", str(cliente_proponente)]) in (0, 1)
    sumario = Document(str(_a(cliente_proponente, "03-entregas", "Sumario-Executivo-exemplo-prop.docx")))
    texto = "\n".join(p.text for p in sumario.paragraphs) + "\n".join(
        c.text for t in sumario.tables for row in t.rows for c in row.cells)
    assert "Datadog" not in texto and "Respostas ainda não preenchidas" in texto


def test_indice_marca_arquivos_de_execucao_anterior(cliente_proponente):
    import os
    import time
    entregas = _a(cliente_proponente, "03-entregas")
    entregas.mkdir(parents=True, exist_ok=True)
    velho = entregas / "Sumario-Executivo-exemplo-prop.pdf"
    velho.write_bytes(b"%PDF-1.4 antigo")
    antes = time.time() - 3600
    os.utime(velho, (antes, antes))
    assert kit.main(["tudo", str(cliente_proponente)]) == 0
    indice = (entregas / "README-ENTREGAS.md").read_text(encoding="utf-8")
    assert "Sumario-Executivo-exemplo-prop.pdf" not in indice.split("## 2.")[0].split("> ⚠️")[0]
    assert "Arquivos de execuções anteriores" in indice and "`Sumario-Executivo-exemplo-prop.pdf`" in indice


def test_duvida_ligada_a_gate_pelo_numero_exato_da_clausula():
    from rfpkit.analises import _numero_clausula
    import re
    num = _numero_clausula("2.1 O fabricante deverá…")
    padrao = rf"(?<![\d.]){re.escape(num)}(?!\.?\d)"
    assert re.search(padrao, "Item 2.1 do TR") and not re.search(padrao, "item 2.13 (volumetria)")
    assert not re.search(padrao, "item 12.1 (treinamento)") and not re.search(padrao, "item 2.10")


def test_ocr_sem_tesseract_instalado_so_avisa(tmp_path, monkeypatch, capsys):
    import sys
    import types

    import fitz
    from rfpkit import extracao
    pdf = tmp_path / "escaneado.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))

    def sem_tesseract(img, lang):
        raise OSError("tesseract is not installed or it's not in your PATH")
    falso = types.SimpleNamespace(pytesseract=types.SimpleNamespace(tesseract_cmd=""),
                                  Output=types.SimpleNamespace(DICT="dict"), image_to_string=sem_tesseract,
                                  image_to_data=sem_tesseract)
    monkeypatch.setitem(sys.modules, "pytesseract", falso)
    md, stats = extracao.pdf_para_markdown(pdf, ocr=True)
    assert stats["paginas_sem_texto_lista"] == [1] and "OCR falhou" in capsys.readouterr().out
