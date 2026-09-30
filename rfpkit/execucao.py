"""Execução assistida no VS Code.

O kit é executado pela skill do GitHub Copilot no VS Code. A cada execução, o LLM:
1. atualiza a base de conhecimento dos fornecedores do campo (fatos, notas, evidências) e confere o Gartner MQ;
2. revisa TODOS os requisitos do edital (revisao-requisitos.json), transformando lacunas em perguntas de
   esclarecimento;
3. verifica as URLs citadas no estudo.

Este módulo confere se essas etapas aconteceram NESTA execução (com rfp.yaml -> execucao.assistida: true) e grava
o manifesto 02-analise/execucao.json. Sem elas a validação acusa ERRO e os entregáveis saem marcados como
PRELIMINAR.
"""
import datetime as dt
import os

from . import __version__, util


def ambiente() -> str:
    """vscode (terminal integrado/agente do VS Code) | copilot (agente do Copilot) | terminal."""
    env = os.environ
    if env.get("TERM_PROGRAM") == "vscode" or any(k.startswith("VSCODE_") for k in env):
        return "vscode"
    if any(k.startswith("COPILOT_") for k in env):
        return "copilot"
    return "terminal"


def config(projeto) -> dict:
    cfg = projeto.cfg.get("execucao") or {}
    return {"assistida": bool(cfg.get("assistida", True)), "kb_max_dias": int(cfg.get("kb_max_dias", 1))}


def fornecedores_do_campo(projeto) -> list:
    selecao = util.ler_json(projeto.dir_analise / "selecao.json") or {}
    ids = [t["id"] for t in selecao.get("triagem") or []]
    prop = projeto.cfg.get("proponente")
    if prop and prop not in ids:
        ids.append(prop)
    return ids


def _data(valor):
    try:
        return util.para_data(valor)
    except (ValueError, TypeError):
        return None


def estado(projeto, kb, hoje: dt.date | None = None) -> dict:
    from . import independente, investigacao, revisao, urls
    hoje = hoje or dt.date.today()
    cfg = config(projeto)
    limite = cfg["kb_max_dias"]

    def fresco(data):
        return bool(data and 0 <= (hoje - data).days <= limite)

    kb_forn = {}
    for fid in fornecedores_do_campo(projeto):
        data = _data((kb.fornecedores.get(fid) or {}).get("atualizado_em"))
        kb_forn[fid] = {"nome": kb.nome(fid), "atualizado_em": data.isoformat() if data else None, "ok": fresco(data)}
    gartner = _data(kb.gartner.get("revisado_em"))
    rev = revisao.cobertura(projeto)
    citadas = urls.alvos_do_estudo(projeto, kb)
    checagem = util.ler_csv(projeto.dir_analise / "validacao-urls.csv")
    verificadas = _data(checagem[0].get("verificado_em")) if checagem else None
    urls_ok = not citadas or (verificadas == hoje and {r.get("url") for r in checagem} >= set(citadas))
    inv = investigacao.cobertura(projeto)
    ind = independente.resumo(projeto)
    conf = (util.ler_json(projeto.dir_analise / "confianca.json", {}) or {}).get("resumo") or {}
    isolados = sorted(p.relative_to(projeto.dir_analise).as_posix()
                      for pasta in (revisao.dir_lotes(projeto), investigacao.dir_lotes(projeto),
                                    independente.dir_lotes(projeto)) if pasta.exists()
                      for p in pasta.rglob("*.invalido"))
    pendencias = []
    if cfg["assistida"]:
        pendencias += [f"KB de {v['nome']} não atualizada nesta execução (atualizado_em {v['atualizado_em'] or '—'})"
                       for v in kb_forn.values() if not v["ok"]]
        if not fresco(gartner):
            pendencias.append(f"Gartner MQ não revisado nesta execução (revisado_em {gartner or '—'})")
        if rev["pendentes"]:
            pendencias.append(f"{rev['pendentes']} de {rev['total']} requisitos sem revisão por LLM")
        if rev["lacunas_sem_duvida"]:
            pendencias.append(f"{len(rev['lacunas_sem_duvida'])} lacuna(s) sem pergunta de esclarecimento")
        if not urls_ok:
            pendencias.append("URLs citadas não verificadas nesta execução")
        if not inv["por_fornecedor"] and investigacao.requisitos_relevantes(projeto):
            pendencias.append("investigação requisito × fornecedor não iniciada")
        elif inv["pendentes"]:
            pendencias.append(f"{inv['pendentes']} avaliação(ões) requisito × fornecedor pendentes na investigação")
        if ind["pendentes"]:
            pendencias.append(f"{ind['pendentes']} verificação(ões) independente(s) pendente(s)")
        if ind["divergencias_abertas"]:
            pendencias.append(f"{ind['divergencias_abertas']} divergência(s) da verificação independente sem decisão")
        if isolados:
            pendencias.append(f"{len(isolados)} lote(s) ilegível(is) isolado(s) sem incorporar")
    return {"data": hoje.isoformat(), "ambiente": ambiente(), "kit": __version__, "assistida": cfg["assistida"],
            "kb_max_dias": limite, "kb": kb_forn,
            "gartner": {"revisado_em": gartner.isoformat() if gartner else None, "ok": fresco(gartner)},
            "revisao": rev, "urls": {"citadas": len(citadas), "verificadas_em": verificadas.isoformat() if verificadas else None,
                                     "ok": urls_ok},
            "investigacao": inv, "independente": ind, "confianca": conf, "lotes_isolados": isolados,
            "completa": cfg["assistida"] and not pendencias, "pendencias": pendencias}


def validar(projeto, kb) -> tuple[list, dict]:
    """[(nível, mensagem)] da execução assistida + o estado (também gravado em 02-analise/execucao.json)."""
    est = estado(projeto, kb)
    util.gravar_json(projeto.dir_analise / "execucao.json", est)
    if not est["assistida"]:
        return [], est
    prob = []
    if est["ambiente"] == "terminal":
        prob.append(("AVISO", "execução fora do VS Code/Copilot: as etapas de LLM (atualizar a KB, revisar os "
                              "requisitos, pesquisar evidências) só acontecem pela skill no VS Code"))
    for fid, v in est["kb"].items():
        if not v["ok"]:
            prob.append(("ERRO", f"KB de {v['nome']} não foi atualizada nesta execução (atualizado_em "
                                 f"{v['atualizado_em'] or '—'}; máximo {est['kb_max_dias']} dia(s)) — atualize pela "
                                 "skill (prompts/kb-pesquisar-fornecedor.md) e rode kb-validar-urls --atualizar"))
    if not est["gartner"]["ok"]:
        prob.append(("ERRO", "Gartner MQ não revisado nesta execução — confira se saiu edição nova "
                             "(prompts/kb-atualizar-gartner.md) e atualize 'revisado_em' em kb/gartner-mq.yaml"))
    rev = est["revisao"]
    if rev["pendentes"]:
        prob.append(("ERRO", f"{rev['pendentes']} de {rev['total']} requisitos sem revisão por LLM — "
                             "python kit.py revisar + prompts/14-revisar-requisitos.md + python kit.py revisar --consolidar"))
    if rev["lacunas_sem_duvida"]:
        prob.append(("ERRO", f"lacuna sem pergunta de esclarecimento em {', '.join(rev['lacunas_sem_duvida'][:10])} — "
                             "informe 'duvida_sugerida' (ou o id da dúvida) na revisão"))
    if not est["urls"]["ok"]:
        prob.append(("ERRO", "URLs citadas não verificadas nesta execução — python kit.py validar-urls "
                             "(o 'tudo' faz isso sozinho na execução assistida)"))
    inv, ind = est["investigacao"], est["independente"]
    if not inv["por_fornecedor"] and investigacao_relevante(projeto):
        prob.append(("ERRO", "investigação requisito × fornecedor não iniciada — python kit.py investigar + "
                             "prompts/15-investigar-requisitos.md + python kit.py investigar --consolidar"))
    elif inv["pendentes"]:
        prob.append(("ERRO", f"{inv['pendentes']} avaliação(ões) requisito × fornecedor pendentes — "
                             "python kit.py investigar (lotes por fornecedor, prompts/15) e --consolidar"))
    if ind["pendentes"]:
        prob.append(("ERRO", f"{ind['pendentes']} verificação(ões) independente(s) pendente(s) — "
                             "python kit.py verificar-independente + prompts/16 (outro modelo) + --consolidar"))
    if ind["divergencias_abertas"]:
        prob.append(("ERRO", f"{ind['divergencias_abertas']} divergência(s) da verificação independente sem decisão — "
                             "apresente ao usuário e registre resolucao (manter/corrigir) em verificacao-independente.json"))
    if est["lotes_isolados"]:
        prob.append(("ERRO", f"lote(s) ilegível(is) não incorporado(s): {', '.join(est['lotes_isolados'][:5])} — corrija o "
                             "JSON e renomeie de volta para .json (ou apague para descartar) e rode de novo"))
    return prob, est


def investigacao_relevante(projeto) -> bool:
    from .investigacao import requisitos_relevantes
    return bool(requisitos_relevantes(projeto))
