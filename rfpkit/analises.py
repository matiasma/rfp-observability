"""Análises internas geradas a partir dos artefatos do estudo (02-analise/, uso interno — NÃO enviar ao cliente):

- eliminatorios.md             gates de qualificação (quem elimina quem, leituras estrita × flexibilizada, overrides,
                               dúvidas ligadas) + requisitos eliminatórios do edital (com a resposta, no modo proponente)
- ranking.md                   régua e método, matriz de aderência, scorecard, duas lentes, sensibilidade, recomendação
                               por cenário de gate, esforço × custo e battlecards (modo proponente)
- duvidas-interna.md           versão estratégica das dúvidas (por que perguntamos, resposta desejada, impacto, status,
                               retiradas)
- cases-referencia-maturidade.md  cases pontuados pela rubrica 0–10 e verificação das URLs
- esforco-custo.md             esforço de POC por frente, estimativa de custo (list price) e cruzamento
"""
import datetime as dt
import re
from collections import defaultdict

from . import __version__, util
from . import esforco_custo as ec
from .evidencias import _c, _tabela, referencias_do_estudo
from .kb import NOME_QUADRANTE, KB

ROTULO = {"PASSA": "PASSA", "RISCO": "RISCO", "INDEFINIDO": "INDEFINIDO", "NAO": "NÃO", "REPROVA": "REPROVA"}
RUBRICA_CASES = (("solucao", "Produto do proponente como solução principal (verificado pelo conteúdo)", 4.0),
                 ("setor", "Setor/cenário do cliente", 3.0),
                 ("escala", "Escala e picos sazonais", 1.5),
                 ("capacidades", "Capacidades pedidas no edital (APM, RUM, alertas, AIOps, DR…)", 1.5))


def _cab(projeto, titulo: str, fontes: str) -> list:
    return [f"# {titulo}", "",
            f"_{projeto.cfg['cliente']['nome']} · referência {projeto.data_ref.isoformat()} · gerado pelo kit "
            f"v{__version__} em {dt.date.today().isoformat()} a partir de {fontes}. **Uso interno — não enviar ao "
            "cliente.** Não edite este arquivo: altere as entradas e rode `python kit.py tudo`._", ""]


def _nome(kb, ranking, fid):
    return next((l["nome"] for l in ranking.get("ranking") or [] if l["fornecedor"] == fid), None) or kb.nome(fid)


def _nomes(kb, ranking, ids) -> str:
    return ", ".join(_nome(kb, ranking, f) for f in ids) or "—"


# ---------------------------------------------------------------- eliminatórios
def _numero_clausula(texto: str):
    m = re.match(r"^\s*(\d+(?:\.\d+)+)", str(texto or ""))
    return m.group(1) if m else None


def eliminatorios_md(projeto, kb, ranking, gates, rtm) -> list:
    L = _cab(projeto, "Gates e requisitos eliminatórios", "gates.json, ranking.json, rtm.json e duvidas.yaml")
    gcfg = gates.get("gates") or []
    triagem = ranking.get("triagem") or []
    por_forn = gates.get("fornecedores") or {}
    L += ["## 1. Gates de qualificação (pass/fail antes do mérito)", ""]
    if not gcfg:
        L += ["Nenhum gate configurado no rfp.yaml.", ""]
    else:
        L += _tabela(["Gate", "Cláusula do edital", "Regra", "Eliminatório"],
                     [[g["id"], g.get("clausula"), g.get("regra"), "sim" if g.get("eliminatorio", True) else "não"]
                      for g in gcfg])
        L += ["", "### 1.1 Veredito por fornecedor", ""]
        linhas = []
        for t in triagem:
            vg = {l["gate"]: l for l in (por_forn.get(t["id"]) or {}).get("gates") or []}
            linhas.append([t["nome"], t.get("origem")] + [ROTULO.get((vg.get(g["id"]) or {}).get("veredito"), "—")
                                                          for g in gcfg] + [ROTULO.get(t.get("status_gate"), "—")])
        L += _tabela(["Fornecedor", "Origem"] + [g["id"] for g in gcfg] + ["Resultado"], linhas)
        L += ["", "### 1.2 Qual gate elimina quem", ""]
        linhas = []
        for g in gcfg:
            nao = [t["nome"] for t in triagem for l in (por_forn.get(t["id"]) or {}).get("gates") or []
                   if l["gate"] == g["id"] and l["veredito"] == "NAO"]
            duv = [t["nome"] for t in triagem for l in (por_forn.get(t["id"]) or {}).get("gates") or []
                   if l["gate"] == g["id"] and l["veredito"] in ("RISCO", "INDEFINIDO")]
            linhas.append([g["id"], "sim" if g.get("eliminatorio", True) else "não", ", ".join(nao) or "—",
                           ", ".join(duv) or "—"])
        L += _tabela(["Gate", "Eliminatório", "Reprova", "Risco / indefinido"], linhas)
        L += ["", "### 1.3 Justificativas e fontes", ""]
        linhas = []
        for t in triagem:
            for l in (por_forn.get(t["id"]) or {}).get("gates") or []:
                fontes = "; ".join(f"{f.get('fato')}: {f.get('fonte') or 'sem fonte'} ({f.get('verificado_em') or 's/d'})"
                                   for f in l.get("fatos") or [])
                linhas.append([l["gate"], t["nome"], ROTULO.get(l["veredito"]), l.get("justificativa"), fontes,
                               "sim" if l.get("override") else "—"])
        L += _tabela(["Gate", "Fornecedor", "Veredito", "Justificativa", "Fatos (fonte, data)", "Override"], linhas)
        cen = ranking.get("cenarios_gate") or []
        if cen:
            L += ["", "### 1.4 Leituras do gate — estrita × flexibilizada", ""]
            L += _tabela(["Cenário", "Melhor elegível (por nota final)", "Elegíveis", "Passam a elegíveis"],
                         [[c["cenario"], _nome(kb, ranking, c["melhor"]) if c.get("melhor") else "nenhum",
                           _nomes(kb, ranking, c.get("elegiveis") or []),
                           _nomes(kb, ranking, c.get("passam_a_elegiveis") or [])] for c in cen])
        overrides = [o for o in util.ler_yaml(projeto.dir_analise / "gates-override.yaml", []) or []
                     if isinstance(o, dict)]
        if overrides:
            L += ["", "### 1.5 Overrides deste edital (gates-override.yaml)", ""]
            L += _tabela(["Fornecedor", "Gate", "Veredito", "Justificativa", "Fonte"],
                         [[kb.nome(o.get("fornecedor")), o.get("gate"), o.get("veredito"), o.get("justificativa"),
                           o.get("fonte")] for o in overrides])
        from .duvidas import carregar, enviavel
        ligadas = []
        for d in carregar(projeto):
            texto = " ".join(str(d.get(k) or "") for k in ("referencia", "pergunta", "objetivo", "tema"))
            gates_d = d.get("gates") if isinstance(d.get("gates"), list) else []
            alvo = [g["id"] for g in gcfg
                    if g["id"] in gates_d or re.search(rf"\b{re.escape(g['id'])}\b", texto)
                    or (_numero_clausula(g.get("clausula"))
                        and re.search(rf"(?<![\d.]){re.escape(_numero_clausula(g.get('clausula')))}(?!\.?\d)", texto))]
            if alvo:
                ligadas.append([d.get("id"), ", ".join(alvo), d.get("pergunta"),
                                "enviar" if enviavel(d) else "retirada"])
        if ligadas:
            L += ["", "### 1.6 Dúvidas que podem reabrir um gate", ""]
            L += _tabela(["Dúvida", "Gate", "Pergunta", "Situação"], ligadas)

    elim = [r for r in rtm.get("requisitos") or [] if r.get("obrigatoriedade") == "eliminatorio"]
    L += ["", f"## 2. Requisitos eliminatórios do edital ({len(elim)})", ""]
    if not elim:
        return L + ["Nenhum requisito classificado como eliminatório na RTM."]
    proponente = projeto.cfg.get("modo") == "proponente"
    respostas = {}
    if proponente:
        from .respostas import nivel
        for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
            if r.get("resposta") and not r.get("_orfa"):
                respostas[r["id"]] = (r["resposta"], nivel(r["resposta"], r.get("escala") or
                                                           projeto.cfg["respostas"]["escala"]))
        cont = defaultdict(int)
        for r in elim:
            cont[(respostas.get(r["id"]) or ("", "sem resposta"))[1] or "sem resposta"] += 1
        L += ["Situação da resposta do proponente: " + " · ".join(f"{k} {v}" for k, v in sorted(cont.items())), ""]
    notas = {l["fornecedor"]: l.get("notas") or {} for l in ranking.get("ranking") or []}
    grupos = defaultdict(list)
    for r in elim:
        grupos[f"{r.get('fonte')} — {r.get('secao')}".strip(" —") if r.get("secao") else r.get("fonte")].append(r)
    for grupo, itens in grupos.items():
        L += ["", f"### {grupo} ({len(itens)})", ""]
        if proponente:
            L += _tabela(["ID", "Categoria", "Requisito", "Resposta", "Situação"],
                         [[r["id"], r.get("categoria"), r.get("texto"), (respostas.get(r["id"]) or ("—",))[0],
                           "⚠️ " + respostas[r["id"]][1] if r["id"] in respostas and respostas[r["id"]][1]
                           in ("parcial", "nao") else (respostas.get(r["id"]) or ("", "sem resposta"))[1]]
                          for r in itens])
        else:
            L += _tabela(["ID", "Categoria", "Requisito", "Fornecedores com nota ≤ 0,5 na categoria"],
                         [[r["id"], r.get("categoria"), r.get("texto"),
                           ", ".join(_nome(kb, ranking, f) for f, n in notas.items()
                                     if n.get(r.get("categoria")) is not None and n[r["categoria"]] <= 0.5) or "—"]
                          for r in itens])
    return L


# ---------------------------------------------------------------- ranking
def battlecards(projeto, kb, ranking) -> list:
    """Concorrentes × proponente: onde cada um é mais forte, pela diferença de nota ponderada pelo peso do edital."""
    prop = projeto.cfg.get("proponente")
    linhas = {l["fornecedor"]: l for l in ranking.get("ranking") or []}
    if projeto.cfg.get("modo") != "proponente" or prop not in linhas:
        return []
    cats = {c["id"]: c for c in ranking.get("categorias") or []}
    base = linhas[prop]["notas"]
    edicao = kb.edicao_vigente(projeto.data_ref)
    cards = []
    for fid, l in linhas.items():
        if fid == prop:
            continue
        difs = []
        for cid, c in cats.items():
            a, b = l["notas"].get(cid), base.get(cid)
            if a is None or b is None or abs(a - b) < 0.25:
                continue
            difs.append((c["peso"] * (a - b), c["nome"], a, b, c["peso"]))
        forn = kb.fornecedores.get(fid) or {}
        cards.append({"fornecedor": fid, "nome": l["nome"], "gate": l["status_gate"],
                      "gartner": NOME_QUADRANTE.get(kb.posicao(edicao, fid)) if edicao else "—",
                      "aderencia_pct": l.get("aderencia_pct"), "nota_final": l.get("nota_final"),
                      "reprovados": l.get("gates_reprovados"), "riscos": l.get("gates_risco"),
                      "mais_forte": [d[1:] for d in sorted([d for d in difs if d[0] > 0], key=lambda d: -d[0])[:5]],
                      "proponente_mais_forte": [d[1:] for d in sorted([d for d in difs if d[0] < 0], key=lambda d: d[0])[:5]],
                      "destaques": forn.get("destaques") or [], "gaps": forn.get("gaps") or []})
    return cards


def ranking_md(projeto, kb, ranking, esforco, custo) -> list:
    L = _cab(projeto, "Ranking de mérito e inteligência competitiva", "ranking.json, gates.json, eixos.yaml, "
                                                                        "esforco-poc.yaml e custo.yaml")
    eixos = ranking.get("eixos") or {}
    forn = ranking.get("ranking") or []
    L += ["## 1. Régua e método", "",
          "- Aderência = média das notas por categoria (régua 1,0 nativo-líder · 0,75 forte · 0,5 parcial/por extensão · "
          "0,25 fraco · 0 não atende) ponderada pela massa de requisitos do edital em cada categoria.",
          "- Nota final (0–5) = " + " + ".join(f"{util.br(p / 100, 2)}·{k}" for k, p in eixos.items()) +
          "; aderência convertida para 0–5. Risco, esforço, custo e estratégico vêm de `eixos.yaml` (com justificativa).",
          "- Gate antes do mérito: nenhum eixo compensa um gate eliminatório reprovado.",
          "- Confiança da KB por fornecedor: " + ", ".join(f"{l['nome']} {l.get('confianca') or '—'}" for l in forn) + ".",
          ""]
    L += ["## 2. Matriz de aderência por categoria", ""]
    L += _tabela(["Categoria", "Peso"] + [l["nome"] for l in forn],
                 [[c["nome"], util.br(c["peso"])] + [util.br(l["notas"].get(c["id"]), 2) +
                                                     ("*" if l["origem_notas"].get(c["id"]) == "ajuste" else "")
                                                     for l in forn] for c in ranking.get("categorias") or []]
                 + [["**Aderência ponderada**", "100"] + [f"**{util.br(l.get('aderencia_pct'))}%**" for l in forn]])
    L += ["", "_* nota ajustada para este edital (ajustes-notas.yaml)._", "", "## 3. Scorecard multi-eixo (0–5)", ""]
    L += _tabela(["#", "Fornecedor", "Aderência %", "Risco", "Esforço", "Custo", "Estratégico", "Nota final", "Gate"],
                 [[l["posicao"], l["nome"], util.br(l.get("aderencia_pct")), util.br(l.get("risco")),
                   util.br(l.get("esforco")), util.br(l.get("custo")), util.br(l.get("estrategico")),
                   util.br(l.get("nota_final"), 2), ROTULO.get(l["status_gate"])] for l in forn])
    lentes = ranking.get("lentes") or {}
    if lentes.get("lider_aderencia"):
        L += ["", "## 4. Duas lentes", "",
              f"- **Aderência pura ao edital:** {_nome(kb, ranking, lentes['lider_aderencia'])} "
              f"({util.br(lentes.get('aderencia_pct'))}%).",
              f"- **Balanço completo (nota final):** {_nome(kb, ranking, lentes['lider_nota'])} "
              f"({util.br(lentes.get('nota_final'), 2)})." if lentes.get("lider_nota") else "- Nota final em aberto.",
              "- " + ("As duas lentes coincidem." if lentes.get("coincidem") else
                      "As lentes divergem: a decisão depende do peso dado a risco, esforço, custo e estratégia."),
              f"- **Melhor elegível no gate:** {_nome(kb, ranking, ranking['melhor_elegivel'])}."
              if ranking.get("melhor_elegivel") else "- Nenhum fornecedor passa em todos os gates eliminatórios."]
    sens = ranking.get("sensibilidade")
    if sens:
        L += ["", "## 5. Sensibilidade (o que muda o resultado)", ""]
        L += _tabela(["Cenário de pesos", "1º", "2º", "3º", "1º elegível"],
                     [[c["cenario"]] + [f"{_nome(kb, ranking, f)} ({util.br(c['notas'].get(f), 2)})"
                                        for f in c["ordem"][:3]] + [""] * (3 - len(c["ordem"][:3])) +
                      [_nome(kb, ranking, c["primeiro_elegivel"]) if c.get("primeiro_elegivel") else "—"]
                      for c in sens["cenarios"]])
        L += ["", f"- **1º robusto:** {_nome(kb, ranking, sens['robusto'])} — 1º em {sens['vitorias'][sens['robusto']]} "
                  f"de {len(sens['cenarios'])} cenários (posição média {util.br(sens['posicao_media'][sens['robusto']], 2)})."
              + (" O 1º não muda em nenhum cenário." if sens.get("estavel") else ""),
              f"- **1º robusto entre os elegíveis:** {_nome(kb, ranking, sens['robusto_elegivel'])}."
              if sens.get("robusto_elegivel") else "- Nenhum elegível com nota final completa."]
    cen = ranking.get("cenarios_gate") or []
    if len(cen) > 1:
        L += ["", "## 6. Recomendação por cenário de gate", ""]
        L += _tabela(["Cenário", "Melhor elegível", "Passam a elegíveis"],
                     [[c["cenario"], _nome(kb, ranking, c["melhor"]) if c.get("melhor") else "nenhum",
                       _nomes(kb, ranking, c.get("passam_a_elegiveis") or [])] for c in cen])
    cruz = ec.cruzamento(ranking, esforco, custo)
    if cruz:
        L += ["", "## 7. Esforço de POC × custo de produção", ""]
        L += _tabela(["Fornecedor", "Esforço POC (dias)", "Risco POC", "Custo/mês", "Anual", "Modelo", "Gate",
                      "Nota final"],
                     [[c["nome"], c["esforco"], c["risco"], c["custo_mensal"], c["custo_anual"], c["modelo"],
                       ROTULO.get(c["status_gate"]), util.br(c["nota_final"], 2)] for c in cruz])
        L += ["", "_Detalhe em `esforco-custo.md`." + (" Valores ILUSTRATIVOS." if (custo or {}).get("ilustrativo") else "")
              + "_"]
    cards = battlecards(projeto, kb, ranking)
    if cards:
        prop = kb.nome(projeto.cfg["proponente"])
        L += ["", f"## 8. Battlecards — concorrentes × {prop}", ""]
        for c in cards:
            L += [f"### {c['nome']} — {c['gartner']} no MQ · gate {ROTULO.get(c['gate'])} · aderência "
                  f"{util.br(c['aderencia_pct'])}% · nota final {util.br(c['nota_final'], 2)}", ""]
            if c["mais_forte"]:
                L.append(f"- **Mais forte que o {prop} em:** " + "; ".join(
                    f"{n} ({util.br(a, 2)} × {util.br(b, 2)}, peso {util.br(p)})" for n, a, b, p in c["mais_forte"]))
            if c["proponente_mais_forte"]:
                L.append(f"- **{prop} mais forte em:** " + "; ".join(
                    f"{n} ({util.br(b, 2)} × {util.br(a, 2)}, peso {util.br(p)})" for n, a, b, p in c["proponente_mais_forte"]))
            gates_txt = "; ".join(x for x in (f"reprova {c['reprovados']}" if c["reprovados"] not in (None, "-") else "",
                                              f"em risco {c['riscos']}" if c["riscos"] not in (None, "-") else "") if x)
            if gates_txt:
                L.append(f"- **Gates:** {gates_txt}")
            L += [f"- ✅ {d}" for d in c["destaques"][:3]] + [f"- ⚠️ {g}" for g in c["gaps"][:3]] + [""]
    return L


# ---------------------------------------------------------------- dúvidas (versão interna)
def duvidas_md(projeto) -> list:
    from .duvidas import carregar, enviavel
    duv = carregar(projeto)
    L = _cab(projeto, "Dúvidas — versão interna / estratégica (NÃO ENVIAR)", "duvidas.yaml")
    enviar = [d for d in duv if enviavel(d)]
    retiradas = [d for d in duv if not enviavel(d)]
    L += [f"Pareia com `03-entregas/duvidas-{projeto.sigla}.xlsx`"
          + (f" e a cópia PREENCHIDO de `{projeto.cfg['duvidas']['modelo']}`" if (projeto.cfg.get('duvidas') or {}).get('modelo') else "")
          + ". A coluna de pergunta enviada é neutra; o porquê e a resposta desejada ficam só aqui.", "",
          f"{len(enviar)} a enviar · {len(retiradas)} retirada(s) · status: " +
          ", ".join(f"{k} {v}" for k, v in sorted(
              {s: sum(1 for d in enviar if (d.get('status') or 'PENDENTE') == s) for s in
               {d.get('status') or 'PENDENTE' for d in enviar}}.items())), ""]
    L += _tabela(["ID", "Tema", "Referência", "Pergunta enviada", "Por que perguntamos", "Resposta desejada", "Impacto",
                  "Gates", "Prioridade", "Status"],
                 [[d.get("id"), d.get("tema"), d.get("referencia"), d.get("pergunta"), d.get("objetivo"),
                   d.get("resposta_desejada"), d.get("impacto"), d.get("gates"), d.get("prioridade"),
                   d.get("status") or "PENDENTE"] for d in enviar])
    respondidas = [d for d in enviar if d.get("resposta_cliente")]
    if respondidas:
        L += ["", "## Respostas do cliente", ""]
        L += _tabela(["ID", "Resposta do cliente", "Impacto previsto"],
                     [[d.get("id"), d.get("resposta_cliente"), d.get("impacto")] for d in respondidas])
    if retiradas:
        L += ["", "## Dúvidas retiradas (não enviar)", ""]
        L += _tabela(["ID", "Pergunta", "Motivo"],
                     [[d.get("id"), d.get("pergunta"), d.get("motivo_retirada") or d.get("objetivo")] for d in retiradas])
    return L


# ---------------------------------------------------------------- cases (maturidade)
def nota_case(c: dict):
    p = c.get("pontuacao")
    if not isinstance(p, dict):
        return None
    valores = [util.num(p.get(k)) for k, _, _ in RUBRICA_CASES]
    return round(sum(v or 0 for v in valores), 1) if any(v is not None for v in valores) else None


def _pontos(c: dict) -> dict:
    return c["pontuacao"] if isinstance(c.get("pontuacao"), dict) else {}


def validar_pontuacao(projeto, kb=None) -> list:
    prob = []
    for c in referencias_do_estudo(projeto, kb):
        p = c.get("pontuacao")
        if p is None:
            continue
        rot = c.get("kb") or c.get("organizacao") or "?"
        if not isinstance(p, dict):
            prob.append(("ERRO", f"case {rot}: 'pontuacao' deve ser um mapa (solucao, setor, escala, capacidades)"))
            continue
        for chave, _, maximo in RUBRICA_CASES:
            v = util.num(p.get(chave)) if p.get(chave) is not None else None
            if p.get(chave) is not None and (v is None or not 0 <= v <= maximo):
                prob.append(("ERRO", f"case {rot}: pontuacao.{chave}={p.get(chave)} fora de 0–{util.br(maximo)}"))
    return prob


def cases_md(projeto, kb) -> list:
    refs = [c for c in referencias_do_estudo(projeto, kb) if not c["_kb_ausente"]]
    check = {r.get("url"): r.get("situacao") for r in util.ler_csv(projeto.dir_analise / "validacao-urls.csv")}
    L = _cab(projeto, f"Casos de referência — maturidade ({kb.nome(projeto.cfg.get('proponente')) if projeto.cfg.get('proponente') else 'proponente'}) × demanda do cliente",
             "cases-referencia.yaml, kb/cases e validacao-urls.csv")
    L += ["## Rubrica de pontuação (0–10)", ""]
    L += [f"- **{chr(65 + i)}. {rot} (0–{util.br(m)})** — `pontuacao.{k}`" for i, (k, rot, m) in enumerate(RUBRICA_CASES)]
    ordenados = sorted(refs, key=lambda c: (c.get("tipo") == "arquitetura", -(nota_case(c) or -1)))
    L += ["", "## Ranking", ""]
    L += _tabela(["#", "Caso", "Tipo", "Verificação", "A", "B", "C", "D", "Nota", "Relação com o edital"],
                 [[i, c.get("organizacao") or c.get("cenario"), c.get("tipo"),
                   " / ".join(x for x in (f"KB {kb.status_evidencia(kb.referencia(c['kb']), projeto.data_ref)}"
                                          if c.get("kb") else "", f"URL {check.get(c.get('url'))}"
                                          if check.get(c.get("url")) else "") if x) or "não verificado",
                   *[util.br(util.num(_pontos(c).get(k)), 1) for k, _, _ in RUBRICA_CASES],
                   f"**{util.br(nota_case(c), 1)}**", c.get("relacao")] for i, c in enumerate(ordenados, start=1)])
    fortes = [c for c in ordenados if (nota_case(c) or 0) >= 7 and c.get("tipo") != "arquitetura"]
    L += ["", "## Uso recomendado", "",
          (f"- Citar no memorial como prova de maturidade: {', '.join(c.get('organizacao') or '?' for c in fortes)}."
           if fortes else "- Nenhum case com nota ≥ 7: use as arquiteturas de referência e não force comparação de setor."),
          "- Cases com verificação diferente de VALIDADA/OK: confira no navegador antes de citar.",
          "- Resultados sempre como publicados, sem extrapolar."]
    return L


# ---------------------------------------------------------------- esforço e custo
def esforco_custo_md(projeto, kb, ranking, esforco, custo) -> list:
    L = _cab(projeto, "Esforço de POC e estimativa de custo de produção", "esforco-poc.yaml, custo.yaml e ranking.json")
    if esforco:
        L += ["## 1. Esforço de POC por fornecedor", "", f"Unidade: {esforco['unidade']}."
              + (f" {esforco['descricao']}" if esforco.get("descricao") else ""), ""]
        forn = sorted(esforco["fornecedores"].items(), key=lambda kv: kv[1]["medio"])
        L += _tabela(["Fornecedor", "Esforço (dias)", "Médio", "% em frentes-portão", "Risco de reprovar", "Motivo"],
                     [[_nome(kb, ranking, f), ec.faixa_texto(t["min"], t["max"], 0), util.br(t["medio"], 0),
                       f"{util.br(t['pct_portoes'], 0)}%" if t.get("pct_portoes") is not None else "—", t.get("risco"),
                       t.get("motivo_risco")] for f, t in forn])
        ids = [f for f, _ in forn]
        L += ["", "## 2. Esforço por frente", ""]
        L += _tabela(["#", "Frente", "Portão"] + [_nome(kb, ranking, f) for f in ids] + ["Observação"],
                     [[fr.get("id"), fr["nome"], "sim" if fr["portao"] else "—"] +
                      [ec.faixa_texto(*fr["dias"][f], 0) if f in fr["dias"] else "—" for f in ids] + [fr.get("obs")]
                      for fr in esforco["frentes"]])
        if esforco["portoes"]:
            L += ["", f"_Frentes-portão (critérios de aceite de alto risco): {', '.join(esforco['portoes'])}._"]
    if custo:
        ilus = " (ILUSTRATIVO)" if custo["ilustrativo"] else ""
        cen = custo.get("cenario") or {}
        L += ["", f"## 3. Estimativa de custo de produção — list price{ilus}", "",
              f"Cenário de referência: {cen.get('descricao') or '—'}. Moeda: {custo['moeda']}. "
              "Estimativa indicativa, não é proposta comercial."]
        L += [f"- {p}" for p in cen.get("premissas") or []]
        forn = sorted(custo["fornecedores"].items(), key=lambda kv: kv[1]["mensal_min"])
        L += [""] + _tabela(["Fornecedor", "Custo/mês", "Anualizado", "Modelo de cobrança", "Ressalva"],
                            [[_nome(kb, ranking, f), ec.dinheiro(t["mensal_min"], t["mensal_max"], custo["moeda"]),
                              ec.dinheiro(t["anual_min"], t["anual_max"], custo["moeda"]), t.get("modelo_cobranca"),
                              t.get("ressalva")] for f, t in forn])
        L += ["", "### Preços unitários e fontes", ""]
        linhas = []
        for f, t in forn:
            for c in t["componentes"]:
                linhas.append([_nome(kb, ranking, f), c.get("item"), c.get("quantidade"), c.get("unidade"),
                               c.get("preco_unitario"), ec.dinheiro(c["valor_min"], c["valor_max"], custo["moeda"]),
                               c.get("fonte"), c.get("verificado_em")])
        L += _tabela(["Fornecedor", "Componente", "Qtde", "Unidade", "Preço unitário", "Valor/mês", "Fonte",
                      "Verificado em"], linhas)
        if custo.get("leitura"):
            L += ["", f"**Leitura:** {custo['leitura']}"]
    cruz = ec.cruzamento(ranking, esforco, custo)
    if cruz:
        L += ["", "## 4. Cruzamento esforço × custo (leitura de decisão)", ""]
        L += _tabela(["Fornecedor", "Esforço POC", "Risco POC", "Custo/mês", "Gate", "Nota final"],
                     [[c["nome"], c["esforco"], c["risco"], c["custo_mensal"], ROTULO.get(c["status_gate"]),
                       util.br(c["nota_final"], 2)] for c in cruz])
    return L


# ---------------------------------------------------------------- geração
def gerar(projeto, kb: KB | None = None) -> list:
    kb = kb or KB()
    ranking = util.ler_json(projeto.dir_analise / "ranking.json")
    gates = util.ler_json(projeto.dir_analise / "gates.json")
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json")
    if not (ranking and gates and rtm):
        raise RuntimeError("ranking ainda não calculado — rode 'python kit.py ranking' antes.")
    esforco, custo = ec.resumo_esforco(projeto), ec.resumo_custo(projeto)
    saidas = []

    def gravar(nome, linhas):
        destino = projeto.dir_analise / nome
        destino.write_text("\n".join(str(x) for x in linhas).rstrip() + "\n", encoding="utf-8")
        saidas.append(destino)

    gravar("eliminatorios.md", eliminatorios_md(projeto, kb, ranking, gates, rtm))
    gravar("ranking.md", ranking_md(projeto, kb, ranking, esforco, custo))
    from .duvidas import carregar
    if carregar(projeto):
        gravar("duvidas-interna.md", duvidas_md(projeto))
    if referencias_do_estudo(projeto, kb):
        gravar("cases-referencia-maturidade.md", cases_md(projeto, kb))
    if esforco or custo:
        gravar("esforco-custo.md", esforco_custo_md(projeto, kb, ranking, esforco, custo))
    return saidas
