"""Verificação independente: um segundo agente — de preferência outro modelo — reavalia uma amostra das avaliações
SEM ver a conclusão do primeiro (só o requisito e as evidências citadas) e diz se a evidência sustenta o atendimento.

Amostra (reprodutível): 100% dos eliminatórios do proponente (modo proponente) ou dos 3 primeiros do ranking (modo
neutro), 100% das respostas plenas do proponente e uma parcela aleatória do restante (padrão 20% para esses
fornecedores e 10% para os demais; rfp.yaml -> verificacao_independente).

- 02-analise/verificacao-independente/lote-NN.json — lotes cegos para os subagentes (prompts/16)
- 02-analise/verificacao-independente.json — consolidado: segunda opinião, divergência e resolução humana

Divergência (atendimento diferente, evidência que não sustenta, ou sustenta só em parte uma resposta plena) rebaixa a
confiança até alguém decidir: resolucao "manter" (a primeira conclusão fica, com justificativa) ou "corrigir"
(a investigação é refeita e a verificação volta para a fila). Uma verificação feita continua valendo enquanto a
conclusão verificada for a mesma, mesmo que o item saia da amostra (na_amostra: false); se a conclusão sumir ou mudar,
ela fica guardada como suspensa e volta a valer se a mesma conclusão voltar.
"""
import hashlib

from . import util

CONFERE = ("sim", "parcial", "nao")
CAMPOS = ("atendimento", "confere_evidencia", "obs", "modelo", "verificado")
PADRAO = {"aleatoria_pct": 20, "outros_pct": 10}


def arquivo(projeto):
    return projeto.dir_analise / "verificacao-independente.json"


def dir_lotes(projeto):
    return projeto.dir_analise / "verificacao-independente"


def carregar(projeto) -> list:
    dados = util.ler_json(arquivo(projeto), []) or []
    return [v for v in dados if isinstance(v, dict)] if isinstance(dados, list) else []


def _sorteio(projeto, rid: str, fid: str) -> int:
    chave = f"{projeto.sigla}|{rid}|{fid}".encode("utf-8")
    return int(hashlib.sha256(chave).hexdigest()[:8], 16) % 100


def _foco(projeto) -> list:
    """Fornecedores com cobertura total dos eliminatórios: o proponente ou os 3 primeiros do ranking."""
    prop = projeto.cfg.get("proponente")
    if projeto.cfg.get("modo") == "proponente" and prop:
        return [prop]
    ranking = util.ler_json(projeto.dir_analise / "ranking.json") or {}
    return [l["fornecedor"] for l in (ranking.get("ranking") or [])[:3]]


def amostra(projeto, itens: list) -> list:
    cfg = {**PADRAO, **(projeto.cfg.get("verificacao_independente") or {})}
    foco = set(_foco(projeto))
    prop = projeto.cfg.get("proponente") if projeto.cfg.get("modo") == "proponente" else None
    escolhidos = []
    for a in itens:
        if not a.get("atendimento"):
            continue
        fid = a["fornecedor"]
        motivo = None
        if fid in foco and a.get("obrigatoriedade") == "eliminatorio":
            motivo = "eliminatório"
        elif fid == prop and a.get("atendimento") == "pleno":
            motivo = "resposta plena do proponente"
        elif _sorteio(projeto, a["id"], fid) < (cfg["aleatoria_pct"] if fid in foco else cfg["outros_pct"]):
            motivo = "amostra aleatória"
        if motivo:
            escolhidos.append((a, motivo))
    return escolhidos


def impressao(a: dict) -> str:
    """Identifica a conclusão verificada (atendimento + evidências): se mudar, a verificação não vale mais."""
    evs = a.get("evidencias") if isinstance(a.get("evidencias"), list) else []
    return f"{a.get('atendimento')}|{','.join(sorted(map(str, evs)))}"


def _evidencias_cegas(a: dict, kb) -> list:
    from .urls import citacoes_da_evidencia
    saida = []
    for ev in a.get("evidencias") or []:
        e = kb.evidencia(ev)
        if e:
            saida.append({"ref": ev, "url": e.get("url"), "citacoes": citacoes_da_evidencia(e)})
        else:
            saida.append({"ref": ev, "url": str(ev), "citacoes": a.get("citacoes") or []})
    return saida


def divergente(v: dict) -> bool:
    if not v.get("verificado"):
        return False
    primeiro = (v.get("primeiro") or {}).get("atendimento")
    return (v.get("atendimento") != primeiro or v.get("confere_evidencia") == "nao"
            or (v.get("confere_evidencia") == "parcial" and primeiro == "pleno"))


def _rechavear(projeto, registros: list) -> list:
    """Errata que renumera requisitos: a verificação acompanha o texto do requisito para o novo id (se único)."""
    rtm = (util.ler_json(projeto.dir_projeto / "rtm.json") or {}).get("requisitos") or []
    texto_por_id = {r["id"]: util.norm(r["texto"]) for r in rtm}
    por_texto = {}
    for r in rtm:
        por_texto.setdefault(util.norm(r["texto"]), []).append(r["id"])
    for v in registros:
        texto = util.norm(v.get("requisito") or "")
        if texto_por_id.get(v.get("id")) == texto:
            continue
        novos = por_texto.get(texto) or []
        if len(novos) == 1:
            v["id"] = novos[0]
    return registros


def preparar(projeto, kb, tamanho: int = 30) -> dict:
    """Incorpora os lotes preenchidos, sorteia a amostra e gera os lotes cegos dos pendentes. Cada verificação fica
    guardada com a conclusão que verificou ('impressao'): volta a valer se a mesma conclusão voltar (item reaberto por
    resposta do cliente, fornecedor que saiu e voltou do campo) e é ignorada enquanto a conclusão for outra."""
    from .confianca import avaliacoes_do_estudo
    from .revisao import carregar as carregar_revisao
    todos = _rechavear(projeto, carregar(projeto))
    pendentes = {(v.get("id"), v.get("fornecedor")): v for v in todos
                 if v.get("na_amostra") is not False and not v.get("verificado")}
    problemas, ruins = [], []
    for lote in sorted(dir_lotes(projeto).glob("lote-*.json")):
        dados, erro = util.ler_lote(lote)
        if erro:
            problemas.append(f"{lote.name}: {erro} — isolado como .invalido")
            ruins.append(lote)
            continue
        for r in dados:
            v = pendentes.get((r.get("id"), r.get("fornecedor")))
            if v:
                v.update({k: r[k] for k in CAMPOS if k in r})
    por_impressao = {}
    for v in todos:
        chave = (v.get("id"), v.get("fornecedor"), v.get("impressao"))
        if v.get("verificado") or chave not in por_impressao:
            por_impressao[chave] = v
    revisao = {i["id"]: i for i in carregar_revisao(projeto)}
    itens = avaliacoes_do_estudo(projeto, kb)
    idx = {(a["id"], a["fornecedor"]): a for a in itens}
    registros, usados = [], set()
    for a, motivo in amostra(projeto, itens):
        chave = (a["id"], a["fornecedor"], impressao(a))
        ant = por_impressao.get(chave) or {}
        base = {"atendimento": a.get("atendimento"), "evidencias": a.get("evidencias") or [], "modelo": a.get("modelo") or ""}
        v = {"id": a["id"], "fornecedor": a["fornecedor"], "motivo_amostra": motivo, "requisito": a.get("requisito"),
             "obrigatoriedade": a.get("obrigatoriedade"), "primeiro": ant.get("primeiro") or base,
             "impressao": chave[2], "na_amostra": True}
        if ant:
            v.update({k: ant.get(k) for k in CAMPOS if k in ant})
            v.update({k: ant[k] for k in ("resolucao", "resolucao_obs", "resolvido_por") if ant.get(k)})
        else:
            v.update({"atendimento": "", "confere_evidencia": "", "obs": "", "modelo": "", "verificado": False})
        v["divergente"] = divergente(v)
        registros.append(v)
        usados.add(chave)
    for chave, ant in por_impressao.items():
        if chave in usados or not ant.get("verificado"):
            continue
        a = idx.get(chave[:2])
        registros.append({**ant, "na_amostra": False, "suspensa": not (a and impressao(a) == chave[2]),
                          "divergente": divergente(ant)})
    util.gravar_json(arquivo(projeto), registros)
    pasta = dir_lotes(projeto)
    pasta.mkdir(parents=True, exist_ok=True)
    for lote in ruins:
        util.isolar_lote(lote)
    for antigo in pasta.glob("lote-*.json"):
        antigo.unlink()
    pend = [v for v in registros if not v.get("verificado")]
    lotes = []
    for n, ini in enumerate(range(0, len(pend), max(1, int(tamanho))), start=1):
        cegos = []
        for v in pend[ini:ini + max(1, int(tamanho))]:
            a = idx[(v["id"], v["fornecedor"])]
            rev = revisao.get(v["id"]) or {}
            cegos.append({"id": v["id"], "fornecedor": v["fornecedor"], "requisito": v["requisito"],
                          "entendimento": rev.get("entendimento") or "", "parametros": rev.get("parametros") or "",
                          "evidencias": _evidencias_cegas(a, kb), "atendimento": "", "confere_evidencia": "",
                          "obs": "", "modelo": "", "verificado": False})
        destino = pasta / f"lote-{n:02d}.json"
        util.gravar_json(destino, cegos)
        lotes.append(destino)
    return {"lotes": lotes, "problemas": problemas, **resumo(projeto)}


def resumo(projeto) -> dict:
    """Amostra, pendências e concordância contam só a amostra atual; divergências abertas contam também as
    verificações da conclusão atual de itens que saíram da amostra (as suspensas — conclusão ausente ou outra — não)."""
    todos = carregar(projeto)
    regs = [v for v in todos if v.get("na_amostra") is not False]
    verificados = [v for v in regs if v.get("verificado")]
    divergentes = [v for v in verificados if v.get("divergente")]
    abertas = [v for v in todos if v.get("verificado") and v.get("divergente") and v.get("resolucao") != "manter"
               and not v.get("suspensa")]
    return {"amostra": len(regs), "verificados": len(verificados), "pendentes": len(regs) - len(verificados),
            "divergentes": len(divergentes), "divergencias_abertas": len(abertas),
            "concordancia_pct": round(100 * (len(verificados) - len(divergentes)) / len(verificados), 1) if verificados else None}


def validar(projeto) -> list:
    prob = []
    for v in carregar(projeto):
        if not v.get("verificado"):
            continue
        rot = f"verificação independente {v['id']} × {v['fornecedor']}"
        if v.get("atendimento") not in ("pleno", "parcial", "nao", "na"):
            prob.append(("ERRO", f"{rot}: atendimento '{v.get('atendimento')}' inválido"))
        if v.get("confere_evidencia") not in CONFERE:
            prob.append(("ERRO", f"{rot}: confere_evidencia '{v.get('confere_evidencia')}' fora de {'/'.join(CONFERE)}"))
        modelo1 = util.norm((v.get("primeiro") or {}).get("modelo"))
        if modelo1 and modelo1 == util.norm(v.get("modelo")):
            prob.append(("AVISO", f"{rot}: feita com o mesmo modelo da investigação ({v.get('modelo')}) — use outro modelo"))
        if v.get("resolucao") and v["resolucao"] not in ("manter", "corrigir"):
            prob.append(("ERRO", f"{rot}: resolucao '{v['resolucao']}' (use manter ou corrigir)"))
        if v.get("resolucao") == "manter" and not str(v.get("resolucao_obs") or "").strip():
            prob.append(("ERRO", f"{rot}: 'manter' exige justificativa em resolucao_obs"))
    r = resumo(projeto)
    minimo = float((projeto.cfg.get("verificacao_independente") or {}).get("concordancia_min", 85))
    if r["concordancia_pct"] is not None and r["concordancia_pct"] < minimo:
        prob.append(("AVISO", f"concordância da verificação independente {util.br(r['concordancia_pct'])}% (< "
                              f"{util.br(minimo, 0)}%): revise o método da investigação antes de confiar no resultado"))
    return prob
