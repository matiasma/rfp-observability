"""Evidências do estudo.

- Registro de alegações (02-analise/registro-evidencias.yaml): cada afirmação que sustenta uma decisão do estudo
  (gate, direcionamento, resposta negativa, risco), com fonte, citação literal, confiança e impacto.
- Cases e arquiteturas de referência (02-analise/cases-referencia.yaml), próprios do estudo ou apontando para kb/cases.
- Dossiês em 00-projeto/evidencias/: retrato, na data de referência, de tudo o que sustentou notas, gates e
  respostas — o estudo continua auditável mesmo depois que a KB evoluir.
"""
import datetime as dt
import re
from collections import Counter

from . import __version__, util
from .kb import FATOS, NOME_QUADRANTE, KB

CONFIANCAS = ("alta", "media", "baixa")
TTL_REGISTRO_DIAS = 180


def _c(valor) -> str:
    """Valor pronto para célula de tabela markdown."""
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, (list, tuple)):
        valor = ", ".join(str(v) for v in valor)
    return str(valor).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _tabela(cab: list, linhas: list) -> list:
    saida = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    saida += ["| " + " | ".join(_c(v) for v in l) + " |" for l in linhas]
    return saida


def _checagens_url(projeto) -> dict:
    return {r.get("url"): r for r in util.ler_csv(projeto.dir_analise / "validacao-urls.csv")}


# ---------------------------------------------------------------- registro de alegações
def _lista(valor) -> list:
    if valor in (None, ""):
        return []
    return list(valor) if isinstance(valor, (list, tuple)) else [valor]


def _data(valor):
    """(data, erro) — datas digitadas à mão fora de AAAA-MM-DD viram erro de validação, não exceção."""
    try:
        return util.para_data(valor), None
    except ValueError:
        return None, f"data '{valor}' inválida — use AAAA-MM-DD"


def _bruto(projeto, nome: str) -> list:
    dados = util.ler_yaml(projeto.dir_analise / nome, []) or []
    return dados if isinstance(dados, list) else [dados]


def _resolver_alegacao(e: dict, kb: KB) -> dict:
    base = kb.evidencia(e.get("kb")) if e.get("kb") else None
    item = dict(e)
    if base:
        item.setdefault("fornecedor", base.get("fornecedor"))
        item["fonte"] = item.get("fonte") or base.get("url")
        item["alegacao"] = item.get("alegacao") or base.get("alegacao") or base.get("capacidade")
        item["citacoes"] = item.get("citacoes") or base.get("citacoes") or _lista(base.get("citacao"))
        item["data_acesso"] = item.get("data_acesso") or base.get("verificado_em")
    item["citacoes"] = _lista(item.get("citacoes"))
    item["palavras_chave"] = _lista(item.get("palavras_chave"))
    return item


def carregar_registro(projeto, kb: KB | None = None) -> list:
    """Itens do registro com os campos herdados da KB quando 'kb: EV-...' é usado (url, alegação, citações)."""
    kb = kb or KB()
    return [_resolver_alegacao(e, kb) for e in _bruto(projeto, "registro-evidencias.yaml") if isinstance(e, dict)]


def _citacoes_varias_paginas(eid, e: dict, fontes: list, checagem: dict) -> list:
    """Fonte com várias URLs: cada citação precisa estar em alguma delas (a checagem por URL não acusa isso)."""
    linhas = [checagem.get(u) for u in fontes]
    if len(fontes) < 2 or not all(linhas):
        return []
    conferidas = {c for l in linhas for c in (l.get("_conferidas") or [])}
    inconclusivo = any(l.get("situacao") in ("BLOQUEADA", "NAVEGADOR") or l.get("_ausentes") is None for l in linhas)
    prob = []
    for c in map(str, e.get("citacoes") or []):
        if not util.trechos_citacao(c) or c in conferidas:
            continue
        if inconclusivo:
            prob.append(("AVISO", f"{eid}: citação não confirmada automaticamente nas páginas da fonte — conferir no "
                                  f"navegador: {c[:70]}"))
        else:
            prob.append(("ERRO", f"{eid}: citação não encontrada em nenhuma das páginas da fonte (CITACAO_AUSENTE): {c[:70]}"))
    return prob


def validar_registro(projeto, kb: KB | None = None) -> list:
    """[(nível, mensagem)] do registro de alegações."""
    kb = kb or KB()
    arquivo = projeto.dir_analise / "registro-evidencias.yaml"
    if arquivo.exists() and not isinstance(util.ler_yaml(arquivo, []) or [], list):
        return [("ERRO", "registro-evidencias.yaml deve ser uma lista de alegações (itens começando com '- id:')")]
    prob, vistos = [], set()
    from .urls import urls_do_texto
    try:
        checagem = {r.get("url"): r for r in util.ler_json(projeto.dir_analise / "validacao-urls.json", []) or []
                    if isinstance(r, dict)}
    except ValueError:
        checagem = {}
    for bruto in _bruto(projeto, "registro-evidencias.yaml"):
        if not isinstance(bruto, dict):
            prob.append(("ERRO", f"registro-evidencias.yaml: item '{str(bruto)[:40]}' não é uma alegação "
                                 "(esperado: id, alegacao, fonte… ou id + kb)"))
            continue
        e = _resolver_alegacao(bruto, kb)
        eid = e.get("id")
        if not eid:
            prob.append(("ERRO", f"alegação sem id: {str(e.get('alegacao') or e.get('kb'))[:60]}"))
            continue
        if eid in vistos:
            prob.append(("ERRO", f"{eid}: id repetido"))
        vistos.add(eid)
        for campo in ("citacoes", "usado_em", "palavras_chave"):
            if bruto.get(campo) is not None and not isinstance(bruto.get(campo), list):
                prob.append(("ERRO", f"{eid}: '{campo}' deve ser lista"))
        if e.get("kb") and not kb.evidencia(e["kb"]):
            prob.append(("ERRO", f"{eid}: evidência {e['kb']} não existe em kb/evidencias"))
        elif e.get("kb"):
            st = kb.status_evidencia(kb.evidencia(e["kb"]), projeto.data_ref)
            if st != "VALIDADA":
                prob.append(("AVISO", f"{eid}: evidência {e['kb']} com status {st} — revalidar"))
        if not e.get("alegacao"):
            prob.append(("ERRO", f"{eid}: sem 'alegacao'"))
        if e.get("confianca") and util.norm(e["confianca"]) not in CONFIANCAS:
            prob.append(("AVISO", f"{eid}: confiança '{e['confianca']}' fora de {'/'.join(CONFIANCAS)}"))
        fonte = str(e.get("fonte") or "").strip()
        if not fonte:
            prob.append(("ERRO", f"{eid}: sem 'fonte' (URL oficial ou 'edital: <arquivo> <item>') nem 'kb'"))
            continue
        acesso, erro = _data(e.get("data_acesso"))
        if erro:
            prob.append(("ERRO", f"{eid}: data_acesso {erro}"))
        if fonte.startswith("http"):
            if not e.get("citacoes"):
                prob.append(("AVISO", f"{eid}: sem citação literal da fonte ('citacoes')"))
            if not acesso and not erro:
                prob.append(("AVISO", f"{eid}: sem 'data_acesso'"))
            elif acesso and acesso + dt.timedelta(days=TTL_REGISTRO_DIAS) < projeto.data_ref:
                prob.append(("AVISO", f"{eid}: fonte acessada em {acesso} (> {TTL_REGISTRO_DIAS} dias) — revalidar"))
            prob += _citacoes_varias_paginas(eid, e, urls_do_texto(fonte), checagem)
        elif not util.norm(fonte).startswith("edital"):
            prob.append(("AVISO", f"{eid}: fonte '{fonte[:50]}' não é URL nem 'edital: <arquivo> <item>'"))
    return prob


# ---------------------------------------------------------------- cases e arquiteturas
def referencias_do_estudo(projeto, kb: KB | None = None) -> list:
    """cases-referencia.yaml resolvido: itens com 'kb: REF-...' herdam os dados públicos da KB; 'relacao'
    (por que o case importa para ESTE cliente) é sempre do estudo."""
    kb = kb or KB()
    saida = []
    for c in _bruto(projeto, "cases-referencia.yaml"):
        if not isinstance(c, dict):
            continue
        base = kb.referencia(c.get("kb")) if c.get("kb") else None
        item = {**(base or {}), **{k: v for k, v in c.items() if v not in (None, "", [])}}
        item["resultados"] = _lista(item.get("resultados") or item.get("resultado"))
        item.setdefault("tipo", "case")
        item["_kb_ausente"] = bool(c.get("kb") and not base)
        saida.append(item)
    return saida


def validar_referencias(projeto, kb: KB | None = None) -> list:
    kb = kb or KB()
    prob = []
    for c in _bruto(projeto, "cases-referencia.yaml"):
        if not isinstance(c, dict):
            prob.append(("ERRO", f"cases-referencia.yaml: item '{str(c)[:40]}' não é um case "
                                 "(esperado: '- kb: REF-…' + relacao, ou os campos do case)"))
    for c in referencias_do_estudo(projeto, kb):
        rotulo = c.get("kb") or c.get("organizacao") or "?"
        if c["_kb_ausente"]:
            prob.append(("ERRO", f"case {rotulo}: referência não existe em kb/cases"))
            continue
        if not re.match(r"^https?://\S+$", str(c.get("url") or "").strip()):
            prob.append(("ERRO", f"case {rotulo}: sem URL pública válida (http/https): '{c.get('url') or ''}'"))
        if c.get("tipo") not in ("case", "arquitetura"):
            prob.append(("ERRO", f"case {rotulo}: tipo '{c.get('tipo')}' (use case ou arquitetura)"))
        if c.get("kb"):
            st = kb.status_evidencia(kb.referencia(c["kb"]), projeto.data_ref)
            if st != "VALIDADA":
                prob.append(("AVISO", f"case {rotulo}: status {st} na KB — conferir antes de citar"))
    return prob


# ---------------------------------------------------------------- dossiês
def _cabecalho(projeto, titulo: str) -> list:
    return [f"# {titulo}", "",
            f"Estudo: **{projeto.cfg['cliente']['nome']}** · data de referência: **{projeto.data_ref.isoformat()}** · "
            f"gerado em {dt.date.today().isoformat()} (kit v{__version__}).", "",
            "> Retrato da KB e do estudo nesta data. A KB é atualizada entre editais; este arquivo registra o que "
            "sustentou as decisões **deste** estudo.", ""]


def _dossie_fornecedor(projeto, kb: KB, fid: str, triagem: dict, ranking: dict, gates: dict, categorias: list,
                       registro: list) -> list:
    from .ranking import notas_efetivas
    forn = kb.fornecedores.get(fid) or {}
    linhas = _cabecalho(projeto, f"Dossiê de evidências — {kb.nome(fid)}")
    linhas += [f"- Ficha: `kb/fornecedores/{fid}.yaml` (atualizada em {forn.get('atualizado_em') or '—'}; "
               f"confiança {forn.get('confianca') or '—'}; entrega: {_c(forn.get('entrega'))})",
               f"- Origem na triagem: {triagem.get('origem') or '—'} · gates: **{triagem.get('status_gate') or '—'}** · "
               f"aderência prévia: {util.br(triagem.get('aderencia_previa_pct'))}% · avaliação completa: "
               f"{'sim' if triagem.get('avaliacao_completa') else 'não'}"]
    if ranking:
        linhas.append(f"- Ranking: {ranking.get('posicao')}º · aderência {util.br(ranking.get('aderencia_pct'))}% · "
                      f"nota final {util.br(ranking.get('nota_final'), 2)}")
    linhas += ["", "## Gartner Magic Quadrant", ""]
    linhas += _tabela(["Edição", "Posição", "Quadrante"],
                      [[h["ano"], NOME_QUADRANTE.get(h["posicao"]), h.get("titulo")]
                       for h in kb.historico(fid, projeto.data_ref)])

    linhas += ["", "## Gates eliminatórios", ""]
    gs = (gates.get("fornecedores") or {}).get(fid, {}).get("gates") or []
    if gs:
        clausulas = {g["id"]: g.get("clausula") for g in gates.get("gates") or []}
        linhas += _tabela(["Gate", "Cláusula", "Veredito", "Justificativa", "Fatos usados", "Override do estudo"],
                          [[g["gate"], clausulas.get(g["gate"]), g["veredito"], g.get("justificativa"),
                            "; ".join(f"{f['fato']}={_c(f.get('valor'))} ({f.get('status')}, {f.get('fonte') or 'sem fonte'}, "
                                      f"{f.get('verificado_em') or 's/d'})" for f in g.get("fatos") or []),
                            "sim" if g.get("override") else "—"] for g in gs])
    else:
        linhas.append("Nenhum gate configurado no rfp.yaml.")

    linhas += ["", "## Fatos da KB", ""]
    fatos = []
    for nome in FATOS:
        f = kb.fato(fid, nome, projeto.data_ref)
        valor = f.get("valor")
        if f.get("qualificador") and valor is not None:
            valor = f"{f['qualificador']} {valor}"
        fatos.append([nome, valor, f["status"], f.get("fonte"), f.get("verificado_em"), f.get("obs") or f.get("texto")])
    linhas += _tabela(["Fato", "Valor", "Status", "Fonte", "Verificado em", "Observação"], fatos)

    notas, origem = notas_efetivas(projeto, kb, fid, categorias)
    ajustes = {a["categoria"]: a for a in util.ler_yaml(projeto.dir_analise / "ajustes-notas.yaml", []) or []
               if isinstance(a, dict) and a.get("fornecedor") == fid and a.get("categoria")}
    base = forn.get("notas_base") or {}
    linhas += ["", "## Notas por categoria (peso do edital)", ""]
    tab = []
    for c in sorted(categorias, key=lambda c: -(c.get("peso") or 0)):
        cid = c["id"]
        if origem.get(cid) == "ajuste":
            obs, fontes = f"AJUSTE do estudo: {ajustes[cid].get('justificativa')}", ajustes[cid].get("fontes")
        else:
            obs, fontes = (base.get(cid) or {}).get("obs"), (base.get(cid) or {}).get("fontes")
        tab.append([c.get("nome") or cid, util.br(c.get("peso")), util.br(notas.get(cid), 2), origem.get(cid), obs,
                    fontes])
    linhas += _tabela(["Categoria", "Peso %", "Nota", "Origem", "Observação", "Fontes"], tab)

    if forn.get("destaques") or forn.get("gaps"):
        linhas += ["", "## Destaques e gaps (KB)", ""]
        linhas += [f"- ✅ {d}" for d in forn.get("destaques") or []]
        linhas += [f"- ⚠️ {g}" for g in forn.get("gaps") or []]

    bib = kb.bibliotecas.get(fid)
    if bib:
        linhas += ["", f"## Biblioteca de evidências (`kb/evidencias/{fid}.yaml`)", ""]
        linhas += _tabela(["ID", "Capacidade", "GA", "Status", "Verificado em", "URL"],
                          [[e.get("id"), e.get("capacidade"), "não" if e.get("ga") is False else "sim",
                            kb.status_evidencia({**e, "fornecedor": fid}, projeto.data_ref), e.get("verificado_em"),
                            e.get("url")] for e in bib.get("evidencias") or []])
    refs = (kb.cases.get(fid) or {}).get("referencias") or []
    if refs:
        linhas += ["", f"## Cases e arquiteturas de referência (`kb/cases/{fid}.yaml`)", ""]
        linhas += _tabela(["ID", "Tipo", "Organização", "Cenário", "Status", "URL"],
                          [[r.get("id"), r.get("tipo"), r.get("organizacao"), r.get("cenario"),
                            kb.status_evidencia({**r, "fornecedor": fid}, projeto.data_ref), r.get("url")]
                           for r in refs])
    from .investigacao import avaliacoes
    conf = {(s["id"], s["fornecedor"]): s for s in
            (util.ler_json(projeto.dir_analise / "confianca.json", {}) or {}).get("avaliacoes") or []}
    inv = [a for a in avaliacoes(projeto) if a["fornecedor"] == fid]
    if inv:
        linhas += ["", f"## Investigação dos requisitos ({len(inv)})", ""]
        linhas += _tabela(["Requisito", "Obrig.", "Atendimento", "Como", "Confiança", "Evidências", "Citação", "Lacuna"],
                          [[a["id"], a.get("obrigatoriedade"), a.get("atendimento"), a.get("como"),
                            (conf.get((a["id"], fid)) or {}).get("nivel"), a.get("evidencias"),
                            "; ".join(str(c) for c in (a.get("citacoes") or []))[:160], a.get("lacuna")] for a in inv])
    meus = [e for e in registro if e.get("fornecedor") == fid]
    if meus:
        linhas += ["", "## Alegações do estudo sobre este fornecedor (registro)", ""]
        linhas += _tabela(["ID", "Tema", "Alegação", "Confiança", "Impacto", "Fonte"],
                          [[e.get("id"), e.get("tema"), e.get("alegacao"), e.get("confianca"), e.get("impacto"),
                            e.get("fonte")] for e in meus])
    return linhas


def _gartner(projeto, kb: KB, triagem: list, gates: dict) -> list:
    linhas = _cabecalho(projeto, "Gartner Magic Quadrant — fornecedores da triagem")
    eds = kb.edicoes(projeto.data_ref)
    if not eds:
        return linhas + ["Nenhuma edição do MQ publicada até a data de referência em kb/gartner-mq.yaml."]
    vig = eds[0]
    linhas += [f"Edição vigente em {projeto.data_ref.isoformat()}: **{vig['ano']} — {vig.get('titulo')}** "
               f"(publicada em {vig.get('data_publicacao') or '—'}; confiança {vig.get('confianca') or '—'}).",
               f"Líderes: {', '.join(kb.nome(f) for f in (vig.get('quadrantes') or {}).get('lider') or [])}.", ""]
    titulos = list(dict.fromkeys(e.get("titulo") for e in eds if e.get("titulo")))
    if len(titulos) > 1:
        linhas += ["> O quadrante mudou de nome ao longo das edições (" + " → ".join(reversed(titulos)) + "). "
                   "Cláusula que cite o nome antigo é ambígua: registre a leitura adotada em dúvida ao cliente.", ""]
    anos = [int(e["ano"]) for e in eds]
    linhas += _tabela(["Fornecedor", "Origem"] + [str(a) for a in anos],
                      [[t["nome"], t.get("origem")] + [NOME_QUADRANTE.get(kb.posicao(e, t["id"])) for e in eds]
                       for t in triagem])
    regras = [g for g in gates.get("gates") or [] if g.get("regra") == "gartner_lider"]
    for g in regras:
        linhas += ["", f"## Gate {g['id']} — {g.get('clausula') or 'Gartner'}", ""]
        vered = []
        for t in triagem:
            for v in ((gates.get("fornecedores") or {}).get(t["id"], {}).get("gates") or []):
                if v["gate"] == g["id"]:
                    vered.append([t["nome"], v["veredito"], v.get("justificativa"), "sim" if v.get("override") else "—"])
        linhas += _tabela(["Fornecedor", "Veredito", "Base", "Override"], vered)
    linhas += ["", "## Fontes por edição", ""]
    for e in eds:
        linhas.append(f"- **{e['ano']}** ({e.get('confianca') or '—'}): " + "; ".join(e.get("fontes") or ["—"]))
        if e.get("obs"):
            linhas.append(f"  - {e['obs']}")
    return linhas


def _registro_md(projeto, registro: list, checagens: dict) -> list:
    linhas = _cabecalho(projeto, "Registro de evidências do estudo")
    linhas += ["Alegações que sustentam decisões deste estudo (gates, direcionamento, respostas negativas, riscos). "
               "Fonte: `02-analise/registro-evidencias.yaml`.", ""]
    conf = Counter(util.norm(e.get("confianca") or "—") for e in registro)
    linhas += [f"{len(registro)} alegação(ões) · confiança: " + ", ".join(f"{k} {v}" for k, v in sorted(conf.items())), ""]
    linhas += _tabela(["ID", "Tema", "Alegação", "Confiança", "Impacto", "Fonte", "Acesso", "Checagem da URL"],
                      [[e.get("id"), e.get("tema"), e.get("alegacao"), e.get("confianca"), e.get("impacto"),
                        e.get("fonte"), e.get("data_acesso"),
                        (checagens.get(str(e.get("fonte") or "")) or {}).get("situacao")] for e in registro])
    for e in registro:
        if e.get("citacoes"):
            linhas += ["", f"### {e.get('id')} — citações", ""]
            linhas += [f"> {c}" + "\n" for c in e["citacoes"]]
    return linhas


def _biblioteca_md(projeto, kb: KB, checagens: dict) -> list:
    prop = projeto.cfg.get("proponente")
    linhas = _cabecalho(projeto, f"Evidências usadas nas respostas — {kb.nome(prop)}")
    usos = {}
    for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
        if r.get("resposta") and not r.get("_orfa"):
            for ev in r.get("evidencias") or []:
                usos.setdefault(str(ev), []).append(r["id"])
    ids = sorted(u for u in usos if kb.evidencia(u))
    diretas = sorted(u for u in usos if u.startswith("http"))
    linhas += [f"{len(ids)} evidência(s) da biblioteca e {len(diretas)} URL(s) direta(s) citadas em respostas.", ""]
    linhas += _tabela(["ID", "Capacidade", "Status", "Verificado em", "Checagem no estudo", "Usos", "Requisitos", "URL"],
                      [[i, kb.evidencia(i).get("capacidade"), kb.status_evidencia(kb.evidencia(i), projeto.data_ref),
                        kb.evidencia(i).get("verificado_em"), (checagens.get(kb.evidencia(i)["url"]) or {}).get("situacao"),
                        len(usos[i]), ", ".join(usos[i][:12]) + (" …" if len(usos[i]) > 12 else ""),
                        kb.evidencia(i)["url"]] for i in ids]
                      + [["—", "URL direta", "—", "—", (checagens.get(u) or {}).get("situacao"), len(usos[u]),
                          ", ".join(usos[u][:12]), u] for u in diretas])
    for i in ids:
        e = kb.evidencia(i)
        cit = e.get("citacoes") or ([e["citacao"]] if e.get("citacao") else [])
        if e.get("alegacao") or cit:
            linhas += ["", f"### {i} — {e.get('capacidade')}", ""]
            if e.get("alegacao"):
                linhas += [e["alegacao"], ""]
            linhas += [f"> {c}" + "\n" for c in cit]
    return linhas


def gerar(projeto, kb: KB | None = None) -> list:
    """Gera os dossiês em 00-projeto/evidencias/. Requer o ranking (gates.json/selecao.json/ranking.json)."""
    kb = kb or KB()
    pasta = projeto.dir_projeto / "evidencias"
    pasta.mkdir(parents=True, exist_ok=True)
    selecao = util.ler_json(projeto.dir_analise / "selecao.json")
    rk = util.ler_json(projeto.dir_analise / "ranking.json")
    gates = util.ler_json(projeto.dir_analise / "gates.json") or {}
    if not selecao or not rk:
        raise RuntimeError("ranking ainda não calculado — rode 'python kit.py ranking' antes.")
    triagem = selecao.get("triagem") or []
    por_fid = {l["fornecedor"]: l for l in rk.get("ranking") or []}
    categorias = rk.get("categorias") or []
    registro = carregar_registro(projeto, kb)
    checagens = _checagens_url(projeto)
    for antigo in pasta.glob("*.md"):
        if antigo.name.startswith(("dossie-", "biblioteca-")) or antigo.name in ("indice.md", "gartner-mq.md",
                                                                                   "registro-evidencias.md"):
            antigo.unlink()

    arquivos = []

    def gravar(nome, linhas, descricao):
        destino = pasta / nome
        destino.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")
        arquivos.append((nome, descricao))
        return destino

    saidas = [gravar("gartner-mq.md", _gartner(projeto, kb, triagem, gates),
                     "Posições no Gartner MQ por edição, gates baseados no Gartner e fontes")]
    for t in triagem:
        saidas.append(gravar(f"dossie-{t['id']}.md",
                             _dossie_fornecedor(projeto, kb, t["id"], t, por_fid.get(t["id"]), gates, categorias,
                                                registro),
                             f"{t['nome']}: gates, fatos, notas por categoria, evidências e cases"))
    if registro:
        saidas.append(gravar("registro-evidencias.md", _registro_md(projeto, registro, checagens),
                             f"{len(registro)} alegação(ões) do estudo com fonte, citação, confiança e impacto"))
    if projeto.cfg.get("modo") == "proponente" and projeto.cfg.get("proponente"):
        if (projeto.dir_analise / "respostas.json").exists():
            saidas.append(gravar(f"biblioteca-{projeto.cfg['proponente']}.md", _biblioteca_md(projeto, kb, checagens),
                                 "Evidências oficiais citadas nas respostas, com status, usos e citações"))

    fatos = Counter(kb.fato(t["id"], n, projeto.data_ref)["status"] for t in triagem for n in FATOS)
    indice = _cabecalho(projeto, f"Evidências do estudo — {projeto.cfg['cliente']['nome']}")
    indice += [f"Fornecedores na triagem: {len(triagem)} · fatos da KB: " +
               ", ".join(f"{k} {v}" for k, v in sorted(fatos.items())) +
               f" · alegações no registro: {len(registro)}", ""]
    indice += _tabela(["Arquivo", "Conteúdo"], [[f"[{n}]({n})", d] for n, d in arquivos])
    indice += ["", "Fatos AUSENTE/VENCIDO que decidem gate aparecem como INDEFINIDO em `02-analise/gates.json`: "
               "pesquise fonte oficial (vai para a KB) ou trate com o fabricante neste edital "
               "(`02-analise/gates-override.yaml`)."]
    saidas.insert(0, gravar("indice.md", indice, "este índice"))
    return saidas
