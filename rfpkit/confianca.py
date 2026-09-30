"""Confiança de cada avaliação requisito × fornecedor — calculada por regras, não declarada pelo LLM.

ALTA   requisito claro; evidência oficial do próprio fornecedor com citação literal conferível (15+ caracteres)
       conferida (nesta execução, na execução assistida) — cada evidência pelas SUAS citações; recurso GA; a fonte
       cobre o parâmetro pedido; sem conflito; para "não atende", fonte oficial que afirma a limitação; para "não se
       aplica", justificativa.
MÉDIA  requisito ambíguo/incompleto (depende de esclarecimento do cliente); a fonte cobre a capacidade mas não o
       parâmetro; atendimento por configuração complexa, extensão, terceiro ou desenvolvimento; verificação
       inconclusiva (site que recusa robôs, página montada por JavaScript sem conferência no navegador); evidência
       vencida ou a validar; citação curta demais para conferir; "não atende" sem fonte que afirme a limitação
       (ausência de evidência); "não se aplica" sem justificativa; divergência na verificação independente.
BAIXA  pleno/parcial sem evidência oficial; evidência de outro fornecedor; fontes em conflito; preview numa resposta
       plena; evidência quebrada ou cuja citação sumiu da página (em nenhuma das páginas citadas pelo item); a
       verificação independente concluiu que a evidência não sustenta a conclusão; fonte que não cobre o parâmetro
       numa resposta plena.

Cada motivo tem um tipo que define o encaminhamento exigido quando a confiança não é alta:
cliente/conflito -> pergunta de esclarecimento (duvidas.yaml); documentacao -> pergunta ao fabricante ou item de
POC; verificacao -> refazer a checagem (URLs, navegador, revisão); independente -> decisão humana.
"""
import datetime as dt

from . import util

NIVEIS = ("baixa", "media", "alta")
ORDEM = {n: i for i, n in enumerate(NIVEIS)}
ROTULO = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}
FATOS_PALAVRAS = {                     # fato da KB -> termos do requisito que dependem dele (checagem de consistência)
    "rum_mobile": ("mobile", "android", "ios", "aplicativo movel", "aplicativos moveis", "app movel", "apps moveis"),
    "session_replay": ("session replay", "replay de sessao", "gravacao de sessao", "gravacao de sessoes"),
    "self_managed": ("on-premises", "on premises", "self-hosted", "auto-hospedad", "instalacao local"),
    "regiao_dados_brasil": ("dados no brasil", "residencia de dados", "territorio nacional", "regiao brasil"),
}
_FATOS_RE = {fato: util.compilar_palavras(termos) for fato, termos in FATOS_PALAVRAS.items()}  # "ios" ≠ "relatórios"


def _data(valor):
    try:
        return util.para_data(valor)
    except (ValueError, TypeError):
        return None


class _Contexto:
    def __init__(self, projeto, kb):
        from .duvidas import carregar as carregar_duvidas
        from .execucao import config
        from .revisao import carregar as carregar_revisao
        self.projeto, self.kb = projeto, kb
        cfg = config(projeto)
        self.assistida, self.max_dias = cfg["assistida"], cfg["kb_max_dias"]
        self.hoje = dt.date.today()
        self.revisao = {i["id"]: i for i in carregar_revisao(projeto)}
        self.urls = self._checagem(projeto)
        from .duvidas import id_duvida
        self.duvidas = {id_duvida(d.get("id")): d for d in carregar_duvidas(projeto)}
        indep = util.ler_json(projeto.dir_analise / "verificacao-independente.json", []) or []
        self.independente = {(v.get("id"), v.get("fornecedor"), v.get("impressao")): v   # vale a da conclusão atual
                             for v in (indep if isinstance(indep, list) else []) if isinstance(v, dict)}

    @staticmethod
    def _checagem(projeto) -> dict:
        """Checagem de URLs desta análise; o JSON traz as citações conferidas/ausentes de cada página."""
        try:
            dados = util.ler_json(projeto.dir_analise / "validacao-urls.json", None)
        except ValueError:
            dados = None
        if isinstance(dados, list):
            return {r.get("url"): r for r in dados if isinstance(r, dict)}
        return {r.get("url"): r for r in util.ler_csv(projeto.dir_analise / "validacao-urls.csv")}

    def fresco(self, valor) -> bool:
        data = _data(valor)
        if not data:
            return False
        return (self.hoje - data).days <= self.max_dias if self.assistida else True


CURTA = "citação curta demais para conferência literal (use um trecho com 15+ caracteres)"


def _nivel_ev_kb(ev_ref, avaliacao: dict, ctx: _Contexto) -> tuple[str, list]:
    """(melhor nível possível, [(tipo, motivo)]) para uma evidência EV-… da KB — julgada pelas SUAS citações (outra
    evidência na mesma página não a derruba nem a sustenta)."""
    from .urls import citacoes_da_evidencia
    kb = ctx.kb
    e = kb.evidencia(ev_ref)
    if e.get("fornecedor") != avaliacao.get("fornecedor"):
        return "baixa", [("documentacao", f"{ev_ref} é evidência de outro fornecedor ({e.get('fornecedor')})")]
    st = kb.status_evidencia(e, ctx.projeto.data_ref)
    if st == "QUEBRADA":
        return "baixa", [("verificacao", f"{ev_ref}: URL quebrada")]
    if e.get("mudanca_detectada"):
        return "baixa", [("verificacao", f"{ev_ref}: fonte mudou ({str(e['mudanca_detectada'])[:80]})")]
    check = ctx.urls.get(e.get("url")) or {}
    if check.get("situacao") == "QUEBRADA":
        return "baixa", [("verificacao", f"{ev_ref}: quebrada na checagem desta execução")]
    proprias = citacoes_da_evidencia(e)
    navegador = e.get("verificacao") == "navegador" or check.get("situacao") in ("BLOQUEADA", "NAVEGADOR")
    # página montada por JavaScript/que recusa robôs: o HTML cru não tem as citações — decide a conferência no navegador
    faltando = [] if navegador else [c for c in proprias if c in (check.get("_ausentes") or [])]
    if faltando:
        return "baixa", [("verificacao", f"{ev_ref}: citação não encontrada na página — {faltando[0][:80]}")]
    nivel, motivos = "alta", []

    def piorar(tipo, texto):
        nonlocal nivel
        nivel = "media"
        motivos.append((tipo, texto))

    if st != "VALIDADA":
        piorar("verificacao", f"{ev_ref}: evidência {st.lower()}")
    if check.get("situacao") == "CITACAO_AUSENTE" and "_ausentes" not in check:
        piorar("verificacao", f"{ev_ref}: checagem sem detalhe por citação — rode validar-urls de novo")
    verificaveis = [c for c in proprias if util.trechos_citacao(c)]
    conferidas = check.get("_conferidas") or []
    agora = bool(verificaveis) and ctx.fresco(check.get("verificado_em")) and all(c in conferidas for c in verificaveis)
    if not proprias:
        piorar("documentacao", f"{ev_ref}: sem citação literal")
    elif not verificaveis:
        piorar("verificacao", f"{ev_ref}: {CURTA}")
    elif navegador:
        if not ctx.fresco(e.get("verificado_navegador_em") or (e.get("verificado_em") if not ctx.assistida else None)):
            piorar("verificacao", f"{ev_ref}: conferir as citações no navegador")
    elif not (agora or ctx.fresco(e.get("citacao_conferida_em"))):
        piorar("verificacao", f"{ev_ref}: citação não conferida nesta execução")
    if check.get("situacao") in ("REDIRECIONADA", "SEM_PALAVRAS"):
        piorar("verificacao", f"{ev_ref}: {check['situacao'].lower()}")
    return nivel, motivos


def _nivel_urls(urls_diretas: list, avaliacao: dict, ctx: _Contexto) -> tuple[str, list]:
    """Evidências por URL direta: cada citação do item precisa estar em alguma das páginas citadas."""
    rotulo = urls_diretas[0] if len(urls_diretas) == 1 else f"{len(urls_diretas)} URLs citadas"
    brutas = avaliacao.get("citacoes") if isinstance(avaliacao.get("citacoes"), list) else []
    cit = [c for c in brutas if isinstance(c, str) and c.strip()]
    feitos = [ctx.urls[u] for u in urls_diretas if ctx.urls.get(u)]
    validos = [c for c in feitos if c.get("situacao") != "QUEBRADA"]
    if feitos and not validos and len(feitos) == len(urls_diretas):
        return "baixa", [("verificacao", f"URL quebrada: {rotulo}")]
    if not cit:
        return "media", [("documentacao", f"sem citação literal da fonte ({rotulo})")]
    verificaveis = [c for c in cit if util.trechos_citacao(c)]
    if not verificaveis:
        return "media", [("verificacao", CURTA)]
    if not feitos:
        return ("media", [("verificacao", f"URL não verificada: {rotulo}")]) if ctx.assistida else ("alta", [])
    conferidas = {x for c in validos for x in (c.get("_conferidas") or [])}
    nao_conf = [c for c in verificaveis if c not in conferidas]
    if nao_conf:
        inconclusivo = (len(feitos) < len(urls_diretas) or any("_ausentes" not in c for c in validos)
                        or any(c.get("situacao") in ("BLOQUEADA", "NAVEGADOR") for c in validos))
        if not inconclusivo:
            return "baixa", [("verificacao", f"citação não encontrada nas páginas citadas — {nao_conf[0][:80]}")]
        return "media", [("verificacao", f"citação não confirmada automaticamente ({rotulo}) — conferir no navegador")]
    motivos = []
    if not all(ctx.fresco(c.get("verificado_em")) for c in validos):
        motivos.append(("verificacao", f"citação não conferida nesta execução ({rotulo})"))
    if len(validos) < len(feitos):
        motivos.append(("verificacao", f"há URL quebrada entre as citadas ({rotulo}) — substitua"))
    for c in validos:
        if c.get("situacao") in ("REDIRECIONADA", "SEM_PALAVRAS"):
            motivos.append(("verificacao", f"{c['situacao'].lower()}: {c.get('url')}"))
    return ("media" if motivos else "alta"), motivos


def _niveis_evidencias(evs: list, avaliacao: dict, ctx: _Contexto) -> list:
    from .urls import urls_do_texto
    resultados, diretas = [], []
    for ev in evs:
        if ctx.kb.evidencia(ev):
            resultados.append(_nivel_ev_kb(ev, avaliacao, ctx))
            continue
        u = urls_do_texto(str(ev))[:1]
        if u:
            diretas += [x for x in u if x not in diretas]
        else:
            resultados.append(("baixa", [("documentacao", f"evidência '{ev}' não é EV da KB nem URL")]))
    if diretas:
        resultados.append(_nivel_urls(diretas, avaliacao, ctx))
    return resultados


def avaliar_item(a: dict, ctx: _Contexto) -> dict:
    """Nível de confiança, motivos e pendências de encaminhamento de uma avaliação."""
    nivel = "alta"
    motivos = []

    def rebaixar(n, tipo, texto):
        nonlocal nivel
        if ORDEM[n] < ORDEM[nivel]:
            nivel = n
        motivos.append({"tipo": tipo, "nivel": n, "texto": texto})

    rev = ctx.revisao.get(a["id"]) or {}
    if ctx.assistida and not rev.get("revisado"):
        rebaixar("media", "verificacao", "requisito ainda não revisado pelo LLM")
    if rev.get("clareza") in ("ambigua", "incompleta"):
        adj = {"ambigua": "ambíguo", "incompleta": "incompleto"}[rev["clareza"]]
        rebaixar("media", "cliente", f"requisito {adj}: {rev.get('lacuna') or 'depende de esclarecimento'}")
    at = a.get("atendimento") or ""
    evs = [e for e in (a.get("evidencias") if isinstance(a.get("evidencias"), list) else []) if e]
    if at not in ("pleno", "parcial", "nao", "na"):
        rebaixar("baixa", "documentacao", "sem conclusão de atendimento")
    elif at in ("pleno", "parcial"):
        if not evs:
            rebaixar("baixa", "documentacao", "sem evidência oficial")
        else:
            resultados = _niveis_evidencias(evs, a, ctx)
            melhor = max(resultados, key=lambda r: ORDEM[r[0]])
            if melhor[0] != "alta":
                for tipo, texto in melhor[1]:
                    rebaixar(melhor[0], tipo, texto)
        ga = a.get("ga")
        if ga is False or (a.get("origem") == "investigacao" and ga not in (None, "") and not isinstance(ga, bool)):
            rebaixar("baixa" if at == "pleno" else "media", "documentacao",
                     "recurso em preview (não GA)" if ga is False else f"GA inválido ('{ga}') — tratado como preview")
        elif a.get("origem") == "investigacao" and ga is not True:
            rebaixar("media", "verificacao", "GA não informado na investigação")
        cobre = a.get("cobre_parametro") or ""
        if cobre == "nao":
            rebaixar("baixa" if at == "pleno" else "media", "documentacao", "a fonte não cobre o parâmetro pedido")
        elif cobre == "parcial":
            rebaixar("media", "documentacao", "a fonte cobre o parâmetro só em parte")
        elif not cobre and str(rev.get("parametros") or "").strip():
            rebaixar("media", "documentacao", "não informado se a fonte cobre o parâmetro pedido")
        if at == "pleno" and (a.get("como") or "nativo") in ("extensao", "terceiro", "desenvolvimento"):
            rebaixar("media", "documentacao", f"atendimento por {a['como']}")
    elif at == "nao":
        if not evs:
            rebaixar("media", "documentacao", "'não atende' sem fonte que afirme a limitação (ausência de evidência)")
        else:
            resultados = _niveis_evidencias(evs, a, ctx)
            melhor = max(resultados, key=lambda r: ORDEM[r[0]])
            if melhor[0] != "alta":
                for tipo, texto in melhor[1]:
                    rebaixar(melhor[0], tipo, texto)
    elif at == "na" and not str(a.get("justificativa") or "").strip():
        rebaixar("media", "documentacao", "'não se aplica' sem justificativa")
    if a.get("conflito"):
        rebaixar("baixa", "conflito", "fontes em conflito")
    tipo_lacuna = a.get("tipo_lacuna") or ""
    if str(a.get("lacuna") or "").strip() and tipo_lacuna in ("cliente", "conflito", "documentacao"):
        rebaixar("media", tipo_lacuna, f"lacuna declarada: {a['lacuna']}")
    from .independente import impressao
    ind = ctx.independente.get((a["id"], a["fornecedor"], impressao(a)))   # só a verificação da conclusão atual
    if ind and ind.get("verificado") and ind.get("divergente") and ind.get("resolucao") != "manter":
        if ind.get("confere_evidencia") == "nao":
            rebaixar("baixa", "independente", "verificação independente: a evidência não sustenta a conclusão")
        else:
            rebaixar("media", "independente", f"verificação independente divergiu ({ind.get('atendimento')})")
    return {"nivel": nivel, "motivos": motivos, **_encaminhamento(a, rev, motivos, ctx)}


def _encaminhamento(a: dict, rev: dict, motivos: list, ctx: _Contexto) -> dict:
    """O que foi feito para cada tipo de lacuna e o que ainda falta."""
    from .duvidas import ids_de_duvida
    tipos = {m["tipo"] for m in motivos if m["nivel"] != "alta"}
    duvidas = ids_de_duvida(a.get("duvida")) + ids_de_duvida(rev.get("duvida"))
    duvida_ok = next((d for d in duvidas if d in ctx.duvidas and
                      str(ctx.duvidas[d].get("status") or "").upper() != "RETIRADA"), None)
    fabricante = bool(str(a.get("pergunta_fabricante") or "").strip()) or bool(a.get("poc"))
    pendencias = []
    if tipos & {"cliente", "conflito"} and not duvida_ok:
        pendencias.append("pergunta de esclarecimento ao cliente")
    if "documentacao" in tipos and not fabricante and not duvida_ok:
        pendencias.append("pergunta ao fabricante ou item de POC")
    if "verificacao" in tipos:
        pendencias.append("refazer a verificação (URLs/citações, navegador ou revisão)")
    if "independente" in tipos:
        pendencias.append("decisão humana sobre a divergência da verificação independente")
    return {"duvida": duvida_ok, "fabricante_ou_poc": fabricante, "pendencias": pendencias}


def avaliacoes_do_estudo(projeto, kb) -> list:
    """Avaliações investigadas + (modo proponente) as respostas do proponente que não têm investigação própria."""
    from .investigacao import avaliacoes
    from .respostas import nivel
    itens = avaliacoes(projeto)
    for a in itens:
        a["origem"] = "investigacao"
    prop = projeto.cfg.get("proponente")
    if projeto.cfg.get("modo") == "proponente" and prop:
        investigados = {a["id"] for a in itens if a["fornecedor"] == prop}
        rtm = {r["id"]: r for r in (util.ler_json(projeto.dir_projeto / "rtm.json") or {}).get("requisitos", [])}
        mapa = {"pleno": "pleno", "parcial": "parcial", "nao": "nao", "na": "na"}
        for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
            if not r.get("resposta") or r.get("_orfa") or r.get("id") not in rtm or r["id"] in investigados:
                continue
            nv = nivel(r["resposta"], r.get("escala") or projeto.cfg["respostas"]["escala"])
            evs = [e for e in r.get("evidencias") or [] if e]
            ga = None
            if any(kb.evidencia(e) and kb.evidencia(e).get("ga") is False for e in evs):
                ga = False
            itens.append({"id": r["id"], "requisito": rtm[r["id"]]["texto"], "categoria": rtm[r["id"]]["categoria"],
                          "obrigatoriedade": rtm[r["id"]]["obrigatoriedade"], "fornecedor": prop,
                          "atendimento": mapa.get(nv, ""), "como": _como(r.get("metodo")), "ga": ga,
                          "evidencias": evs, "citacoes": [], "duvida": r.get("duvida") or "",
                          "justificativa": r.get("justificativa") or "", "poc": bool(r.get("poc")),
                          "origem": "respostas"})
    return itens


def _como(metodo) -> str:
    m = util.norm(metodo or "nativo")
    for chave in ("extensao", "terceiro", "desenvolvimento", "configuracao"):
        if chave in m:
            return chave
    return "nativo"


def inconsistencias(projeto, kb, itens: list) -> list:
    """Mesma evidência com conclusões opostas; conclusão que contradiz fato da KB; resposta × investigação."""
    saida = []
    por_ev = {}
    for a in itens:
        for ev in a.get("evidencias") or []:
            if kb.evidencia(ev):
                por_ev.setdefault((a["fornecedor"], ev), []).append(a)
    for (fid, ev), lista in por_ev.items():
        niveis = {x.get("atendimento") for x in lista}
        if "pleno" in niveis and "nao" in niveis:
            ids = [x["id"] for x in lista if x.get("atendimento") in ("pleno", "nao")]
            saida.append({"fornecedor": fid, "ids": ids,
                          "texto": f"{ev} sustenta 'pleno' e 'não atende' ao mesmo tempo ({', '.join(ids[:6])})"})
    for a in itens:
        if a.get("atendimento") != "pleno":
            continue
        texto = util.norm(a.get("requisito"))
        for fato, padroes in _FATOS_RE.items():
            if util.contar(padroes, texto):
                f = kb.fato(a["fornecedor"], fato, projeto.data_ref)
                if f.get("valor") == "NAO":
                    saida.append({"fornecedor": a["fornecedor"], "ids": [a["id"]],
                                  "texto": f"{a['id']}: 'pleno' contradiz o fato {fato}=NAO da KB — revise a resposta ou a KB"})
    prop = projeto.cfg.get("proponente")
    if projeto.cfg.get("modo") == "proponente" and prop:
        from .respostas import nivel
        inv = {a["id"]: a for a in itens if a["fornecedor"] == prop and a.get("origem") == "investigacao"}
        for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
            a = inv.get(r.get("id"))
            if a and r.get("resposta"):
                nv = nivel(r["resposta"], r.get("escala") or projeto.cfg["respostas"]["escala"])
                if nv and a.get("atendimento") and nv != a["atendimento"]:
                    saida.append({"fornecedor": prop, "ids": [r["id"]], "erro": True,
                                  "texto": f"{r['id']}: resposta '{r['resposta']}' difere da investigação ({a['atendimento']})"})
    return saida


def calcular(projeto, kb) -> dict:
    ctx = _Contexto(projeto, kb)
    itens = avaliacoes_do_estudo(projeto, kb)
    incons = inconsistencias(projeto, kb, itens)
    marcados = {(i["fornecedor"], rid) for i in incons for rid in i["ids"]}
    saida = []
    for a in itens:
        r = avaliar_item(a, ctx)
        if (a["fornecedor"], a["id"]) in marcados and r["nivel"] == "alta":
            r["nivel"] = "media"
            r["motivos"].append({"tipo": "verificacao", "nivel": "media", "texto": "inconsistente com outra conclusão"})
            r["pendencias"].append("resolver a inconsistência")
        saida.append({"id": a["id"], "fornecedor": a["fornecedor"], "categoria": a.get("categoria"),
                      "obrigatoriedade": a.get("obrigatoriedade"), "atendimento": a.get("atendimento"),
                      "origem": a.get("origem"), **r})
    resumo = {}
    for s in saida:
        c = resumo.setdefault(s["fornecedor"], {"total": 0, "alta": 0, "media": 0, "baixa": 0,
                                                "elim_total": 0, "elim_alta": 0, "pendencias": 0})
        c["total"] += 1
        c[s["nivel"]] += 1
        c["pendencias"] += 1 if s["pendencias"] else 0
        if s.get("obrigatoriedade") == "eliminatorio":
            c["elim_total"] += 1
            c["elim_alta"] += 1 if s["nivel"] == "alta" else 0
    for c in resumo.values():
        c["pct_alta"] = round(100 * c["alta"] / c["total"], 1) if c["total"] else None
        c["pct_elim_alta"] = round(100 * c["elim_alta"] / c["elim_total"], 1) if c["elim_total"] else None
    anterior = util.ler_json(projeto.dir_analise / "confianca.json", {}) or {}
    antes = {(x["id"], x["fornecedor"]): x for x in anterior.get("avaliacoes") or []}
    mudancas = []
    for s in saida:
        v = antes.get((s["id"], s["fornecedor"]))
        if v and (v.get("atendimento") != s["atendimento"] or v.get("nivel") != s["nivel"]):
            mudancas.append({"id": s["id"], "fornecedor": s["fornecedor"],
                             "antes": f"{v.get('atendimento')}/{v.get('nivel')}",
                             "agora": f"{s['atendimento']}/{s['nivel']}"})
    return {"gerado_em": ctx.hoje.isoformat(), "assistida": ctx.assistida, "avaliacoes": saida, "resumo": resumo,
            "inconsistencias": incons, "mudancas": mudancas}


def gravar(projeto, kb, dados: dict) -> list:
    util.gravar_json(projeto.dir_analise / "confianca.json", dados)
    nomes = lambda f: kb.nome(f)  # noqa: E731
    L = ["# Confiança da análise", "",
         f"_{projeto.cfg['cliente']['nome']} · {dados['gerado_em']} · regras em `rfpkit/confianca.py` (alta: requisito "
         "claro + citação oficial conferida + GA + cobre o parâmetro). Uso interno._", "",
         "| Fornecedor | Avaliações | Alta | Média | Baixa | % alta | Eliminatórios com alta | Com pendência |",
         "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for fid, c in dados["resumo"].items():
        L.append(f"| {nomes(fid)} | {c['total']} | {c['alta']} | {c['media']} | {c['baixa']} | {util.br(c['pct_alta'])}% | "
                 f"{c['elim_alta']}/{c['elim_total']} | {c['pendencias']} |")
    abaixo = [s for s in dados["avaliacoes"] if s["nivel"] != "alta"]
    if abaixo:
        L += ["", "## Itens abaixo de confiança alta", "",
              "| Requisito | Fornecedor | Obrig. | Atendimento | Confiança | Motivos | Encaminhamento | Pendências |",
              "|---|---|---|---|---|---|---|---|"]
        for s in sorted(abaixo, key=lambda x: (x.get("obrigatoriedade") != "eliminatorio", ORDEM[x["nivel"]], x["id"])):
            enc = " · ".join(x for x in (f"dúvida {s['duvida']}" if s.get("duvida") else "",
                                         "fabricante/POC" if s.get("fabricante_ou_poc") else "") if x) or "—"
            L.append(f"| {s['id']} | {nomes(s['fornecedor'])} | {s.get('obrigatoriedade') or ''} | {s.get('atendimento') or ''} | "
                     f"{ROTULO[s['nivel']]} | {'; '.join(m['texto'] for m in s['motivos'])[:300].replace('|', '/')} | {enc} | "
                     f"{'; '.join(s['pendencias']) or '—'} |")
    if dados["inconsistencias"]:
        L += ["", "## Inconsistências", ""] + [f"- {nomes(i['fornecedor'])}: {i['texto']}" for i in dados["inconsistencias"]]
    if dados["mudancas"]:
        L += ["", "## Mudanças desde a execução anterior", "", "| Requisito | Fornecedor | Antes | Agora |", "|---|---|---|---|"]
        L += [f"| {m['id']} | {nomes(m['fornecedor'])} | {m['antes']} | {m['agora']} |" for m in dados["mudancas"]]
    destino = projeto.dir_analise / "confianca.md"
    destino.write_text("\n".join(L) + "\n", encoding="utf-8")
    return [projeto.dir_analise / "confianca.json", destino]


def validar(projeto, kb) -> list:
    """Portão de confiança: grava confianca.json/md e devolve [(nível, mensagem)]."""
    dados = calcular(projeto, kb)
    gravar(projeto, kb, dados)
    grave = "ERRO" if dados["assistida"] else "AVISO"
    prob = []
    prop = projeto.cfg.get("proponente")
    for s in dados["avaliacoes"]:
        if s["nivel"] == "alta" or not s["pendencias"]:
            continue
        rot = f"{s['id']} × {kb.nome(s['fornecedor'])}"
        motivos = "; ".join(m["texto"] for m in s["motivos"])[:200]
        if s.get("obrigatoriedade") == "eliminatorio":
            prob.append((grave, f"confiança {s['nivel']} em eliminatório {rot} sem encaminhamento "
                                f"({'; '.join(s['pendencias'])}) — {motivos}"))
        if s["fornecedor"] == prop and s.get("atendimento") == "pleno":
            prob.append(("ERRO" if s["nivel"] == "baixa" else grave,
                         f"resposta plena de {s['id']} com confiança {s['nivel']} — {motivos}; "
                         "só 'atende plenamente' com confiança alta: rebaixe ou encaminhe"))
    outros = [s for s in dados["avaliacoes"] if s["nivel"] != "alta" and s["pendencias"]
              and s.get("obrigatoriedade") != "eliminatorio" and not (s["fornecedor"] == prop and s.get("atendimento") == "pleno")]
    if outros:
        prob.append(("AVISO", f"{len(outros)} avaliação(ões) abaixo de confiança alta com pendência de encaminhamento "
                              "— ver 02-analise/confianca.md"))
    for i in dados["inconsistencias"]:
        prob.append(("ERRO" if i.get("erro") else "AVISO", f"inconsistência ({kb.nome(i['fornecedor'])}): {i['texto']}"))
    return prob
