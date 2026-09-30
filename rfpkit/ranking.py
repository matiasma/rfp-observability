"""Seleção de fornecedores (triagem -> avaliação completa), aderência ponderada e scorecard multi-eixo."""
from . import gates as gates_mod
from . import util
from .kb import KB

ORDEM_STATUS = {"PASSA": 0, "RISCO": 1, "REPROVA": 2}
EIXOS_NOTA = ("risco", "esforco", "custo", "estrategico")


def lista_triagem(projeto, kb: KB) -> tuple[list, list]:
    cfg = projeto.cfg["fornecedores"]
    avisos, lista = [], []

    def add(fid, origem):
        if fid in cfg.get("excluir", []):
            return
        if fid not in kb.fornecedores:
            avisos.append(f"fornecedor '{fid}' ({origem}) sem ficha em kb/fornecedores — ignorado "
                          f"(crie a partir de kb/fornecedores/_modelo.yaml)")
            return
        if fid not in [x["id"] for x in lista]:
            lista.append({"id": fid, "origem": origem})

    for fid in cfg.get("obrigatorios") or []:
        add(fid, "obrigatório")
    if projeto.cfg.get("modo") == "proponente" and projeto.cfg.get("proponente"):
        add(projeto.cfg["proponente"], "proponente")
    lideres = cfg.get("lideres_gartner", "auto")
    if lideres == "auto":
        for fid in kb.lideres_vigentes(projeto.data_ref):
            add(fid, "Líder Gartner")
    elif isinstance(lideres, list):
        for fid in lideres:
            add(fid, "Líder Gartner")
    for fid in cfg.get("contexto") or []:
        add(fid, "contexto do cliente")
    return lista, avisos


def notas_efetivas(projeto, kb: KB, fid: str, categorias: list) -> tuple[dict, dict]:
    ajustes = {}
    for a in util.ler_yaml(projeto.dir_analise / "ajustes-notas.yaml", []) or []:
        if a.get("fornecedor") == fid and a.get("categoria") and util.num(a.get("nota")) is not None:
            ajustes[a["categoria"]] = a
    notas, origem = {}, {}
    for c in categorias:
        cid = c["id"]
        if cid in ajustes:
            notas[cid], origem[cid] = util.num(ajustes[cid]["nota"]), "ajuste"
        else:
            base = kb.nota_base(fid, cid)
            notas[cid], origem[cid] = (float(base) if base is not None else None), ("kb" if base is not None else "ausente")
    return notas, origem


def aderencia(notas: dict, categorias: list):
    soma_w = sum(c["peso"] for c in categorias if c["peso"] > 0)
    if not soma_w:
        return None, False
    total = sum((notas.get(c["id"]) or 0.0) * c["peso"] for c in categorias if c["peso"] > 0)
    completo = all(notas.get(c["id"]) is not None for c in categorias if c["peso"] > 0)
    return total / soma_w, completo


def calcular(projeto, kb: KB | None = None, pesos: dict | None = None) -> dict:
    kb = kb or KB()
    pesos = pesos or util.ler_json(projeto.dir_projeto / "categorias-pesos.json")
    if not pesos:
        raise RuntimeError("categorias-pesos.json não encontrado — rode 'python kit.py pesos' antes.")
    categorias = [c for c in pesos["categorias"] if c["peso"] > 0]
    triagem, avisos = lista_triagem(projeto, kb)
    resultado_gates = gates_mod.avaliar(projeto, [t["id"] for t in triagem], kb)

    from .investigacao import aplicar_itens, carregar as carregar_investigacao
    investigado = carregar_investigacao(projeto)
    for t in triagem:          # prévia só pela KB: o corte da avaliação completa não oscila com a investigação
        notas, _ = notas_efetivas(projeto, kb, t["id"], categorias)
        ader, completo = aderencia(notas, categorias)
        g = resultado_gates["fornecedores"][t["id"]]
        t.update({"nome": kb.nome(t["id"]), "status_gate": g["status"], "reprovados": g["reprovados"],
                  "riscos": g["riscos"], "aderencia_previa_pct": round(ader * 100, 1) if ader is not None else None,
                  "notas_completas": completo})

    cfg = projeto.cfg["fornecedores"]
    fixos = [t for t in triagem if t["origem"] in ("obrigatório", "proponente")]
    demais = sorted([t for t in triagem if t not in fixos],
                    key=lambda t: (ORDEM_STATUS[t["status_gate"]], -(t["aderencia_previa_pct"] or 0)))
    limite = max(int(cfg.get("max_avaliacao_completa") or 6), len(fixos))
    completa = fixos + demais[:limite - len(fixos)]
    ids_completa = [t["id"] for t in completa]
    for t in triagem:
        t["avaliacao_completa"] = t["id"] in ids_completa

    eixos_cfg = projeto.cfg["eixos"]
    eixos_forn = util.ler_yaml(projeto.dir_analise / "eixos.yaml", {}) or {}
    linhas = []
    for fid in ids_completa:
        notas, origem = notas_efetivas(projeto, kb, fid, categorias)
        notas, origem, pct_itens = aplicar_itens(projeto, fid, categorias, notas, origem, investigado)
        ader, completo = aderencia(notas, categorias)
        completo = completo and not any("ausente" in str(origem.get(c["id"]) or "") for c in categorias)
        e = eixos_forn.get(fid) or {}
        valores = {k: util.num(e.get(k)) for k in EIXOS_NOTA}
        ader5 = ader * 5 if ader is not None else None
        nota_final = None
        if ader5 is not None and all(valores[k] is not None for k in eixos_cfg if k != "aderencia"):
            nota_final = round(sum(float(p) / 100 * (ader5 if k == "aderencia" else valores[k])
                                   for k, p in eixos_cfg.items()), 2)
        g = resultado_gates["fornecedores"][fid]
        linhas.append({
            "fornecedor": fid, "nome": kb.nome(fid), "confianca": (kb.fornecedores[fid].get("confianca") or ""),
            "aderencia_pct": round(ader * 100, 1) if ader is not None else None,
            "aderencia_5": round(ader5, 2) if ader5 is not None else None,
            **{k: valores[k] for k in EIXOS_NOTA},
            "nota_final": nota_final, "notas_completas": completo, "status_gate": g["status"],
            "gates_reprovados": ",".join(g["reprovados"]) or "-", "gates_risco": ",".join(g["riscos"]) or "-",
            "notas": notas, "origem_notas": origem, "investigacao_pct": pct_itens,
            "justificativa_eixos": e.get("justificativa") or {},
        })
    linhas.sort(key=lambda l: (-(l["nota_final"] if l["nota_final"] is not None else -1),
                               -(l["aderencia_pct"] or 0)))
    for i, l in enumerate(linhas, start=1):
        l["posicao"] = i
    elegiveis = [l for l in linhas if l["status_gate"] != "REPROVA"]
    resultado = {
        "data_referencia": projeto.data_ref,
        "edicao_gartner": (kb.edicao_vigente(projeto.data_ref) or {}).get("ano"),
        "eixos": eixos_cfg,
        "categorias": categorias,
        "triagem": triagem,
        "avaliacao_completa": ids_completa,
        "ranking": linhas,
        "melhor_merito": linhas[0]["fornecedor"] if linhas else None,
        "melhor_elegivel": elegiveis[0]["fornecedor"] if elegiveis else None,
        "lentes": lentes(linhas),
        "sensibilidade": sensibilidade(linhas, eixos_cfg),
        "cenarios_gate": cenarios_gate(linhas, resultado_gates),
        "avisos": avisos,
    }
    util.gravar_json(projeto.dir_analise / "ranking.json", resultado)
    colunas = ["posicao", "fornecedor", "nome", "confianca", "aderencia_pct", "aderencia_5", *EIXOS_NOTA,
               "nota_final", "status_gate", "gates_reprovados", "gates_risco", "notas_completas"]
    util.gravar_csv(projeto.dir_analise / "ranking.csv", linhas, colunas)
    util.gravar_json(projeto.dir_analise / "selecao.json",
                     {"criterio": "obrigatórios + proponente + Líderes Gartner (edição vigente) + contexto − excluir; "
                                  "avaliação completa = fixos + melhores da triagem (gate, depois aderência prévia) "
                                  f"até {limite}",
                      "triagem": triagem, "avaliacao_completa": ids_completa})
    return resultado


NOME_EIXO = {"aderencia": "Aderência", "risco": "Risco", "esforco": "Esforço", "custo": "Custo",
             "estrategico": "Estratégico"}


def _nota(l: dict, pesos: dict):
    total = sum(pesos.values()) or 1
    valores = {k: (l.get("aderencia_5") if k == "aderencia" else l.get(k)) for k in pesos}
    if any(v is None for k, v in valores.items() if pesos[k]):
        return None
    return round(sum(float(p) / total * float(valores[k] or 0) for k, p in pesos.items()), 2)


def _redistribuir(eixos: dict, eixo: str, delta: float) -> dict:
    """Soma 'delta' p.p. ao eixo e reduz os demais proporcionalmente (total continua 100)."""
    base = {k: float(v) for k, v in eixos.items()}
    novo_k = min(100.0, base[eixo] + delta)
    resto_antes = 100.0 - base[eixo]
    fator = (100.0 - novo_k) / resto_antes if resto_antes > 0 else 0.0
    return {k: round(novo_k if k == eixo else v * fator, 1) for k, v in base.items()}


def lentes(linhas: list) -> dict:
    """Duas lentes: aderência pura ao edital × balanço completo (nota final)."""
    com_ader = [l for l in linhas if l.get("aderencia_pct") is not None]
    com_nota = [l for l in linhas if l.get("nota_final") is not None]
    ader = max(com_ader, key=lambda l: l["aderencia_pct"]) if com_ader else None
    nota = max(com_nota, key=lambda l: l["nota_final"]) if com_nota else None
    return {"lider_aderencia": ader and ader["fornecedor"], "aderencia_pct": ader and ader["aderencia_pct"],
            "lider_nota": nota and nota["fornecedor"], "nota_final": nota and nota["nota_final"],
            "coincidem": bool(ader and nota and ader["fornecedor"] == nota["fornecedor"])}


def sensibilidade(linhas: list, eixos: dict, delta: float = 20.0):
    """Quem fica em 1º quando os pesos do scorecard mudam: base, cada eixo decisivo (+delta p.p.), só aderência e
    pesos iguais. '1º robusto' = mais vitórias (desempate: menor posição média), entre todos e entre os elegíveis."""
    base = [l for l in linhas if l.get("nota_final") is not None]
    if len(base) < 2 or not eixos:
        return None
    cenarios = [("Pesos do edital (base)", {k: float(v) for k, v in eixos.items()})]
    cenarios += [(f"{NOME_EIXO.get(k, k)} decisivo (+{delta:g} p.p.)", _redistribuir(eixos, k, delta))
                 for k in eixos if float(eixos[k]) < 100]
    cenarios.append(("Só aderência ao edital", {k: (100.0 if k == "aderencia" else 0.0) for k in eixos}))
    cenarios.append(("Pesos iguais", {k: round(100.0 / len(eixos), 1) for k in eixos}))
    saida = []
    for nome, pesos in cenarios:
        notas = {l["fornecedor"]: _nota(l, pesos) for l in base}
        ordem = sorted(base, key=lambda l: (-(notas[l["fornecedor"]] or 0), -(l.get("aderencia_pct") or 0)))
        saida.append({"cenario": nome, "pesos": pesos, "ordem": [l["fornecedor"] for l in ordem],
                      "notas": notas,
                      "primeiro_elegivel": next((l["fornecedor"] for l in ordem if l["status_gate"] != "REPROVA"),
                                                None)})

    def robusto(ids):
        if not ids:
            return None
        vitorias = {f: sum(1 for c in saida if [o for o in c["ordem"] if o in ids][0] == f) for f in ids}
        media = {f: sum([o for o in c["ordem"] if o in ids].index(f) + 1 for c in saida) / len(saida) for f in ids}
        return sorted(ids, key=lambda f: (-vitorias[f], media[f]))[0], vitorias, media

    todos = [l["fornecedor"] for l in base]
    eleg = [l["fornecedor"] for l in base if l["status_gate"] != "REPROVA"]
    r_todos, r_eleg = robusto(todos), robusto(eleg)
    return {"delta_pp": delta, "cenarios": saida,
            "robusto": r_todos[0], "vitorias": r_todos[1], "posicao_media": {k: round(v, 2) for k, v in r_todos[2].items()},
            "robusto_elegivel": r_eleg[0] if r_eleg else None,
            "estavel": len({c["ordem"][0] for c in saida}) == 1}


def cenarios_gate(linhas: list, gates: dict) -> list:
    """Recomendação por cenário de gate: leitura estrita, cada gate eliminatório flexibilizado isoladamente e todos
    flexibilizados (mérito). Mostra quem elimina quem e quem vira o melhor elegível."""
    por_forn = gates.get("fornecedores") or {}
    ids = [l["fornecedor"] for l in linhas]

    def melhor(ignorar: set):
        eleg = []
        for fid in ids:
            linhas_g = [g for g in (por_forn.get(fid) or {}).get("gates") or [] if g["gate"] not in ignorar]
            if gates_mod.status(linhas_g)["status"] != "REPROVA":
                eleg.append(fid)
        return (eleg[0] if eleg else None), eleg

    base_melhor, base_eleg = melhor(set())
    saida = [{"cenario": "Gates estritos (leitura literal)", "gates_flexibilizados": [], "melhor": base_melhor,
              "elegiveis": base_eleg, "passam_a_elegiveis": []}]
    eliminatorios = [g["id"] for g in gates.get("gates") or [] if g.get("eliminatorio", True)]
    for gid in eliminatorios:
        reprovados = [fid for fid in ids if any(g["gate"] == gid and g["eliminatorio"] and g["veredito"] == "NAO"
                                                for g in (por_forn.get(fid) or {}).get("gates") or [])]
        if not reprovados:
            continue
        m, eleg = melhor({gid})
        saida.append({"cenario": f"{gid} flexibilizado", "gates_flexibilizados": [gid], "reprovados_pelo_gate": reprovados,
                      "melhor": m, "elegiveis": eleg, "passam_a_elegiveis": [f for f in eleg if f not in base_eleg]})
    if len(saida) > 1:
        saida.append({"cenario": "Todos os gates flexibilizados (só mérito)", "gates_flexibilizados": eliminatorios,
                      "melhor": ids[0] if ids else None, "elegiveis": ids,
                      "passam_a_elegiveis": [f for f in ids if f not in base_eleg]})
    return saida
