"""Investigação requisito × fornecedor (execução assistida no VS Code).

Para cada requisito que pesa na aderência e cada fornecedor da avaliação completa, um subagente do LLM (um por
fornecedor e lote, prompts/15-investigar-requisitos.md) registra: atendimento, como (nativo, configuração, extensão,
terceiro, desenvolvimento), se é GA, evidências oficiais (EV-… da KB ou URL) com citação literal, se a fonte cobre o
parâmetro pedido, conflitos entre fontes e a lacuna tipificada com o encaminhamento (dúvida ao cliente, pergunta ao
fabricante ou item de POC).

- 02-analise/investigacao.json — consolidado (requisito → fornecedor → avaliação); avaliações de fornecedores que
  saíram da avaliação completa ficam em 'fora_do_campo' e voltam se o fornecedor voltar
- 02-analise/investigacao-arquivo.json — avaliações de requisitos que saíram do escopo (voltam com o mesmo texto)
- 02-analise/investigacao/<fornecedor>/lote-NN.json — lotes pendentes para os subagentes

A aderência de quem está na avaliação completa passa a ser calculada item a item; a nota da categoria na KB (ou o
ajuste do estudo) só cobre os itens ainda não investigados.
"""
import datetime as dt

from . import util
from .classificacao import NAO_CLASSIFICADO

ATENDIMENTOS = ("pleno", "parcial", "nao", "na")
COMO = ("nativo", "configuracao", "extensao", "terceiro", "desenvolvimento")
COBRE = ("sim", "parcial", "nao", "na")
TIPOS_LACUNA = ("cliente", "documentacao", "conflito")
CAMPOS = ("atendimento", "como", "ga", "evidencias", "citacoes", "cobre_parametro", "conflito", "justificativa",
          "lacuna", "tipo_lacuna", "duvida_sugerida", "duvida", "pergunta_fabricante", "poc", "modelo", "investigado",
          "investigado_em")
CAMPOS_KIT = ("reabrir", "reabrir_por", "respostas_incorporadas", "resposta_cliente")
VAZIO = {"atendimento": "", "como": "", "ga": None, "evidencias": [], "citacoes": [], "cobre_parametro": "",
         "conflito": False, "justificativa": "", "lacuna": "", "tipo_lacuna": "", "duvida_sugerida": "", "duvida": "",
         "pergunta_fabricante": "", "poc": False, "modelo": "", "investigado": False, "investigado_em": ""}


def arquivo(projeto):
    return projeto.dir_analise / "investigacao.json"


def arquivo_morto(projeto):
    return projeto.dir_analise / "investigacao-arquivo.json"


def dir_lotes(projeto):
    return projeto.dir_analise / "investigacao"


def _lista_json(caminho) -> list:
    dados = util.ler_json(caminho, []) or []
    return [e for e in dados if isinstance(e, dict) and e.get("id")] if isinstance(dados, list) else []


def carregar(projeto) -> list:
    return _lista_json(arquivo(projeto))


def requisitos_relevantes(projeto, rtm: dict | None = None) -> list:
    """Requisitos que entram nos pesos (natureza considerada, categoria de produto, classificados)."""
    rtm = rtm or util.ler_json(projeto.dir_projeto / "rtm.json") or {"requisitos": []}
    pesos = projeto.cfg.get("pesos") or {}
    naturezas = set(pesos.get("naturezas") or [])
    excluidas = set(pesos.get("categorias_excluidas") or [])
    return [r for r in rtm["requisitos"] if r["natureza"] in naturezas and r["categoria"] not in excluidas
            and r["categoria"] != NAO_CLASSIFICADO]


def fornecedores(projeto) -> list:
    ranking = util.ler_json(projeto.dir_analise / "ranking.json") or {}
    ids = list(ranking.get("avaliacao_completa") or [])
    prop = projeto.cfg.get("proponente")
    if projeto.cfg.get("modo") == "proponente" and prop and prop not in ids:
        ids.insert(0, prop)
    return ids


def _mesmo(a, b) -> bool:
    return util.norm(a or "") == util.norm(b or "")


def _hoje() -> str:
    return dt.date.today().isoformat()


def _tem_trabalho(a) -> bool:
    return isinstance(a, dict) and (bool(a.get("investigado")) or any(a.get(k) != VAZIO[k] for k in CAMPOS if k in a))


def _mesclar_lote_item(atual: dict, r: dict) -> int:
    """Item concluído no lote (investigado: true) vale inteiro — inclusive para limpar campos; item parcial só
    acrescenta o que foi preenchido (um lote antigo não apaga o consolidado)."""
    concluido = r.get("investigado") is True
    mudou = 0
    for k in CAMPOS:
        if k not in r:
            continue
        if (concluido or r[k] != VAZIO.get(k)) and r[k] != atual.get(k):
            atual[k] = r[k]
            mudou += 1
    return mudou


def _mesclar_lotes(projeto, entradas: list, problemas: list) -> tuple[int, list]:
    idx = {e["id"]: e for e in entradas}
    aplicados, ruins = 0, []
    for lote in sorted(dir_lotes(projeto).glob("*/lote-*.json")):
        itens, erro = util.ler_lote(lote)
        if erro:
            problemas.append(f"{lote.parent.name}/{lote.name}: {erro} — isolado como .invalido")
            ruins.append(lote)
            continue
        for r in itens:
            e = idx.get(r.get("id"))
            fid = r.get("fornecedor")
            if not e or not fid or not _mesmo(e.get("requisito"), r.get("requisito")):
                continue
            destino = (e.setdefault("fornecedores", {}).get(fid) or (e.get("fora_do_campo") or {}).get(fid))
            if destino is None:
                destino = e["fornecedores"].setdefault(fid, dict(VAZIO))
            aplicados += _mesclar_lote_item(destino, r)
    return aplicados, ruins


def preparar(projeto, tamanho: int = 30) -> dict:
    """Incorpora os lotes já preenchidos, sincroniza com a RTM e o campo avaliado (sem perder avaliações de quem saiu
    do escopo), aplica o ciclo de respostas do cliente, cria as dúvidas sugeridas e gera novos lotes (por fornecedor)
    só com os pendentes."""
    from .duvidas import ciclo_resposta, ligadas_por_requisito, respondidas
    from .revisao import carregar as carregar_revisao, criar_duvidas
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json")
    if not rtm:
        raise RuntimeError("rtm.json não encontrado — rode 'python kit.py rtm' antes.")
    problemas = []
    anteriores = carregar(projeto)
    morto = _lista_json(arquivo_morto(projeto))
    aplicados, ruins = _mesclar_lotes(projeto, anteriores, problemas)
    por_id = {e["id"]: e for e in anteriores}
    guardadas = {}
    for e in morto + anteriores:                       # o consolidado prevalece sobre o arquivo
        guardadas[(e["id"], util.norm(e.get("requisito") or ""))] = e
    exatos = {(r["id"], util.norm(r["texto"])) for r in rtm["requisitos"]}
    por_texto = {}                                     # errata que renumera: a investigação segue o texto
    for k in guardadas:
        if k not in exatos:
            por_texto.setdefault(k[1], []).append(k)
    revisao = {i["id"]: i for i in carregar_revisao(projeto)}
    resp, ligadas, hoje = respondidas(projeto), ligadas_por_requisito(projeto), _hoje()
    campo = fornecedores(projeto)
    entradas, usados, reabertas = [], set(), 0
    for req in requisitos_relevantes(projeto, rtm):
        chave = (req["id"], util.norm(req["texto"]))
        ant = por_id.get(req["id"])
        if not (ant and _mesmo(ant.get("requisito"), req["texto"])):
            ant = guardadas.get(chave)
        if not ant:
            cand = [k for k in por_texto.get(chave[1], []) if k not in usados]
            ant = guardadas[cand[0]] if len(cand) == 1 else None
        if ant:
            usados.add((ant["id"], util.norm(ant.get("requisito") or "")))
        ids_ant = set((ant or {}).get("ids_anteriores") or []) | ({ant["id"]} if ant else set())
        ids_ant.discard(req["id"])
        dentro = dict((ant or {}).get("fornecedores") or {})
        fora = dict((ant or {}).get("fora_do_campo") or {})
        rev = revisao.get(req["id"]) or {}
        entrada = {"id": req["id"], "requisito": req["texto"], "categoria": req["categoria"],
                   "obrigatoriedade": req["obrigatoriedade"], "fonte": req["fonte"], "localizacao": req["localizacao"],
                   "entendimento": rev.get("entendimento") or "", "parametros": rev.get("parametros") or "",
                   "fornecedores": {}}
        if ids_ant:
            entrada["ids_anteriores"] = sorted(ids_ant)
        for fid in campo:
            fonte = dentro.get(fid) if isinstance(dentro.get(fid), dict) else fora.get(fid)
            aval = dict(VAZIO)
            if isinstance(fonte, dict):
                aval.update({k: v for k, v in fonte.items() if k in CAMPOS or k in CAMPOS_KIT})
            reabertas += 1 if ciclo_resposta(aval, "investigado", "investigado_em", [req["id"], *sorted(ids_ant)],
                                             resp, ligadas, hoje) else 0
            entrada["fornecedores"][fid] = aval
        saiu = {fid: a for fid, a in {**fora, **dentro}.items() if fid not in campo and _tem_trabalho(a)}
        if saiu:
            entrada["fora_do_campo"] = saiu
        entradas.append(entrada)
        usados.add(chave)
    planos = [{"id": e["id"], "fonte": e["fonte"], "localizacao": e["localizacao"],
               "obrigatoriedade": e["obrigatoriedade"], "categoria": e["categoria"], "fornecedor": fid, "a": a,
               "duvida_sugerida": a.get("duvida_sugerida"), "duvida": a.get("duvida"), "lacuna": a.get("lacuna")}
              for e in entradas for fid, a in e["fornecedores"].items()
              if str(a.get("tipo_lacuna") or "") in ("cliente", "conflito", "")]
    novas = criar_duvidas(projeto, planos, origem="investigacao-llm")
    for p in planos:
        if p.get("duvida"):
            p["a"]["duvida"] = p["duvida"]
    util.gravar_json(arquivo(projeto), entradas)
    arquivar = {}
    for chave, e in guardadas.items():
        if chave not in usados and any(_tem_trabalho(a) for a in list((e.get("fornecedores") or {}).values())
                                       + list((e.get("fora_do_campo") or {}).values())):
            arquivar[chave] = e
    if arquivar or arquivo_morto(projeto).exists():
        util.gravar_json(arquivo_morto(projeto), list(arquivar.values()))

    pasta = dir_lotes(projeto)
    pasta.mkdir(parents=True, exist_ok=True)
    for lote in ruins:
        util.isolar_lote(lote)
    for antigo in pasta.glob("*/lote-*.json"):
        antigo.unlink()
    tamanho = max(1, int(tamanho))
    lotes = []
    for fid in campo:
        pend = []
        for e in entradas:
            a = e["fornecedores"][fid]
            if a.get("investigado"):
                continue
            item = {"id": e["id"], "requisito": e["requisito"], "categoria": e["categoria"],
                    "obrigatoriedade": e["obrigatoriedade"], "entendimento": e["entendimento"],
                    "parametros": e["parametros"], "fornecedor": fid, **{k: a.get(k, VAZIO[k]) for k in CAMPOS}}
            for k in ("reabrir", "resposta_cliente"):
                if a.get(k):
                    item[k] = a[k]
            pend.append(item)
        for n, ini in enumerate(range(0, len(pend), tamanho), start=1):
            destino = pasta / fid / f"lote-{n:02d}.json"
            destino.parent.mkdir(parents=True, exist_ok=True)
            util.gravar_json(destino, pend[ini:ini + tamanho])
            lotes.append(destino)
    return {"requisitos": len(entradas), "fornecedores": campo, "aplicados": aplicados, "reabertas": reabertas,
            "duvidas_criadas": novas, "lotes": lotes, "problemas": problemas, "arquivadas": len(arquivar),
            **cobertura(projeto)}


def cobertura(projeto) -> dict:
    por_forn = {}
    for e in carregar(projeto):
        for fid, a in (e.get("fornecedores") or {}).items():
            if not isinstance(a, dict):
                continue
            c = por_forn.setdefault(fid, {"total": 0, "investigados": 0})
            c["total"] += 1
            c["investigados"] += 1 if a.get("investigado") else 0
    for c in por_forn.values():
        c["pendentes"] = c["total"] - c["investigados"]
        c["pct"] = round(100 * c["investigados"] / c["total"], 1) if c["total"] else 0.0
    return {"por_fornecedor": por_forn, "pendentes": sum(c["pendentes"] for c in por_forn.values())}


def avaliacoes(projeto, somente_investigadas: bool = True) -> list:
    """Lista achatada: uma linha por requisito × fornecedor do campo atual (com os dados do requisito)."""
    saida = []
    for e in carregar(projeto):
        for fid, a in (e.get("fornecedores") or {}).items():
            if not isinstance(a, dict) or (somente_investigadas and not a.get("investigado")):
                continue
            saida.append({"id": e["id"], "requisito": e.get("requisito"), "categoria": e.get("categoria"),
                          "obrigatoriedade": e.get("obrigatoriedade"), "fornecedor": fid, **a})
    return saida


def pontuacao(a: dict):
    """Nota do item na régua do kit: pleno nativo/configuração 1,0 · pleno por extensão/terceiro/desenvolvimento 0,5 ·
    parcial 0,5 (0,25 se por extensão) · não atende 0 · não se aplica = fora da conta."""
    at = a.get("atendimento")
    if at not in ("pleno", "parcial", "nao"):
        return None
    externo = (a.get("como") or "nativo") in ("extensao", "terceiro", "desenvolvimento")
    if at == "pleno":
        return 0.5 if externo else 1.0
    if at == "parcial":
        return 0.25 if externo else 0.5
    return 0.0


def aplicar_itens(projeto, fid: str, categorias: list, notas: dict, origem: dict,
                  entradas: list | None = None) -> tuple[dict, dict, float | None]:
    """Nota de cada categoria calculada pelos itens investigados (peso pela obrigatoriedade), completando com a nota
    da KB/ajuste só na parcela ainda não investigada. Sem nota na KB para essa parcela, ela conta como ausente: a nota
    fica conservadora (a parcela vale 0) e a origem 'itens+ausente' mantém a categoria incompleta.
    Retorna (notas, origem, % investigado)."""
    entradas = carregar(projeto) if entradas is None else entradas
    if not entradas:
        return notas, origem, None
    mult = (projeto.cfg.get("pesos") or {}).get("multiplicadores") or {}
    notas, origem = dict(notas), dict(origem)
    total_w = invest_w = 0.0
    for c in categorias:
        cid = c["id"]
        soma = w_itens = w_resto = 0.0
        for e in entradas:
            if e.get("categoria") != cid:
                continue
            a = (e.get("fornecedores") or {}).get(fid) or {}
            if a.get("investigado") and a.get("atendimento") == "na":
                continue
            w = float(mult.get(e.get("obrigatoriedade"), 1.0))
            p = pontuacao(a) if a.get("investigado") else None
            total_w += w
            if p is None:
                w_resto += w
            else:
                soma += w * p
                w_itens += w
                invest_w += w
        if not w_itens:
            continue
        base = notas.get(cid)
        if not w_resto:
            notas[cid], origem[cid] = round(soma / w_itens, 3), "itens"
        elif base is not None:
            notas[cid] = round((soma + w_resto * base) / (w_itens + w_resto), 3)
            origem[cid] = "itens+" + (origem.get(cid) or "kb")
        else:
            notas[cid], origem[cid] = round(soma / (w_itens + w_resto), 3), "itens+ausente"
    return notas, origem, (round(100 * invest_w / total_w, 1) if total_w else None)


def validar(projeto, kb) -> list:
    prob = []
    for a in avaliacoes(projeto):
        rot = f"investigação {a['id']} × {a['fornecedor']}"
        if a.get("atendimento") not in ATENDIMENTOS:
            prob.append(("ERRO", f"{rot}: atendimento '{a.get('atendimento')}' fora de {'/'.join(ATENDIMENTOS)}"))
        if a.get("como") and a["como"] not in COMO:
            prob.append(("ERRO", f"{rot}: como '{a['como']}' fora de {'/'.join(COMO)}"))
        if a.get("cobre_parametro") and a["cobre_parametro"] not in COBRE:
            prob.append(("ERRO", f"{rot}: cobre_parametro '{a['cobre_parametro']}' fora de {'/'.join(COBRE)}"))
        if a.get("tipo_lacuna") and a["tipo_lacuna"] not in TIPOS_LACUNA:
            prob.append(("ERRO", f"{rot}: tipo_lacuna '{a['tipo_lacuna']}' fora de {'/'.join(TIPOS_LACUNA)}"))
        if a.get("atendimento") == "na" and not str(a.get("justificativa") or "").strip():
            prob.append(("AVISO", f"{rot}: 'não se aplica' sem justificativa"))
        if a.get("atendimento") in ("pleno", "parcial") and not isinstance(a.get("ga"), bool):
            if a.get("ga") in (None, ""):
                prob.append(("AVISO", f"{rot}: 'ga' não informado (true = GA, false = preview) — confiança média"))
            else:
                prob.append(("ERRO", f"{rot}: 'ga' deve ser true ou false (veio '{a.get('ga')}') — tratado como preview"))
        for campo in ("evidencias", "citacoes"):
            if a.get(campo) is not None and not isinstance(a.get(campo), list):
                prob.append(("ERRO", f"{rot}: '{campo}' deve ser lista"))
        for ev in a.get("evidencias") or [] if isinstance(a.get("evidencias"), list) else []:
            if str(ev).startswith("EV-"):
                e = kb.evidencia(ev)
                if not e:
                    prob.append(("ERRO", f"{rot}: evidência {ev} não existe em kb/evidencias"))
                elif e.get("fornecedor") != a["fornecedor"]:
                    prob.append(("AVISO", f"{rot}: evidência {ev} é da biblioteca de {e.get('fornecedor')}, não de "
                                          f"{a['fornecedor']}"))
    return prob
