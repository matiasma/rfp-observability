"""As 5 melhorias de confiança: investigação requisito × fornecedor (aderência por item), confiança por regras,
portão com encaminhamento e ciclo de respostas do cliente, conferência literal das citações e verificação
independente com checagens de consistência."""
import datetime as dt
import json
import shutil

import pytest
import yaml
from openpyxl import load_workbook

import kit
from rfpkit import confianca, execucao, independente, investigacao, revisao, urls, util
from rfpkit.config import KB_DIR, Projeto
from rfpkit.kb import KB


def _a(pasta, *partes):
    return pasta.joinpath("_analise-rfp", *partes)


def _preparar(pasta):
    assert kit.main(["tudo", str(pasta)]) in (0, 1)
    proj = Projeto(pasta)
    investigacao.preparar(proj)
    return proj


def _definir(proj, fid, avaliacoes: dict):
    """Grava avaliações (id -> campos) do fornecedor em investigacao.json, marcando-as como investigadas."""
    dados = json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8"))
    for e in dados:
        if e["id"] in avaliacoes:
            e["fornecedores"][fid].update({"investigado": True, "investigado_em": "2026-09-30", **avaliacoes[e["id"]]})
    investigacao.arquivo(proj).write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _nivel(dados, rid, fid):
    return next(s for s in dados["avaliacoes"] if s["id"] == rid and s["fornecedor"] == fid)


# ---------------------------------------------------------------- 4. citações literais
@pytest.mark.parametrize("citacao,esperado", [
    ("'Microsoft is not obligated to provide any support services.'", ["microsoft is not obligated to provide any support services"]),
    ("Sec. 7: 'Any support provided is as is, with all faults.'", ["any support provided is as is with all faults"]),
    ("Location tags: 'Brazil South | latam-br-gru-edge'.", ["brazil south latam br gru edge"]),
    ("Location tags incluem 'Brazil South | latam-br-gru-edge'.", ["location tags incluem brazil south latam br gru edge"]),
    ('Segundo a documentação, o "Log Analytics workspace" suporta retenção de 12 anos',           # paráfrase não passa
     ["segundo a documentacao o log analytics workspace suporta retencao de 12 anos"]),
    ("First fragment long enough... second fragment long enough", ["first fragment long enough", "second fragment long enough"]),
    ("curto", []),
])
def test_trechos_da_citacao(citacao, esperado):
    assert util.trechos_citacao(citacao) == esperado


def test_citacao_conferida_ignora_pontuacao_e_detecta_ausencia():
    pagina = "<p>Azure Monitor Logs already uses TLS 1.2/1.3 as the encryption mechanisms of choice.</p>"
    ok, falta, curtas = urls.conferir_citacoes(pagina, ["Azure Monitor Logs already uses TLS 1.2/1.3 as the encryption mechanisms",
                                                       "Data is encrypted with quantum keys everywhere", "TLS 1.3"])
    assert len(ok) == 1 and falta == ["Data is encrypted with quantum keys everywhere"] and curtas == ["TLS 1.3"]


def test_url_com_citacao_ausente_marca_mudanca_na_kb(tmp_path, rede_falsa):
    copia = tmp_path / "kb"
    shutil.copytree(KB_DIR, copia)
    kb = KB(copia)
    ev = kb.evidencia("EV-AZ-044")
    rede_falsa.texto_mudou.add(ev["url"])
    resultados = urls.verificar_varias(urls.alvos_da_kb(kb, "azure-monitor"))
    r = next(x for x in resultados if x["url"] == ev["url"])
    assert r["situacao"] == "CITACAO_AUSENTE" and r["citacoes_ausentes"]
    urls.atualizar_bibliotecas(kb, resultados)
    nova = KB(copia).evidencia("EV-AZ-044")
    assert nova["status"] == "A_VALIDAR" and "citação não encontrada" in nova["mudanca_detectada"]
    outra = KB(copia).evidencia("EV-AZ-002")
    assert outra["status"] == "VALIDADA" and outra["citacao_conferida_em"]


# ---------------------------------------------------------------- 1. investigação e aderência por item
def test_investigacao_gera_lotes_por_fornecedor_e_aderencia_por_item(cliente_proponente):
    proj = _preparar(cliente_proponente)
    info = investigacao.preparar(proj, tamanho=5)
    assert len(info["fornecedores"]) >= 3 and {l.parent.name for l in info["lotes"]} == set(info["fornecedores"])
    dados = json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8"))
    apm = [e["id"] for e in dados if e["categoria"] == "apm"]
    assert apm
    _definir(proj, "azure-monitor", {rid: {"atendimento": "nao", "evidencias": []} for rid in apm})
    kit.main(["ranking", str(cliente_proponente)])
    rk = json.loads(_a(cliente_proponente, "02-analise", "ranking.json").read_text(encoding="utf-8"))
    dd = next(l for l in rk["ranking"] if l["fornecedor"] == "azure-monitor")      # proponente: sempre na avaliação completa
    assert dd["notas"]["apm"] == 0.0 and dd["origem_notas"]["apm"] == "itens" and dd["investigacao_pct"] > 0
    assert investigacao.pontuacao({"atendimento": "pleno", "como": "extensao"}) == 0.5
    assert investigacao.pontuacao({"atendimento": "parcial", "como": "terceiro"}) == 0.25


# ---------------------------------------------------------------- 2 e 3. regras de confiança e portão
def test_regras_de_confianca(cliente_proponente, rede_falsa):
    proj = _preparar(cliente_proponente)
    url = "https://docs.datadog.example/x"
    cit = urls.citacoes_da_evidencia(KB().evidencia("EV-AZ-002"))[0]            # texto presente na página simulada
    fonte = {"evidencias": [url], "citacoes": [cit]}
    _definir(proj, "datadog", {
        "RF-01": {"atendimento": "pleno", "evidencias": [], "ga": True},
        "RF-02": {"atendimento": "pleno", **fonte, "ga": False},
        "RF-03": {"atendimento": "parcial", **fonte, "ga": True, "cobre_parametro": "parcial"},
        "RF-06": {"atendimento": "nao", "evidencias": []},
        "RF-07": {"atendimento": "pleno", **fonte, "ga": True, "conflito": True},
        "RF-09": {"atendimento": "pleno", "evidencias": ["EV-AZ-002"], "ga": True, "cobre_parametro": "sim"},
        "RF-10": {"atendimento": "pleno", **fonte, "ga": True, "cobre_parametro": "sim"},
        "RF-11": {"atendimento": "na", "evidencias": []},
        "RF-12": {"atendimento": "na", "evidencias": [], "justificativa": "o cliente não tem tabelas analíticas"},
    })
    kit.main(["validar-urls", str(cliente_proponente)])
    dados = confianca.calcular(proj, KB())
    esperado = {"RF-01": "baixa", "RF-02": "baixa", "RF-03": "media", "RF-06": "media", "RF-07": "baixa",
                "RF-09": "baixa", "RF-10": "alta", "RF-11": "media", "RF-12": "alta"}
    for rid, nivel in esperado.items():
        assert _nivel(dados, rid, "datadog")["nivel"] == nivel, rid
    motivos = {rid: json.dumps(_nivel(dados, rid, "datadog")["motivos"], ensure_ascii=False) for rid in esperado}
    assert "sem evidência oficial" in motivos["RF-01"]
    assert "evidência de outro fornecedor (azure-monitor)" in motivos["RF-09"]           # EV do Azure não sustenta Datadog
    assert "'não se aplica' sem justificativa" in motivos["RF-11"]
    assert _nivel(dados, "RF-01", "datadog")["pendencias"] == ["pergunta ao fabricante ou item de POC"]


def test_portao_de_confianca_e_resposta_plena_sem_alta(cliente_proponente, rede_falsa):
    proj = _preparar(cliente_proponente)
    rtm = json.loads(_a(cliente_proponente, "00-projeto", "rtm.json").read_text(encoding="utf-8"))
    elim = next(r["id"] for r in rtm["requisitos"] if r["obrigatoriedade"] == "eliminatorio")
    _definir(proj, "datadog", {elim: {"atendimento": "pleno", "evidencias": [], "ga": True}})
    caminho = _a(cliente_proponente, "02-analise", "respostas.json")
    resp = json.loads(caminho.read_text(encoding="utf-8"))
    for r in resp:
        if r["id"] == "RF-08":
            r["evidencias"] = []
    caminho.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    msgs = confianca.validar(proj, KB())
    texto = "\n".join(f"{n} {m}" for n, m in msgs)
    assert f"AVISO confiança baixa em eliminatório {elim} × Datadog sem encaminhamento" in texto   # não assistida
    assert "ERRO resposta plena de RF-08 com confiança baixa" in texto
    assert _a(cliente_proponente, "02-analise", "confianca.md").exists()
    _definir(proj, "datadog", {elim: {"atendimento": "pleno", "evidencias": [], "ga": True, "tipo_lacuna": "documentacao",
                                      "lacuna": "doc não detalha", "pergunta_fabricante": "Há limite de X?"}})
    texto = "\n".join(m for _, m in confianca.validar(proj, KB()))
    assert f"eliminatório {elim} × Datadog" not in texto                                     # encaminhado


def test_inconsistencias(cliente_proponente, rede_falsa):
    proj = _preparar(cliente_proponente)
    _definir(proj, "azure-monitor", {"RF-04": {"atendimento": "pleno", "evidencias": ["EV-AZ-045"], "ga": True},
                                     "RF-01": {"atendimento": "nao", "evidencias": ["EV-AZ-045"]}})
    msgs = confianca.validar(proj, KB())
    texto = "\n".join(f"{n} {m}" for n, m in msgs)
    assert "ERRO inconsistência (Azure Monitor): RF-04: resposta 'Não Atende' difere da investigação (pleno)" in texto
    assert "EV-AZ-045 sustenta 'pleno' e 'não atende'" in texto
    assert "contradiz o fato rum_mobile=NAO" in texto


# ---------------------------------------------------------------- 3. ciclo de respostas do cliente
def test_resposta_do_cliente_reabre_revisao_e_investigacao(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "datadog", {"RF-04": {"atendimento": "nao", "evidencias": [], "duvida": "DUV-001"}})
    caminho = _a(cliente_proponente, "02-analise", "duvidas.yaml")
    t = caminho.read_text(encoding="utf-8")
    t = t.replace('  prioridade: Alta\n  status: PENDENTE',
                  '  prioridade: Alta\n  status: RESPONDIDA\n  resposta_cliente: "OpenTelemetry é aceito."\n'
                  '  respondida_em: 2026-10-01', 1)
    caminho.write_text(t, encoding="utf-8")
    info = investigacao.preparar(proj)
    assert info["reabertas"] >= 1
    rf04 = next(e for e in json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8")) if e["id"] == "RF-04")
    dd = rf04["fornecedores"]["datadog"]
    assert not dd["investigado"] and dd["resposta_cliente"] == "DUV-001: OpenTelemetry é aceito."
    lote = next(l for l in (investigacao.dir_lotes(proj) / "datadog").glob("lote-*.json")
                if any(i["id"] == "RF-04" for i in json.loads(l.read_text(encoding="utf-8"))))
    assert "resposta_cliente" in next(i for i in json.loads(lote.read_text(encoding="utf-8")) if i["id"] == "RF-04")
    rev = next(i for i in revisao.carregar(proj) if i["id"] == "RF-04")
    assert rev["revisado"] is True                                          # ainda não reprocessada
    info_rev = revisao.preparar(proj)
    rev = next(i for i in revisao.carregar(proj) if i["id"] == "RF-04")
    assert not rev["revisado"] and rev["reabrir_por"] == ["DUV-001"] and info_rev["pendentes"] >= 1
    _definir(proj, "datadog", {"RF-04": {"atendimento": "parcial", "evidencias": [], "investigado": True}})
    investigacao.preparar(proj)
    dd = next(e for e in json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8")) if e["id"] == "RF-04")["fornecedores"]["datadog"]
    assert dd["investigado"] and dd["respostas_incorporadas"] == ["DUV-001"] and "reabrir" not in dd
    investigacao.preparar(proj)                                             # não reabre de novo
    dd = next(e for e in json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8")) if e["id"] == "RF-04")["fornecedores"]["datadog"]
    assert dd["investigado"]


def test_lacuna_da_investigacao_vira_duvida(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "datadog", {"RF-12": {"atendimento": "parcial", "evidencias": [], "tipo_lacuna": "cliente",
                                         "lacuna": "tabelas analíticas não identificadas",
                                         "duvida_sugerida": "Quais tabelas analíticas devem ter a atualidade monitorada?"}})
    investigacao.preparar(proj)
    duv = yaml.safe_load(_a(cliente_proponente, "02-analise", "duvidas.yaml").read_text(encoding="utf-8"))
    nova = next(d for d in duv if d.get("origem") == "investigacao-llm")
    assert nova["requisitos"] == ["RF-12"] and nova["id"] == "DUV-004"


# ---------------------------------------------------------------- 5. verificação independente
def test_verificacao_independente_amostra_divergencia_e_resolucao(cliente_proponente, rede_falsa):
    proj = _preparar(cliente_proponente)
    kit.main(["validar-urls", str(cliente_proponente)])
    kb = KB()
    info = independente.preparar(proj, kb)
    regs = independente.carregar(proj)
    motivos = {v["motivo_amostra"] for v in regs}
    assert info["amostra"] == len(regs) and {"resposta plena do proponente", "eliminatório"} <= motivos
    lote = info["lotes"][0]
    itens = json.loads(lote.read_text(encoding="utf-8"))
    assert "primeiro" not in itens[0] and "atendimento" in itens[0] and not itens[0]["atendimento"]   # cego
    alvo = (itens[0]["id"], itens[0]["fornecedor"])
    for i in itens:
        i.update({"atendimento": "nao" if (i["id"], i["fornecedor"]) == alvo else
                  next(v for v in regs if (v["id"], v["fornecedor"]) == (i["id"], i["fornecedor"]))["primeiro"]["atendimento"],
                  "confere_evidencia": "nao" if (i["id"], i["fornecedor"]) == alvo else "sim", "verificado": True,
                  "modelo": "outro"})
    lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    info = independente.preparar(proj, kb)
    assert info["divergentes"] == 1 and info["divergencias_abertas"] == 1
    assert _nivel(confianca.calcular(proj, kb), *alvo)["nivel"] == "baixa"
    regs = independente.carregar(proj)
    for v in regs:
        if (v["id"], v["fornecedor"]) == alvo:
            v["resolucao"] = "manter"
    independente.arquivo(proj).write_text(json.dumps(regs, ensure_ascii=False), encoding="utf-8")
    assert any("exige justificativa" in m for _, m in independente.validar(proj))
    for v in regs:
        if (v["id"], v["fornecedor"]) == alvo:
            v["resolucao_obs"] = "a documentação oficial citada cobre o requisito na seção X"
    independente.arquivo(proj).write_text(json.dumps(regs, ensure_ascii=False), encoding="utf-8")
    assert not any("exige justificativa" in m for _, m in independente.validar(proj))
    assert _nivel(confianca.calcular(proj, kb), *alvo)["nivel"] != "baixa"
    assert independente.preparar(proj, kb)["divergencias_abertas"] == 0


# ---------------------------------------------------------------- relatórios
def test_relatorios_mostram_confianca(cliente_proponente, rede_falsa):
    assert kit.main(["tudo", str(cliente_proponente), "--urls"]) == 0
    entregas = _a(cliente_proponente, "03-entregas")
    html = (entregas / "relatorio-exemplo-prop.html").read_text(encoding="utf-8")
    assert 'id="confianca"' in html and "Confiança da análise" in html and "com confiança alta" in html
    wb = load_workbook(entregas / "comparativo-exemplo-prop.xlsx", read_only=True)
    assert {"Confiança", "Avaliações"} <= set(wb.sheetnames)
    indice = (entregas / "README-ENTREGAS.md").read_text(encoding="utf-8")
    assert "**Confiança (regras do kit):** Azure Monitor" in indice and "confianca.md" in indice
    conf = (_a(cliente_proponente, "02-analise", "confianca.md")).read_text(encoding="utf-8")
    assert "| DQ-3 | Azure Monitor |" in conf and "dúvida DUV-002" in conf


def test_lote_com_preview_chega_ao_consolidado_e_lote_antigo_nao_apaga(cliente_proponente):
    proj = _preparar(cliente_proponente)
    lote = next((investigacao.dir_lotes(proj) / "datadog").glob("lote-*.json"))
    itens = json.loads(lote.read_text(encoding="utf-8"))
    itens[0].update({"atendimento": "pleno", "ga": False, "evidencias": ["EV-AZ-002"], "investigado": True})
    lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    investigacao.preparar(proj)
    a = next(e for e in json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8"))
             if e["id"] == itens[0]["id"])["fornecedores"]["datadog"]
    assert a["ga"] is False and a["investigado"] is True
    _definir(proj, "datadog", {itens[1]["id"]: {"atendimento": "nao", "evidencias": []}})
    investigacao.preparar(proj)                                               # lotes antigos não revertem a edição
    b = next(e for e in json.loads(investigacao.arquivo(proj).read_text(encoding="utf-8"))
             if e["id"] == itens[1]["id"])["fornecedores"]["datadog"]
    assert b["atendimento"] == "nao" and b["investigado"] is True


# ---------------------------------------------------------------- regressões da revisão de código
def _kb_com_evidencia_extra(tmp_path, citacao_curta=False):
    """Cópia da KB com EV-AZ-998 na MESMA página de EV-AZ-002, com uma citação que a página não tem."""
    copia = tmp_path / "kb"
    shutil.copytree(KB_DIR, copia)
    arq = copia / "evidencias" / "azure-monitor.yaml"
    dados = yaml.safe_load(arq.read_text(encoding="utf-8"))
    base = next(e for e in dados["evidencias"] if e["id"] == "EV-AZ-002")
    limpo = {k: v for k, v in base.items() if k not in ("citacao", "citacoes", "citacao_conferida_em")}
    dados["evidencias"].append({**limpo, "id": "EV-AZ-998",
                                "citacoes": ["This sentence is not on the simulated page at all"]})
    if citacao_curta:
        base.pop("citacao", None)
        base.pop("citacao_conferida_em", None)
        base["citacoes"] = ["TLS 1.3"]
    arq.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return copia


def _responder(pasta, did, texto):
    caminho = _a(pasta, "02-analise", "duvidas.yaml")
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    for d in dados:
        if d.get("id") == did:
            d.update({"status": "RESPONDIDA", "resposta_cliente": texto, "respondida_em": "2026-10-01"})
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_citacao_de_outra_evidencia_na_mesma_pagina_nao_derruba_e_curta_nao_carimba(tmp_path, rede_falsa):
    copia = _kb_com_evidencia_extra(tmp_path, citacao_curta=True)
    kb = KB(copia)
    resultados = urls.verificar_varias(urls.alvos_da_kb(kb, "azure-monitor"))
    r = next(x for x in resultados if x["url"] == kb.evidencia("EV-AZ-002")["url"])
    assert r["situacao"] == "CITACAO_AUSENTE" and "TLS 1.3" in r["_inverificaveis"]
    urls.atualizar_bibliotecas(kb, resultados)
    nova = KB(copia)
    e2, e998 = nova.evidencia("EV-AZ-002"), nova.evidencia("EV-AZ-998")
    assert e2["status"] == "VALIDADA" and not e2.get("citacao_conferida_em")       # curta: não conta como conferida
    assert e998["status"] == "A_VALIDAR" and "citação não encontrada" in e998["mudanca_detectada"]


def test_confianca_julga_cada_evidencia_pelas_proprias_citacoes(cliente_proponente, tmp_path, rede_falsa):
    kb = KB(_kb_com_evidencia_extra(tmp_path))
    proj = _preparar(cliente_proponente)
    _definir(proj, "azure-monitor", {
        "RF-11": {"atendimento": "pleno", "evidencias": ["EV-AZ-002"], "ga": True, "cobre_parametro": "sim"},
        "RF-12": {"atendimento": "pleno", "evidencias": ["EV-AZ-998"], "ga": True, "cobre_parametro": "sim"}})
    resultados = urls.verificar_varias(urls.alvos_do_estudo(proj, kb))
    urls.gravar_relatorio(resultados, proj.dir_analise / "validacao-urls.csv",
                          caminho_json=proj.dir_analise / "validacao-urls.json")
    dados = confianca.calcular(proj, kb)
    rf11 = _nivel(dados, "RF-11", "azure-monitor")
    assert rf11["nivel"] != "baixa" and "citação não encontrada" not in json.dumps(rf11, ensure_ascii=False)
    rf12 = _nivel(dados, "RF-12", "azure-monitor")
    assert rf12["nivel"] == "baixa" and "EV-AZ-998: citação não encontrada" in json.dumps(rf12, ensure_ascii=False)


def test_citacoes_de_item_com_varias_paginas(cliente_proponente, rede_falsa):
    proj = _preparar(cliente_proponente)
    cit = urls.citacoes_da_evidencia(KB().evidencia("EV-AZ-002"))[0]
    u1, u2, u3 = (f"https://docs.datadog.example/{n}" for n in ("a", "b", "c"))
    rede_falsa.texto_mudou.update({u2, u3})
    base = {"atendimento": "pleno", "citacoes": [cit], "ga": True, "cobre_parametro": "sim"}
    _definir(proj, "datadog", {"RF-10": {**base, "evidencias": [u1, u2]},
                               "RF-11": {**base, "evidencias": [u2, u3]},
                               "RF-12": {**base, "evidencias": [u1], "citacoes": ["SLA 99,9%"]}})
    kit.main(["validar-urls", str(cliente_proponente)])
    checagem = {r["url"]: r for r in json.loads(_a(cliente_proponente, "02-analise", "validacao-urls.json")
                                                 .read_text(encoding="utf-8"))}
    assert checagem[u1]["situacao"] == "OK" and checagem[u2]["situacao"] == "OK"   # a citação pode estar na outra página
    dados = confianca.calcular(proj, KB())
    assert _nivel(dados, "RF-10", "datadog")["nivel"] == "alta"
    assert _nivel(dados, "RF-11", "datadog")["nivel"] == "baixa"                    # em nenhuma das páginas
    rf12 = _nivel(dados, "RF-12", "datadog")
    assert rf12["nivel"] == "media" and "curta demais" in json.dumps(rf12["motivos"], ensure_ascii=False)


@pytest.mark.parametrize("citacao,esperado", [
    ("Datadog's docs describe the index's retention settings in detail",
     ["datadog s docs describe the index s retention settings in detail"]),
])
def test_apostrofo_nao_vira_aspas(citacao, esperado):
    assert util.trechos_citacao(citacao) == esperado


def test_fato_da_kb_casa_palavra_inteira():
    padroes = confianca._FATOS_RE["rum_mobile"]
    assert not util.contar(padroes, util.norm("Relatórios de uso por equipe"))
    assert util.contar(padroes, util.norm("Aplicativos iOS e Android"))


def test_investigacao_de_quem_sai_do_escopo_nao_se_perde(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "datadog", {"RF-10": {"atendimento": "pleno", "evidencias": ["https://docs.datadog.example/x"]}})
    caminho = _a(cliente_proponente, "02-analise", "ranking.json")
    rk = json.loads(caminho.read_text(encoding="utf-8"))
    original = list(rk["avaliacao_completa"])
    rk["avaliacao_completa"] = [f for f in original if f != "datadog"]
    caminho.write_text(json.dumps(rk, ensure_ascii=False), encoding="utf-8")
    investigacao.preparar(proj)
    e = next(x for x in investigacao.carregar(proj) if x["id"] == "RF-10")
    assert "datadog" not in e["fornecedores"] and e["fora_do_campo"]["datadog"]["atendimento"] == "pleno"
    rk["avaliacao_completa"] = original
    caminho.write_text(json.dumps(rk, ensure_ascii=False), encoding="utf-8")
    investigacao.preparar(proj)
    e = next(x for x in investigacao.carregar(proj) if x["id"] == "RF-10")
    assert e["fornecedores"]["datadog"]["investigado"] and "fora_do_campo" not in e
    # requisito que sai do escopo vai para o arquivo e volta com a investigação
    rtm_arq = _a(cliente_proponente, "00-projeto", "rtm.json")
    rtm = json.loads(rtm_arq.read_text(encoding="utf-8"))
    for r in rtm["requisitos"]:
        if r["id"] == "RF-10":
            r["natureza"] = "comercial"
    rtm_arq.write_text(json.dumps(rtm, ensure_ascii=False), encoding="utf-8")
    assert investigacao.preparar(proj)["arquivadas"] == 1
    assert not any(x["id"] == "RF-10" for x in investigacao.carregar(proj))
    for r in rtm["requisitos"]:
        if r["id"] == "RF-10":
            r["natureza"] = "tecnico"
    rtm_arq.write_text(json.dumps(rtm, ensure_ascii=False), encoding="utf-8")
    investigacao.preparar(proj)
    e = next(x for x in investigacao.carregar(proj) if x["id"] == "RF-10")
    assert e["fornecedores"]["datadog"]["atendimento"] == "pleno" and e["fornecedores"]["datadog"]["investigado"]


def test_triagem_nao_oscila_com_a_investigacao(cliente_proponente):
    proj = _preparar(cliente_proponente)
    kit.main(["ranking", str(cliente_proponente)])
    caminho = _a(cliente_proponente, "02-analise", "ranking.json")
    rk0 = json.loads(caminho.read_text(encoding="utf-8"))
    antes = {t["id"]: t["aderencia_previa_pct"] for t in rk0["triagem"]}
    _definir(proj, "datadog", {e["id"]: {"atendimento": "nao", "evidencias": []} for e in investigacao.carregar(proj)})
    kit.main(["ranking", str(cliente_proponente)])
    rk = json.loads(caminho.read_text(encoding="utf-8"))
    assert {t["id"]: t["aderencia_previa_pct"] for t in rk["triagem"]} == antes
    assert rk["avaliacao_completa"] == rk0["avaliacao_completa"]
    dd = next(l for l in rk["ranking"] if l["fornecedor"] == "datadog")
    assert dd["aderencia_pct"] < antes["datadog"]


def test_aplicar_itens_sem_nota_da_kb_fica_incompleto(cliente_proponente):
    proj = Projeto(cliente_proponente)
    entradas = [{"id": "R1", "categoria": "apm", "obrigatoriedade": "obrigatorio",
                 "fornecedores": {"x": {"investigado": True, "atendimento": "pleno"}}},
                {"id": "R2", "categoria": "apm", "obrigatoriedade": "obrigatorio",
                 "fornecedores": {"x": {"investigado": False}}}]
    notas, origem, pct = investigacao.aplicar_itens(proj, "x", [{"id": "apm"}], {"apm": None}, {}, entradas)
    assert origem["apm"] == "itens+ausente" and notas["apm"] == 0.5 and pct == 50.0


def test_lote_concluido_limpa_campos(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "datadog", {"RF-10": {"atendimento": "pleno", "evidencias": ["https://docs.datadog.example/x"],
                                         "conflito": True, "lacuna": "fontes divergem", "tipo_lacuna": "conflito"}})
    req = next(e for e in investigacao.carregar(proj) if e["id"] == "RF-10")
    lote = investigacao.dir_lotes(proj) / "datadog" / "lote-99.json"
    lote.write_text(json.dumps([{"id": "RF-10", "fornecedor": "datadog", "requisito": req["requisito"],
                                 "atendimento": "nao", "evidencias": [], "conflito": False, "lacuna": "",
                                 "tipo_lacuna": "", "investigado": True}], ensure_ascii=False), encoding="utf-8-sig")
    investigacao.preparar(proj)
    a = next(e for e in investigacao.carregar(proj) if e["id"] == "RF-10")["fornecedores"]["datadog"]
    assert a["atendimento"] == "nao" and a["evidencias"] == [] and a["conflito"] is False and a["lacuna"] == ""
    rf04 = next(i for i in revisao.carregar(proj) if i["id"] == "RF-04")
    pasta = revisao.dir_lotes(proj)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "lote-01.json").write_text(json.dumps([{**rf04, "clareza": "clara", "lacuna": "", "revisado": True}],
                                                   ensure_ascii=False), encoding="utf-8")
    assert not revisao.preparar(proj)["problemas"]
    rf04 = next(i for i in revisao.carregar(proj) if i["id"] == "RF-04")
    assert rf04["clareza"] == "clara" and rf04["lacuna"] == ""


def test_lotes_ilegiveis_sao_isolados_e_informados(cliente_proponente):
    proj = _preparar(cliente_proponente)
    lote = next((investigacao.dir_lotes(proj) / "datadog").glob("lote-*.json"))
    lote.write_text('[{"id": "RF-01", quebrado', encoding="utf-8")
    info = investigacao.preparar(proj)
    assert info["problemas"] and lote.with_name(lote.name + ".invalido").exists()
    for pasta, preparar in ((revisao.dir_lotes(proj), lambda: revisao.preparar(proj)),
                            (independente.dir_lotes(proj), lambda: independente.preparar(proj, KB()))):
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "lote-01.json").write_text('{"nao": "é uma lista"}', encoding="utf-8")
        assert preparar()["problemas"] and (pasta / "lote-01.json.invalido").exists()
    assert len(execucao.estado(proj, KB())["lotes_isolados"]) == 3                     # apontados na execução


def test_segunda_resposta_do_cliente_nao_se_perde(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "datadog", {"RF-04": {"atendimento": "nao", "evidencias": [], "duvida": ["DUV-001", "DUV-002"]}})
    _responder(cliente_proponente, "DUV-001", "OpenTelemetry é aceito.")
    investigacao.preparar(proj)
    lote = next(l for l in (investigacao.dir_lotes(proj) / "datadog").glob("lote-*.json")
                if any(i["id"] == "RF-04" for i in json.loads(l.read_text(encoding="utf-8"))))
    _responder(cliente_proponente, "DUV-002", "Retenção de 13 meses.")         # chega depois do lote gerado
    itens = json.loads(lote.read_text(encoding="utf-8"))
    for i in itens:
        if i["id"] == "RF-04":
            assert "DUV-001" in i["resposta_cliente"] and "DUV-002" not in i["resposta_cliente"]
            i.update({"atendimento": "parcial", "investigado": True})
    lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    investigacao.preparar(proj)
    dd = next(e for e in investigacao.carregar(proj) if e["id"] == "RF-04")["fornecedores"]["datadog"]
    assert dd["atendimento"] == "parcial" and dd["respostas_incorporadas"] == ["DUV-001"]
    assert not dd["investigado"] and dd["reabrir_por"] == ["DUV-002"]                   # a segunda reabre


def test_proponente_com_investigacao_parcial_mantem_respostas_nos_demais(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "azure-monitor", {"RF-10": {"atendimento": "pleno", "evidencias": ["EV-AZ-045"], "ga": True}})
    prop = [a for a in confianca.avaliacoes_do_estudo(proj, KB()) if a["fornecedor"] == "azure-monitor"]
    assert [a["origem"] for a in prop if a["id"] == "RF-10"] == ["investigacao"]
    assert any(a["origem"] == "respostas" for a in prop)


def test_verificacao_independente_fora_da_amostra_continua_valendo(cliente_proponente, rede_falsa, monkeypatch):
    proj = _preparar(cliente_proponente)
    kb = KB()
    info = independente.preparar(proj, kb)
    lote = info["lotes"][0]
    itens = json.loads(lote.read_text(encoding="utf-8"))
    regs = {(v["id"], v["fornecedor"]): v for v in independente.carregar(proj)}
    alvo = (itens[0]["id"], itens[0]["fornecedor"])
    for i in itens:
        chave = (i["id"], i["fornecedor"])
        i.update({"atendimento": "nao" if chave == alvo else regs[chave]["primeiro"]["atendimento"],
                  "confere_evidencia": "nao" if chave == alvo else "sim", "verificado": True, "modelo": "outro"})
    lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    independente.preparar(proj, kb)
    original = independente.amostra
    monkeypatch.setattr(independente, "amostra", lambda projeto, lista: [
        (a, m) for a, m in original(projeto, lista) if (a["id"], a["fornecedor"]) != alvo])
    info = independente.preparar(proj, kb)
    fora = next(v for v in independente.carregar(proj) if (v["id"], v["fornecedor"]) == alvo)
    assert fora["na_amostra"] is False and fora["divergente"]
    assert info["divergencias_abertas"] == 1 and info["divergentes"] == 0            # fora da amostra, mas vale
    assert _nivel(confianca.calcular(proj, kb), *alvo)["nivel"] == "baixa"
    _definir(proj, alvo[1], {alvo[0]: {"atendimento": "parcial", "evidencias": []}})   # conclusão mudou
    motivos = json.dumps(_nivel(confianca.calcular(proj, kb), *alvo)["motivos"], ensure_ascii=False)
    assert "verificação independente" not in motivos
    independente.preparar(proj, kb)
    guardadas = [v for v in independente.carregar(proj) if (v["id"], v["fornecedor"]) == alvo]
    assert guardadas and all(v["suspensa"] for v in guardadas)                  # guardada, mas não vale
    assert independente.resumo(proj)["divergencias_abertas"] == 0


def test_evidencia_de_navegador_vale_pela_conferencia_no_navegador(cliente_proponente, tmp_path, rede_falsa):
    copia = tmp_path / "kb"
    shutil.copytree(KB_DIR, copia)
    arq = copia / "evidencias" / "azure-monitor.yaml"
    dados = yaml.safe_load(arq.read_text(encoding="utf-8"))
    for e in dados["evidencias"]:
        if e["id"] == "EV-AZ-040":
            e["verificado_navegador_em"] = dt.date.today().isoformat()
    arq.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    kb = KB(copia)
    url = kb.evidencia("EV-AZ-040")["url"]
    rede_falsa.texto_mudou.add(url)                                   # HTML cru sem as citações (página em JavaScript)
    proj = _preparar(cliente_proponente)
    _definir(proj, "azure-monitor", {"RF-11": {"atendimento": "pleno", "evidencias": ["EV-AZ-040"], "ga": True,
                                               "cobre_parametro": "sim"}})
    resultados = urls.verificar_varias(urls.alvos_do_estudo(proj, kb))
    assert next(r for r in resultados if r["url"] == url)["situacao"] == "NAVEGADOR"
    urls.gravar_relatorio(resultados, proj.dir_analise / "validacao-urls.csv",
                          caminho_json=proj.dir_analise / "validacao-urls.json")
    assert _nivel(confianca.calcular(proj, kb), "RF-11", "azure-monitor")["nivel"] == "alta"


def test_ga_invalido_ou_ausente_nao_da_alta(cliente_proponente, rede_falsa):
    proj = _preparar(cliente_proponente)
    cit = urls.citacoes_da_evidencia(KB().evidencia("EV-AZ-002"))[0]
    fonte = {"atendimento": "pleno", "evidencias": ["https://docs.datadog.example/x"], "citacoes": [cit],
             "cobre_parametro": "sim"}
    _definir(proj, "datadog", {"RF-08": {**fonte, "ga": "preview"}, "RF-10": {**fonte, "ga": None},
                               "RF-11": {**fonte, "ga": True}})
    kit.main(["validar-urls", str(cliente_proponente)])
    dados = confianca.calcular(proj, KB())
    assert [_nivel(dados, rid, "datadog")["nivel"] for rid in ("RF-08", "RF-10", "RF-11")] == ["baixa", "media", "alta"]
    msgs = investigacao.validar(proj, KB())
    assert any(n == "ERRO" and "RF-08" in m and "'ga' deve ser true ou false" in m for n, m in msgs)
    assert any(n == "AVISO" and "RF-10" in m and "'ga' não informado" in m for n, m in msgs)


def test_errata_que_renumera_requisitos_preserva_o_trabalho(cliente_proponente):
    proj = _preparar(cliente_proponente)
    _definir(proj, "datadog", {"RF-10": {"atendimento": "pleno", "evidencias": ["https://docs.datadog.example/x"],
                                         "ga": True}})
    caminho = _a(cliente_proponente, "02-analise", "duvidas.yaml")
    duv = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    duv.append({"id": "DUV-009", "pergunta": "Os webhooks precisam de autenticação mútua?", "requisitos": ["RF-10"],
                "status": "PENDENTE"})
    caminho.write_text(yaml.safe_dump(duv, allow_unicode=True, sort_keys=False), encoding="utf-8")
    rtm_arq = _a(cliente_proponente, "00-projeto", "rtm.json")
    rtm = json.loads(rtm_arq.read_text(encoding="utf-8"))
    for r in rtm["requisitos"]:
        r["id"] = "MRE:" + r["id"]                                   # errata: agora há dois documentos
    rtm_arq.write_text(json.dumps(rtm, ensure_ascii=False), encoding="utf-8")
    info = investigacao.preparar(proj)
    assert info["arquivadas"] == 0
    e = next(x for x in investigacao.carregar(proj) if x["id"] == "MRE:RF-10")
    assert e["fornecedores"]["datadog"]["investigado"] and e["ids_anteriores"] == ["RF-10"]
    revisao.preparar(proj)
    rev = next(i for i in revisao.carregar(proj) if i["id"] == "MRE:RF-04")
    assert rev["revisado"] and rev["clareza"] == "ambigua" and rev["ids_anteriores"] == ["RF-04"]
    _responder(cliente_proponente, "DUV-009", "Sim, mTLS.")         # dúvida ligada ao id antigo ainda reabre
    investigacao.preparar(proj)
    dd = next(x for x in investigacao.carregar(proj) if x["id"] == "MRE:RF-10")["fornecedores"]["datadog"]
    assert not dd["investigado"] and dd["reabrir_por"] == ["DUV-009"]
    regs = [{"id": "RF-10", "fornecedor": "datadog", "requisito": e["requisito"], "impressao": "x", "verificado": True}]
    assert independente._rechavear(proj, regs)[0]["id"] == "MRE:RF-10"


def test_rtm_aplica_correcao_da_revisao_pelo_texto(cliente_proponente):
    proj = _preparar(cliente_proponente)
    caminho = revisao.arquivo(proj)
    itens = json.loads(caminho.read_text(encoding="utf-8"))
    for i in itens:
        if i["id"] == "RF-05":
            i.update({"id": "ANTIGO:RF-05", "categoria": "aiops", "revisado": True})
    caminho.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    kit.main(["rtm", str(cliente_proponente)])
    rtm = json.loads(_a(cliente_proponente, "00-projeto", "rtm.json").read_text(encoding="utf-8"))
    rf05 = next(r for r in rtm["requisitos"] if r["id"] == "RF-05")
    assert rf05["categoria"] == "aiops" and rf05["origem_classificacao"] == "revisao-llm"


def test_verificacao_independente_sobrevive_a_reabertura(cliente_proponente, rede_falsa, monkeypatch):
    proj = _preparar(cliente_proponente)
    kb = KB()
    alvo = ("RF-10", "datadog")
    monkeypatch.setattr(independente, "amostra", lambda projeto, lista: [
        (a, "teste") for a in lista if (a["id"], a["fornecedor"]) == alvo])
    fonte = {"atendimento": "pleno", "evidencias": ["https://docs.datadog.example/x"], "ga": True, "duvida": "DUV-001"}
    _definir(proj, "datadog", {"RF-10": fonte})
    lote = independente.preparar(proj, kb)["lotes"][0]
    itens = json.loads(lote.read_text(encoding="utf-8"))
    itens[0].update({"atendimento": "nao", "confere_evidencia": "nao", "verificado": True, "modelo": "outro"})
    lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    independente.preparar(proj, kb)
    regs = independente.carregar(proj)
    regs[0].update({"resolucao": "manter", "resolucao_obs": "a página cobre o requisito na seção X"})
    independente.arquivo(proj).write_text(json.dumps(regs, ensure_ascii=False), encoding="utf-8")
    _responder(cliente_proponente, "DUV-001", "Webhooks com HMAC.")
    investigacao.preparar(proj)                                       # reabre RF-10 × Datadog
    info = independente.preparar(proj, kb)
    guardada = next(v for v in independente.carregar(proj) if (v["id"], v["fornecedor"]) == alvo)
    assert guardada["suspensa"] and guardada["resolucao"] == "manter" and info["divergencias_abertas"] == 0
    _definir(proj, "datadog", {"RF-10": fonte})                      # reinvestigado: mesma conclusão
    investigacao.preparar(proj)
    info = independente.preparar(proj, kb)
    volta = next(v for v in independente.carregar(proj) if (v["id"], v["fornecedor"]) == alvo)
    assert volta["na_amostra"] and volta["verificado"] and volta["resolucao"] == "manter" and not info["lotes"]


def test_duvida_com_id_numerico_nao_trava_nem_reabre_em_loop(cliente_proponente):
    proj = _preparar(cliente_proponente)
    caminho = _a(cliente_proponente, "02-analise", "duvidas.yaml")
    duv = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    duv.append({"id": 7, "pergunta": "Pergunta com id numérico?", "requisitos": ["RF-10"], "status": "RESPONDIDA",
                "resposta_cliente": "Sim."})
    caminho.write_text(yaml.safe_dump(duv, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _definir(proj, "datadog", {"RF-10": {"atendimento": "pleno", "evidencias": [], "ga": True}})
    investigacao.preparar(proj)
    dd = next(x for x in investigacao.carregar(proj) if x["id"] == "RF-10")["fornecedores"]["datadog"]
    assert dd["reabrir_por"] == ["7"] and dd["resposta_cliente"] == "7: Sim."
    _definir(proj, "datadog", {"RF-10": {"atendimento": "parcial"}})
    investigacao.preparar(proj)
    dd = next(x for x in investigacao.carregar(proj) if x["id"] == "RF-10")["fornecedores"]["datadog"]
    assert dd["investigado"] and dd["respostas_incorporadas"] == ["7"]


def test_registro_com_varias_urls_confere_as_citacoes(cliente_proponente, rede_falsa):
    from rfpkit import evidencias
    proj = _preparar(cliente_proponente)
    caminho = _a(cliente_proponente, "02-analise", "registro-evidencias.yaml")
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or []
    u1, u2 = "https://docs.exemplo.example/a", "https://docs.exemplo.example/b"
    rede_falsa.texto_mudou.update({u1, u2})
    dados.append({"id": "EV-0099", "alegacao": "Alegação de teste", "fonte": f"{u1} e {u2}",
                  "data_acesso": "2026-09-29", "citacoes": ["This sentence is not on any of the simulated pages"]})
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    kit.main(["validar-urls", str(cliente_proponente)])
    msgs = evidencias.validar_registro(proj, KB())
    assert any(n == "ERRO" and "EV-0099" in m and "CITACAO_AUSENTE" in m for n, m in msgs)


def test_isolar_lote_nao_sobrescreve(tmp_path):
    lote = tmp_path / "lote-01.json"
    lote.write_text("primeiro", encoding="utf-8")
    util.isolar_lote(lote)
    lote.write_text("segundo", encoding="utf-8")
    util.isolar_lote(lote)
    assert (tmp_path / "lote-01.json.invalido").read_text(encoding="utf-8") == "primeiro"
    assert (tmp_path / "lote-01.json.2.invalido").read_text(encoding="utf-8") == "segundo"
