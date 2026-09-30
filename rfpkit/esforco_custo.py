"""Esforço de POC (frentes × fornecedor, dias de 1 pessoa) e estimativa indicativa de custo de produção
(list price), com o cruzamento esforço × custo.

Entradas opcionais do estudo (julgamento com fonte, ver prompts/13-esforco-custo.md):
- 02-analise/esforco-poc.yaml
- 02-analise/custo.yaml
Sem os arquivos (ou com eles vazios) as seções correspondentes simplesmente não aparecem nos relatórios.
"""
import datetime as dt

from . import util
from .kb import KB

NIVEIS_RISCO = ("baixo", "medio", "alto")
TTL_PRECO_DIAS = 180


def _faixa(valor):
    """número | [min, max] -> (min, max) em float; None se ausente; ValueError se inválido."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (list, tuple)):
        if len(valor) != 2:
            raise ValueError(f"faixa deve ter 2 valores [mín, máx]: {valor}")
        a, b = util.num(valor[0]), util.num(valor[1])
    elif isinstance(valor, dict):
        raise ValueError(f"valor inválido: {valor}")
    else:
        a = b = util.num(valor)
    if a is None or b is None or a < 0 or b < 0:
        raise ValueError(f"valor inválido: {valor}")
    if a > b:
        raise ValueError(f"mínimo maior que o máximo: {valor}")
    return a, b


def _mapa(valor) -> dict:
    return valor if isinstance(valor, dict) else {}


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        return "; ".join(str(v) for v in valor)
    return str(valor)


def _risco(valor) -> dict:
    """Aceita {nivel, motivo} ou só o nível ('baixo')."""
    if isinstance(valor, dict):
        return valor
    return {"nivel": valor} if isinstance(valor, str) else {}


def _valor_componente(c: dict):
    """(mín, máx) mensal do componente: 'valor' pronto ou quantidade × preço unitário. ValueError se inválido."""
    if c.get("valor") not in (None, "", []):
        return _faixa(c["valor"])
    q, p = _faixa(c.get("quantidade")), _faixa(c.get("preco_unitario"))
    if not q or not p:
        raise ValueError("informe quantidade + preco_unitario, ou valor mensal")
    return q[0] * p[0], q[1] * p[1]


def _ler(projeto, nome):
    dados = util.ler_yaml(projeto.dir_analise / nome, None)
    return dados if isinstance(dados, dict) and dados else None


# ---------------------------------------------------------------- esforço de POC
def resumo_esforco(projeto) -> dict | None:
    dados = _ler(projeto, "esforco-poc.yaml")
    if not dados or not isinstance(dados.get("frentes"), list) or not dados["frentes"]:
        return None
    frentes, totais = [], {}
    for f in dados["frentes"]:
        if not isinstance(f, dict):
            continue
        dias = {}
        for fid, v in _mapa(f.get("dias")).items():
            try:
                faixa = _faixa(v)
            except (ValueError, TypeError):
                faixa = None
            if faixa:
                dias[fid] = faixa
                t = totais.setdefault(fid, {"min": 0.0, "max": 0.0, "portoes_min": 0.0, "portoes_max": 0.0})
                t["min"] += faixa[0]
                t["max"] += faixa[1]
                if f.get("portao"):
                    t["portoes_min"] += faixa[0]
                    t["portoes_max"] += faixa[1]
        frentes.append({"id": _texto(f.get("id")) or None, "nome": _texto(f.get("nome") or f.get("id")),
                        "referencia": _texto(f.get("referencia")), "portao": bool(f.get("portao")),
                        "obs": _texto(f.get("obs")), "dias": dias})
    riscos = _mapa(dados.get("risco"))
    for fid, t in totais.items():
        t["medio"] = round((t["min"] + t["max"]) / 2, 1)
        t["pct_portoes"] = round(100 * (t["portoes_min"] + t["portoes_max"]) / (t["min"] + t["max"]), 0) \
            if (t["min"] + t["max"]) else None
        r = _risco(riscos.get(fid))
        t["risco"] = util.norm(_texto(r.get("nivel"))) or None
        t["motivo_risco"] = _texto(r.get("motivo")) or None
    return {"unidade": _texto(dados.get("unidade")) or "dias úteis, 1 pessoa", "descricao": _texto(dados.get("descricao")),
            "frentes": frentes, "fornecedores": totais, "portoes": [f["nome"] for f in frentes if f["portao"]]}


# ---------------------------------------------------------------- custo
def resumo_custo(projeto) -> dict | None:
    dados = _ler(projeto, "custo.yaml")
    if not dados or not isinstance(dados.get("fornecedores"), dict) or not dados["fornecedores"]:
        return None
    forn = {}
    for fid, d in dados["fornecedores"].items():
        if not isinstance(d, dict):
            continue
        comps, tmin, tmax = [], 0.0, 0.0
        for c in d.get("componentes") or [] if isinstance(d.get("componentes"), list) else []:
            if not isinstance(c, dict):
                continue
            try:
                vmin, vmax = _valor_componente(c)
            except (ValueError, TypeError):
                continue
            tmin += vmin
            tmax += vmax
            comps.append({"item": _texto(c.get("item")), "quantidade": c.get("quantidade") if not isinstance(
                              c.get("quantidade"), (dict, list)) else _texto(c.get("quantidade")),
                          "unidade": _texto(c.get("unidade")),
                          "preco_unitario": c.get("preco_unitario") if not isinstance(
                              c.get("preco_unitario"), (dict, list)) else _texto(c.get("preco_unitario")),
                          "fonte": _texto(c.get("fonte")), "verificado_em": _texto(c.get("verificado_em")),
                          "valor_min": round(vmin, 2), "valor_max": round(vmax, 2)})
        forn[fid] = {"modelo_cobranca": _texto(d.get("modelo_cobranca")), "ressalva": _texto(d.get("ressalva")),
                     "componentes": comps, "mensal_min": round(tmin, 2), "mensal_max": round(tmax, 2),
                     "anual_min": round(tmin * 12, 2), "anual_max": round(tmax * 12, 2)}
    cenario = dados.get("cenario") or {}
    cenario = cenario if isinstance(cenario, dict) else {"descricao": _texto(cenario)}
    cenario = {"descricao": _texto(cenario.get("descricao")),
               "premissas": [_texto(x) for x in cenario.get("premissas") or [] if x] if isinstance(
                   cenario.get("premissas"), list) else ([_texto(cenario["premissas"])] if cenario.get("premissas") else [])}
    return {"moeda": _texto(dados.get("moeda")) or "USD", "ilustrativo": bool(dados.get("ilustrativo")),
            "cenario": cenario, "leitura": _texto(dados.get("leitura")), "fornecedores": forn}


def faixa_texto(vmin, vmax, casas: int = 1, sufixo: str = "") -> str:
    if vmin is None:
        return "—"
    if abs((vmax or vmin) - vmin) < 1e-9:
        return f"{util.br(vmin, casas)}{sufixo}"
    return f"{util.br(vmin, casas)}–{util.br(vmax, casas)}{sufixo}"


def dinheiro(vmin, vmax, moeda: str = "USD") -> str:
    """US$ 10,5k ou US$ 2,3k–4,0k (valores mensais/anuais do estudo)."""
    if vmin is None:
        return "—"
    simbolo = {"USD": "US$", "BRL": "R$", "EUR": "€"}.get(str(moeda).upper(), str(moeda))

    def k(v):
        return f"{util.br(v / 1000, 1)}k" if v >= 1000 else util.br(v, 0)
    return f"{simbolo} {k(vmin)}" if abs(vmax - vmin) < 1e-9 else f"{simbolo} {k(vmin)}–{k(vmax)}"


# ---------------------------------------------------------------- cruzamento
def cruzamento(ranking: dict, esforco: dict | None, custo: dict | None) -> list:
    if not esforco and not custo:
        return []
    linhas = []
    for l in ranking.get("ranking") or []:
        fid = l["fornecedor"]
        e = (esforco or {}).get("fornecedores", {}).get(fid)
        c = (custo or {}).get("fornecedores", {}).get(fid)
        if not e and not c:
            continue
        linhas.append({"fornecedor": fid, "nome": l["nome"], "status_gate": l["status_gate"],
                       "nota_final": l.get("nota_final"),
                       "esforco": faixa_texto(e["min"], e["max"], 0) + (f" (~{util.br(e['medio'], 0)})" if e else "")
                       if e else "—",
                       "risco": (e or {}).get("risco") or "—",
                       "custo_mensal": dinheiro(c["mensal_min"], c["mensal_max"], custo["moeda"]) if c else "—",
                       "custo_anual": dinheiro(c["anual_min"], c["anual_max"], custo["moeda"]) if c else "—",
                       "modelo": (c or {}).get("modelo_cobranca") or "—"})
    return linhas


# ---------------------------------------------------------------- validação
def _coerencia_eixo(ranking: dict, medida: dict, eixo: str, rotulo: str) -> list:
    """Menor esforço/custo deve ter nota de eixo maior ou igual (escala: maior = melhor)."""
    prob = []
    notas = {l["fornecedor"]: l.get(eixo) for l in ranking.get("ranking") or []}
    ids = [f for f in medida if notas.get(f) is not None]
    for a in ids:
        for b in ids:
            if a < b:
                ma, mb = medida[a], medida[b]
                if ma < mb * 0.8 and notas[a] < notas[b]:
                    prob.append(("AVISO", f"eixo {eixo}: {a} tem {rotulo} menor que {b} mas nota menor "
                                          f"({util.br(notas[a])} < {util.br(notas[b])}) — revise eixos.yaml"))
                elif mb < ma * 0.8 and notas[b] < notas[a]:
                    prob.append(("AVISO", f"eixo {eixo}: {b} tem {rotulo} menor que {a} mas nota menor "
                                          f"({util.br(notas[b])} < {util.br(notas[a])}) — revise eixos.yaml"))
    return prob


def validar(projeto, kb: KB | None = None, ranking: dict | None = None) -> list:
    kb = kb or KB()
    ranking = ranking or util.ler_json(projeto.dir_analise / "ranking.json") or {}
    prob = []
    bruto = util.ler_yaml(projeto.dir_analise / "esforco-poc.yaml", None)
    if bruto not in (None, {}, []) and not isinstance(bruto, dict):
        prob.append(("ERRO", "esforco-poc.yaml deve ser um mapa com 'frentes:' (ver o modelo)"))
    elif isinstance(bruto, dict):
        frentes = bruto.get("frentes")
        if frentes is not None and not isinstance(frentes, list):
            prob.append(("ERRO", "esforco-poc.yaml: 'frentes' deve ser uma lista"))
            frentes = []
        for f in frentes or []:
            if not isinstance(f, dict):
                prob.append(("ERRO", f"esforco-poc.yaml: frente '{str(f)[:30]}' inválida"))
                continue
            rot = f"esforco-poc.yaml: frente {f.get('id') or f.get('nome')}"
            if f.get("dias") is not None and not isinstance(f.get("dias"), dict):
                prob.append(("ERRO", f"{rot}: 'dias' deve ser um mapa fornecedor: [mín, máx]"))
                continue
            for fid, v in _mapa(f.get("dias")).items():
                if fid not in kb.fornecedores:
                    prob.append(("AVISO", f"esforco-poc.yaml: fornecedor '{fid}' sem ficha na KB"))
                try:
                    _faixa(v)
                except (ValueError, TypeError) as e:
                    prob.append(("ERRO", f"{rot} × {fid}: {e}"))
        risco = bruto.get("risco")
        if risco is not None and not isinstance(risco, dict):
            prob.append(("ERRO", "esforco-poc.yaml: 'risco' deve ser um mapa fornecedor: {nivel, motivo}"))
        for fid, r in _mapa(risco).items():
            nivel = _risco(r).get("nivel")
            if nivel and util.norm(_texto(nivel)) not in NIVEIS_RISCO:
                prob.append(("AVISO", f"esforco-poc.yaml: risco de {fid} '{nivel}' fora de baixo/medio/alto"))
    bruto = util.ler_yaml(projeto.dir_analise / "custo.yaml", None)
    if bruto not in (None, {}, []) and not isinstance(bruto, dict):
        prob.append(("ERRO", "custo.yaml deve ser um mapa com 'fornecedores:' (ver o modelo)"))
    elif isinstance(bruto, dict):
        ilustrativo = bool(bruto.get("ilustrativo"))
        fornecedores = bruto.get("fornecedores")
        if fornecedores is not None and not isinstance(fornecedores, dict):
            prob.append(("ERRO", "custo.yaml: 'fornecedores' deve ser um mapa id-do-fornecedor: {...}"))
        for fid, d in _mapa(fornecedores).items():
            if fid not in kb.fornecedores:
                prob.append(("AVISO", f"custo.yaml: fornecedor '{fid}' sem ficha na KB"))
            if not isinstance(d, dict):
                prob.append(("ERRO", f"custo.yaml: {fid} deve ser um mapa com 'componentes'"))
                continue
            comps = d.get("componentes")
            if comps is not None and not isinstance(comps, list):
                prob.append(("ERRO", f"custo.yaml: {fid}: 'componentes' deve ser uma lista"))
                continue
            for c in comps or []:
                rot = f"custo.yaml: {fid} × {c.get('item') if isinstance(c, dict) else c}"
                if not isinstance(c, dict):
                    prob.append(("ERRO", f"{rot}: componente inválido"))
                    continue
                try:
                    _valor_componente(c)
                except (ValueError, TypeError) as e:
                    prob.append(("ERRO", f"{rot}: {e}"))
                if c.get("fonte") is not None and not isinstance(c.get("fonte"), str):
                    prob.append(("ERRO", f"{rot}: 'fonte' deve ser uma URL (texto), não {type(c['fonte']).__name__}"))
                if ilustrativo:
                    continue
                if not str(c.get("fonte") or "").startswith("http"):
                    prob.append(("AVISO", f"{rot}: preço sem fonte oficial (URL)"))
                try:
                    verif = util.para_data(c.get("verificado_em"))
                except (ValueError, TypeError):
                    verif = None
                    prob.append(("ERRO", f"{rot}: verificado_em inválido — use AAAA-MM-DD"))
                if c.get("verificado_em") in (None, ""):
                    prob.append(("AVISO", f"{rot}: preço sem data de verificação"))
                elif verif and verif + dt.timedelta(days=TTL_PRECO_DIAS) < projeto.data_ref:
                    prob.append(("AVISO", f"{rot}: preço verificado em {verif} (> {TTL_PRECO_DIAS} dias) — revalidar"))
    esf, cus = resumo_esforco(projeto), resumo_custo(projeto)
    if esf:
        prob += _coerencia_eixo(ranking, {f: t["medio"] for f, t in esf["fornecedores"].items()}, "esforco", "esforço")
    if cus:
        prob += _coerencia_eixo(ranking, {f: (t["mensal_min"] + t["mensal_max"]) / 2
                                          for f, t in cus["fornecedores"].items()}, "custo", "custo")
    return prob


def urls_de_preco(projeto) -> list:
    """[(url, uso)] das fontes de preço — entram em 'validar-urls'."""
    custo = resumo_custo(projeto)
    saida = []
    for fid, d in (custo or {}).get("fornecedores", {}).items():
        for c in d["componentes"]:
            if str(c.get("fonte") or "").startswith("http"):
                saida.append((str(c["fonte"]).strip(), f"preço {fid}: {c.get('item')}"))
    return saida
