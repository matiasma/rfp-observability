"""Execução assistida no VS Code: a cada execução a KB do campo e o Gartner precisam estar atualizados, todos os
requisitos revisados por LLM (lacunas viram dúvidas) e as URLs verificadas — senão ERRO e entregáveis PRELIMINAR."""
import datetime as dt
import json
import os
from pathlib import Path

import yaml
from docx import Document

import kit
from rfpkit import execucao, revisao
from rfpkit.config import Projeto
from rfpkit.kb import KB


def _a(pasta, *partes):
    return pasta.joinpath("_analise-rfp", *partes)


def _assistida(pasta):
    cfg = _a(pasta, "rfp.yaml")
    t = cfg.read_text(encoding="utf-8").replace("execucao:\n  assistida: false", "execucao:\n  assistida: true")
    cfg.write_text(t, encoding="utf-8")


def _revisar_tudo(pasta, lacuna_em=None):
    """Simula os subagentes: preenche todos os lotes e consolida."""
    for lote in sorted(_a(pasta, "02-analise", "revisao").glob("lote-*.json")):
        itens = json.loads(lote.read_text(encoding="utf-8"))
        for i in itens:
            i.update({"entendimento": f"Exige {i['requisito'][:40]}", "clareza": "clara", "revisado": True})
            if i["id"] == lacuna_em:
                i.update({"clareza": "incompleta", "lacuna": "volume diário não informado",
                          "duvida_sugerida": "Qual o volume diário de logs esperado no primeiro ano?"})
        lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    assert kit.main(["revisar", str(pasta), "--consolidar"]) == 0


def _reabrir_revisao(pasta, rid):
    caminho = _a(pasta, "02-analise", "revisao-requisitos.json")
    itens = json.loads(caminho.read_text(encoding="utf-8"))
    for i in itens:
        if i["id"] == rid:
            i["revisado"] = False
    caminho.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")


def _citacao_da_kb():
    from rfpkit.urls import citacoes_da_evidencia
    return citacoes_da_evidencia(KB().evidencia("EV-AZ-002"))[0]


def _investigar_tudo(pasta):
    """Simula os subagentes da investigação: o proponente segue as respostas; os concorrentes 'pleno' com URL oficial
    e citação literal (a página simulada contém as citações da KB)."""
    from rfpkit.respostas import nivel
    respostas = {r["id"]: r for r in json.loads(_a(pasta, "02-analise", "respostas.json").read_text(encoding="utf-8"))}
    prop = yaml.safe_load(_a(pasta, "rfp.yaml").read_text(encoding="utf-8"))["proponente"]
    citacao = _citacao_da_kb()
    for lote in sorted(_a(pasta, "02-analise", "investigacao").glob("*/lote-*.json")):
        itens = json.loads(lote.read_text(encoding="utf-8"))
        for i in itens:
            if i["fornecedor"] == prop:
                r = respostas[i["id"]]
                i.update({"atendimento": nivel(r["resposta"], r["escala"]), "como": "nativo", "ga": True,
                          "evidencias": r.get("evidencias") or [], "cobre_parametro": "sim", "investigado": True,
                          "modelo": "modelo-a"})
            else:
                i.update({"atendimento": "pleno", "como": "nativo", "ga": True, "evidencias": [f"https://docs.{i['fornecedor']}.example/doc"],
                          "citacoes": [citacao], "cobre_parametro": "sim", "investigado": True, "modelo": "modelo-a"})
        lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    assert kit.main(["investigar", str(pasta), "--consolidar"]) == 0


def _verificar_independente(pasta, divergir=None):
    """Simula o segundo agente: concorda com a primeira conclusão (exceto o item em 'divergir')."""
    regs = {(v["id"], v["fornecedor"]): v for v in
            json.loads(_a(pasta, "02-analise", "verificacao-independente.json").read_text(encoding="utf-8"))}
    for lote in sorted(_a(pasta, "02-analise", "verificacao-independente").glob("lote-*.json")):
        itens = json.loads(lote.read_text(encoding="utf-8"))
        for i in itens:
            primeiro = regs[(i["id"], i["fornecedor"])]["primeiro"]["atendimento"]
            i.update({"atendimento": primeiro, "confere_evidencia": "sim", "modelo": "modelo-b", "verificado": True})
            if (i["id"], i["fornecedor"]) == divergir:
                i.update({"atendimento": "nao", "confere_evidencia": "nao", "obs": "a página não cita o recurso"})
        lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    assert kit.main(["verificar-independente", str(pasta), "--consolidar"]) == 0


def test_init_cria_workspace_do_vscode_e_execucao_assistida(tmp_path):
    import gerar_exemplo
    pasta = gerar_exemplo.gerar(tmp_path / "novo")
    assert kit.main(["init", str(pasta), "--sigla", "NOVO"]) == 0
    cfg = yaml.safe_load(_a(pasta, "rfp.yaml").read_text(encoding="utf-8"))
    assert cfg["execucao"]["assistida"] is True
    ws = json.loads((pasta / "NOVO-analise-rfp.code-workspace").read_text(encoding="utf-8"))
    caminhos = [f["path"] for f in ws["folders"]]
    assert caminhos[0] == "."
    assert Path(caminhos[1], ".github", "skills", "analise-rfp-observabilidade", "SKILL.md").exists()
    assert "github.copilot-chat" in ws["extensions"]["recommendations"]


def test_execucao_assistida_incompleta_gera_erros_e_preliminar(cliente_proponente, rede_falsa, monkeypatch):
    _assistida(cliente_proponente)
    monkeypatch.setattr(execucao, "ambiente", lambda: "terminal")
    assert kit.main(["tudo", str(cliente_proponente)]) == 1
    val = _a(cliente_proponente, "02-analise", "validacao.md").read_text(encoding="utf-8")
    assert "execução fora do VS Code" in val and "requisito × fornecedor pendentes" in val
    assert "verificação(ões) independente(s) pendente(s)" in val
    estado = json.loads(_a(cliente_proponente, "02-analise", "execucao.json").read_text(encoding="utf-8"))
    assert estado["assistida"] and not estado["completa"] and estado["urls"]["ok"]      # URLs verificadas sozinhas
    lotes = list(_a(cliente_proponente, "02-analise", "investigacao").glob("*/lote-*.json"))
    assert len({l.parent.name for l in lotes}) >= 2                                     # lotes por fornecedor
    html = _a(cliente_proponente, "03-entregas", "relatorio-exemplo-prop.html").read_text(encoding="utf-8")
    assert "PRELIMINAR — execução assistida incompleta" in html
    sumario = Document(str(_a(cliente_proponente, "03-entregas", "Sumario-Executivo-exemplo-prop.docx")))
    assert any(par.text.startswith("PRELIMINAR") for par in sumario.paragraphs[:4])
    indice = _a(cliente_proponente, "03-entregas", "README-ENTREGAS.md").read_text(encoding="utf-8")
    assert "PRELIMINAR — execução assistida incompleta" in indice


def test_revisao_completa_com_lacuna_vira_duvida_e_execucao_completa(cliente_proponente, rede_falsa, monkeypatch):
    _assistida(cliente_proponente)
    monkeypatch.setattr(execucao, "ambiente", lambda: "vscode")
    hoje = dt.date.today().isoformat()
    monkeypatch.setattr(KB, "__init__", _kb_fresca(KB.__init__, hoje))
    _reabrir_revisao(cliente_proponente, "DQ-2")
    kit.main(["tudo", str(cliente_proponente)])                                        # RTM, lotes de revisão e investigação
    _revisar_tudo(cliente_proponente, lacuna_em="DQ-2")
    duv = yaml.safe_load(_a(cliente_proponente, "02-analise", "duvidas.yaml").read_text(encoding="utf-8"))
    nova = [d for d in duv if d.get("origem") == "revisao-llm"]
    assert len(nova) == 1 and nova[0]["id"] == "DUV-004" and nova[0]["requisitos"] == ["DQ-2"]
    _investigar_tudo(cliente_proponente)
    kit.main(["tudo", str(cliente_proponente)])                                        # amostra da verificação independente
    _verificar_independente(cliente_proponente)
    assert kit.main(["tudo", str(cliente_proponente)]) == 0
    estado = json.loads(_a(cliente_proponente, "02-analise", "execucao.json").read_text(encoding="utf-8"))
    assert estado["completa"] and estado["revisao"]["pendentes"] == 0 and estado["revisao"]["com_lacuna"] == 4
    assert estado["investigacao"]["pendentes"] == 0 and estado["independente"]["concordancia_pct"] == 100.0
    enviadas = _a(cliente_proponente, "03-entregas", "Anexo-Duvidas-Exemplo - PREENCHIDO.xlsx")
    assert enviadas.exists()
    indice = _a(cliente_proponente, "03-entregas", "README-ENTREGAS.md").read_text(encoding="utf-8")
    assert "Execução assistida completa" in indice


def _kb_fresca(original, hoje):
    """KB com atualizado_em/revisado_em = hoje (simula a atualização feita pelos subagentes nesta execução)."""
    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        for f in self.fornecedores.values():
            f["atualizado_em"] = hoje
        self.gartner["revisado_em"] = hoje
    return init


def test_kb_desatualizada_e_lacuna_sem_duvida_sao_erros(cliente_proponente, monkeypatch):
    _assistida(cliente_proponente)
    kit.main(["rtm", str(cliente_proponente)]); kit.main(["pesos", str(cliente_proponente)])
    kit.main(["ranking", str(cliente_proponente)])
    assert kit.main(["revisar", str(cliente_proponente)]) == 0
    proj = Projeto(cliente_proponente)
    itens = revisao.carregar(proj)
    itens[0].update({"revisado": True, "entendimento": "x", "clareza": "ambigua", "lacuna": "termo sem definição"})
    (proj.dir_analise / "revisao-requisitos.json").write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    for lote in (proj.dir_analise / "revisao").glob("lote-*.json"):
        lote.unlink()
    kb = KB()
    for f in kb.fornecedores.values():
        f["atualizado_em"] = "2020-01-01"
    msgs, estado = execucao.validar(proj, kb)
    texto = "\n".join(m for _, m in msgs)
    assert "KB de Azure Monitor não foi atualizada nesta execução" in texto
    assert f"lacuna sem pergunta de esclarecimento em {itens[0]['id']}" in texto
    assert not estado["completa"]


def test_revisao_aplica_correcoes_na_rtm_e_preserva_lotes(cliente_exemplo):
    kit.main(["rtm", str(cliente_exemplo)])
    proj = Projeto(cliente_exemplo)
    info = revisao.preparar(proj, tamanho=10)
    assert info["pendentes"] == info["total"] and len(info["lotes"]) == -(-info["total"] // 10)
    lote = info["lotes"][0]
    itens = json.loads(lote.read_text(encoding="utf-8"))
    alvo = itens[0]
    alvo.update({"categoria": "aiops", "natureza": "tecnico", "entendimento": "x", "clareza": "clara", "revisado": True})
    itens[1].update({"entendimento": "rascunho sem concluir"})                          # parcial: não pode se perder
    lote.write_text(json.dumps(itens, ensure_ascii=False), encoding="utf-8")
    info = revisao.preparar(proj, tamanho=10)                                           # rodar de novo antes de consolidar
    assert info["revisados"] == 1
    parcial = next(i for i in revisao.carregar(proj) if i["id"] == itens[1]["id"])
    assert parcial["entendimento"] == "rascunho sem concluir" and not parcial["revisado"]
    kit.main(["rtm", str(cliente_exemplo)])
    rtm = json.loads(_a(cliente_exemplo, "00-projeto", "rtm.json").read_text(encoding="utf-8"))
    req = next(r for r in rtm["requisitos"] if r["id"] == alvo["id"])
    assert req["categoria"] == "aiops" and req["origem_classificacao"] == "revisao-llm"
    assert req["categoria_auto"] == alvo["automatico"]["categoria"]


def test_ambiente_detectado(monkeypatch):
    for k in list(os.environ):
        if k.startswith(("VSCODE_", "COPILOT_")) or k == "TERM_PROGRAM":
            monkeypatch.delenv(k, raising=False)
    assert execucao.ambiente() == "terminal"
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    assert execucao.ambiente() == "vscode"
