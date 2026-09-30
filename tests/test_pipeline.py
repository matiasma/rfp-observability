import json

import yaml
from openpyxl import load_workbook

import kit
from rfpkit import util


def _ler(pasta, rel):
    return json.loads((pasta / "_analise-rfp" / rel).read_text(encoding="utf-8"))


def test_pipeline_completo_no_cliente_exemplo(cliente_exemplo):
    assert kit.main(["tudo", str(cliente_exemplo)]) == 0
    analise = cliente_exemplo / "_analise-rfp"

    rtm = _ler(cliente_exemplo, "00-projeto/rtm.json")
    ids = {r["id"] for r in rtm["requisitos"]}
    assert rtm["total"] >= 45
    assert {"TEO:3.1.3.1", "TEO:3.1.3.2", "TEO:3.1.3.3"} <= ids          # lista "sistemas operacionais:" expandida
    assert "TEO:3.1.3" not in ids                                          # pai substituído pelos filhos
    assert {"TEO:RC-01", "MRE:RF-12"} <= ids                               # tabela do docx + aba do xlsx
    aix = next(r for r in rtm["requisitos"] if r["id"] == "TEO:3.1.3.3")
    assert "AIX" in aix["texto"] and aix["categoria"] == "coleta"
    rf01 = next(r for r in rtm["requisitos"] if r["id"] == "MRE:RF-01")
    assert rf01["obrigatoriedade"] == "eliminatorio" and rf01["celula_resposta"] == "Requisitos Funcionais!E4"
    assert next(r for r in rtm["requisitos"] if r["id"] == "TEO:2.1.1")["natureza"] == "qualificacao"
    assert next(r for r in rtm["requisitos"] if r["id"] == "TEO:4.1.2")["natureza"] == "implantacao"

    pesos = _ler(cliente_exemplo, "00-projeto/categorias-pesos.json")
    assert abs(pesos["soma"] - 100) < 0.05
    assert all(c["id"] not in ("servicos", "licenciamento") for c in pesos["categorias"])

    ranking = _ler(cliente_exemplo, "02-analise/ranking.json")
    assert "azure-monitor" in ranking["avaliacao_completa"]
    assert ranking["edicao_gartner"] == 2026
    assert len(ranking["avaliacao_completa"]) <= 6
    gates = _ler(cliente_exemplo, "02-analise/gates.json")
    g1 = {l["gate"]: l for l in gates["fornecedores"]["azure-monitor"]["gates"]}["G1"]
    assert g1["veredito"] == "NAO"                                         # Microsoft nunca foi Líder
    assert gates["fornecedores"]["azure-monitor"]["status"] == "REPROVA"

    entregas = analise / "03-entregas"
    html = (entregas / "relatorio-exemplo.html").read_text(encoding="utf-8")
    assert "Companhia Exemplo S.A." in html and "{{" not in html and "⟨?⟩" not in html
    assert (entregas / "matriz-rtm-exemplo.xlsx").exists()
    wb = load_workbook(entregas / "comparativo-exemplo.xlsx")
    assert {"Scorecard", "Aderência por categoria", "Triagem e gates", "Fatos e fontes", "Gartner MQ"} <= set(wb.sheetnames)
    md = (entregas / "relatorio-executivo-exemplo.md").read_text(encoding="utf-8")
    assert "## Scorecard" in md and "Pendente" not in md
    assert (analise / "00-projeto" / "premissas.md").exists()
    assert "| ERRO |" not in (analise / "02-analise" / "validacao.md").read_text(encoding="utf-8")


def test_classificacao_manual_e_ajuste_de_nota(cliente_exemplo):
    analise = cliente_exemplo / "_analise-rfp"
    assert kit.main(["rtm", str(cliente_exemplo)]) == 0
    (analise / "02-analise" / "classificacao-manual.csv").write_text(
        "id;categoria;natureza;obrigatoriedade;obs\nTEO:3.7.3;aiops;;;detecção de anomalias\n", encoding="utf-8")
    util.gravar_yaml(analise / "02-analise" / "ajustes-notas.yaml", [
        {"fornecedor": "azure-monitor", "categoria": "apm", "nota": 0.75, "justificativa": "teste",
         "fontes": ["https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview"]}])
    assert kit.main(["tudo", str(cliente_exemplo)]) == 0
    rtm = _ler(cliente_exemplo, "00-projeto/rtm.json")
    item = next(r for r in rtm["requisitos"] if r["id"] == "TEO:3.7.3")
    assert item["categoria"] == "aiops" and item["origem_classificacao"] == "manual"
    ranking = _ler(cliente_exemplo, "02-analise/ranking.json")
    azure = next(l for l in ranking["ranking"] if l["fornecedor"] == "azure-monitor")
    assert azure["notas"]["apm"] == 0.75 and azure["origem_notas"]["apm"] == "ajuste"


def test_ajuste_sem_fonte_e_erro_de_validacao(cliente_exemplo):
    analise = cliente_exemplo / "_analise-rfp"
    util.gravar_yaml(analise / "02-analise" / "ajustes-notas.yaml",
                     [{"fornecedor": "azure-monitor", "categoria": "apm", "nota": 0.9}])
    assert kit.main(["tudo", str(cliente_exemplo)]) == 1


def test_modo_proponente_preenche_matriz_original(cliente_exemplo):
    # matriz numa subpasta + proponente com "/" no nome (sanitização do nome do arquivo gerado)
    (cliente_exemplo / "Anexos").mkdir()
    (cliente_exemplo / "Matriz-Requisitos-Exemplo.xlsx").rename(cliente_exemplo / "Anexos" / "Matriz-Requisitos-Exemplo.xlsx")
    cfg_path = cliente_exemplo / "_analise-rfp" / "rfp.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg.update({"modo": "proponente", "proponente": "grafana"})
    cfg["entradas"][1]["arquivo"] = "Anexos/Matriz-Requisitos-Exemplo.xlsx"
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert kit.main(["rtm", str(cliente_exemplo)]) == 0
    assert kit.main(["respostas", str(cliente_exemplo)]) == 0             # cria o esqueleto
    caminho = cliente_exemplo / "_analise-rfp" / "02-analise" / "respostas.json"
    respostas = json.loads(caminho.read_text(encoding="utf-8"))
    escalas = {r["id"]: r["escala"] for r in respostas}
    assert escalas["MRE:RF-01"][0] == "Atende Plenamente"                  # escala lida do dropdown (nome definido)
    assert escalas["MRE:DQ-1"][0] == "Atendido Nativamente"                # outra aba, outra escala (lista literal)
    for r in respostas:
        if r["id"] == "MRE:RF-01":
            r.update(resposta="atende plenamente", justificativa="Mapa de serviços.",
                     evidencias=["https://grafana.com/docs/"])
        if r["id"] == "MRE:RF-04":
            r.update(resposta="Não Atende", justificativa="Sem RUM mobile nativo GA.")
        if r["id"] == "MRE:RF-12":                                          # linha 15, fora do dropdown original
            r.update(resposta="Atende Parcialmente", justificativa="Via consultas agendadas.", metodo="Configuração",
                     poc=True, evidencias=["https://grafana.com/docs/grafana/latest/alerting/"])
        if r["id"] == "MRE:DQ-1":
            r.update(resposta="Atendido Nativamente", justificativa="Escala horizontal.")
    caminho.write_text(json.dumps(respostas, ensure_ascii=False), encoding="utf-8")
    assert kit.main(["respostas", str(cliente_exemplo)]) == 0
    entregas = cliente_exemplo / "_analise-rfp" / "03-entregas"
    preenchida = load_workbook(entregas / "Matriz-Requisitos-Exemplo - RESPONDIDA Grafana Labs (Grafana Cloud - LGTM).xlsx")
    ws = preenchida["Requisitos Funcionais"]
    assert ws["E4"].value == "Atende Plenamente"                            # grafia exata do dropdown
    assert ws["F4"].value == "Mapa de serviços. Ref.: https://grafana.com/docs/"
    assert ws["E7"].value == "Não Atende"
    assert ws["F15"].value.startswith("Via consultas agendadas. [Método: Configuração.] [Comprovação em POC.] Ref.:")
    dv = next(d for d in ws.data_validations.dataValidation if d.formula1 == "listaAderencia")
    assert "E15" in dv.sqref                                               # dropdown estendido
    assert preenchida["Dados Quantitativos"]["E2"].value == "Atendido Nativamente"
    assert sum(len(w._images) for w in preenchida.worksheets) == 1        # logotipo preservado
    assert (entregas / "matriz-respostas-exemplo.xlsx").exists()
    verificacao = (cliente_exemplo / "_analise-rfp" / "02-analise" / "verificacao-planilhas.md").read_text(encoding="utf-8")
    assert "divergentes: 0" in verificacao and "valor fora da lista: 0" in verificacao
    assert "partes preservadas byte a byte" in verificacao


def test_textos_iguais_com_ids_diferentes_nao_sao_descartados(tmp_path):
    from openpyxl import Workbook
    pasta = tmp_path / "cliente"
    pasta.mkdir()
    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Módulo", "Requisito", "Tipo"])
    ws.append(["R-1", "APM", "Deve permitir a criação de alertas por limiar.", "Obrigatório"])
    ws.append(["R-2", "Infra", "Deve permitir a criação de alertas por limiar.", "Eliminatório"])
    ws.append(["R-2", "Infra", "Deve permitir a criação de alertas por limiar.", "Eliminatório"])  # duplicata real
    wb.save(pasta / "matriz.xlsx")
    assert kit.main(["init", str(pasta), "--nao-assistida"]) == 0
    assert kit.main(["rtm", str(pasta)]) == 0
    rtm = json.loads((pasta / "_analise-rfp" / "00-projeto" / "rtm.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in rtm["requisitos"]] == ["R-1", "R-2"]
    assert rtm["requisitos"][1]["obrigatoriedade"] == "eliminatorio"


def test_init_cria_estrutura_e_detecta_documentos(tmp_path):
    import gerar_exemplo
    pasta = gerar_exemplo.gerar(tmp_path / "novo-cliente")
    assert kit.main(["init", str(pasta), "--cliente", "Novo Cliente", "--sigla", "NOVO", "--nao-assistida"]) == 0
    cfg = yaml.safe_load((pasta / "_analise-rfp" / "rfp.yaml").read_text(encoding="utf-8"))
    assert cfg["cliente"]["nome"] == "Novo Cliente" and cfg["proponente"] is None
    assert {e["arquivo"] for e in cfg["entradas"]} == {"TR-Exemplo-Observabilidade.docx", "Matriz-Requisitos-Exemplo.xlsx"}
    assert cfg["duvidas"]["modelo"] == "Anexo-Duvidas-Exemplo.xlsx"        # modelo de dúvidas reconhecido pelo nome
    assert cfg["fornecedores"]["obrigatorios"] == ["azure-monitor"]
    assert (pasta / "_analise-rfp" / "02-analise" / "narrativa.md").exists()
    assert kit.main(["tudo", str(pasta)]) == 0
