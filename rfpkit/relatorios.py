"""Entregáveis: matriz RTM (xlsx), comparativo (xlsx), relatório HTML e relatório executivo (md)."""
import datetime as dt
import re

import markdown as md_lib
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import __version__, util
from .config import TEMPLATES_DIR
from .kb import KB, NOME_QUADRANTE

AZUL = "1F4E78"
CAB_FILL = PatternFill("solid", fgColor=AZUL)
CAB_FONT = Font(color="FFFFFF", bold=True, size=10)
BORDA = Border(*(Side(style="thin", color="D9D9D9"),) * 4)
CORES_VEREDITO = {"PASSA": "C6EFCE", "RISCO": "FFF2CC", "INDEFINIDO": "FFF2CC", "NAO": "F8CBAD", "REPROVA": "F8CBAD"}
ROTULO_VEREDITO = {"PASSA": "PASSA", "RISCO": "RISCO", "INDEFINIDO": "INDEFINIDO", "NAO": "NÃO", "REPROVA": "REPROVA"}
SECOES_NARRATIVA = ("Recomendação", "Fatores estratégicos", "Próximos passos", "Ressalvas")
SECOES_OPCIONAIS = ("Ressalvas", "Arquitetura", "Cenários", "Revisão crítica")


def cor_nota(v):
    if v is None:
        return "EDEDED"
    v = float(v)
    return "C6EFCE" if v >= 0.9 else "E2EFDA" if v >= 0.7 else "FFF2CC" if v >= 0.5 else "FCE4D6" if v >= 0.25 else "F8CBAD"


def classe_nota(v):
    if v is None:
        return "sna"
    v = float(v)
    return "s10" if v >= 0.9 else "s075" if v >= 0.7 else "s05" if v >= 0.5 else "s025" if v >= 0.25 else "s0"


def classe_veredito(v):
    return {"PASSA": "b-ok", "RISCO": "b-warn", "INDEFINIDO": "b-warn", "NAO": "b-bad", "REPROVA": "b-bad"}.get(v, "b-warn")


def _cabecalho(ws, linha, ncol):
    for c in range(1, ncol + 1):
        cel = ws.cell(row=linha, column=c)
        cel.fill, cel.font, cel.border = CAB_FILL, CAB_FONT, BORDA
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _larguras(ws, larguras):
    for i, w in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _tabela(ws, linha_ini, cabecalho, linhas, larguras=None, quebra=()):
    for i, titulo in enumerate(cabecalho, start=1):
        ws.cell(row=linha_ini, column=i, value=titulo)
    _cabecalho(ws, linha_ini, len(cabecalho))
    for r, valores in enumerate(linhas, start=linha_ini + 1):
        for c, v in enumerate(valores, start=1):
            cel = ws.cell(row=r, column=c, value=v)
            cel.border = BORDA
            cel.alignment = Alignment(vertical="top", wrap_text=c in quebra)
    if larguras:
        _larguras(ws, larguras)
    return linha_ini + len(linhas)


def gerar_xlsx_rtm(projeto, rtm: dict, kb: KB):
    wb = Workbook()
    ws = wb.active
    ws.title = "RTM"
    cab = ["ID", "ID origem", "Fonte", "Localização", "Seção", "Bloco", "Categoria", "Natureza", "Obrigatoriedade",
           "Requisito (texto do edital)"]
    linhas = [[r["id"], r["id_origem"], r["fonte"], r["localizacao"], r["secao"], r["bloco"],
               kb.categoria(r["categoria"])["nome"] if r["categoria"] != "nao-classificado" else "NÃO CLASSIFICADO",
               r["natureza"], r["obrigatoriedade"], r["texto"]] for r in rtm["requisitos"]]
    fim = _tabela(ws, 1, cab, linhas, [12, 10, 18, 14, 22, 26, 28, 13, 15, 90], quebra=(6, 7, 10))
    for r in range(2, fim + 1):
        ob = ws.cell(row=r, column=9).value
        if ob == "eliminatorio":
            ws.cell(row=r, column=9).fill = PatternFill("solid", fgColor="F8CBAD")
        if ws.cell(row=r, column=7).value == "NÃO CLASSIFICADO":
            ws.cell(row=r, column=7).fill = PatternFill("solid", fgColor="FFF2CC")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:J{fim}"

    ws2 = wb.create_sheet("Resumo")
    ws2["A1"] = f"Resumo da matriz de requisitos — {projeto.cfg['cliente']['nome']}"
    ws2["A1"].font = Font(bold=True, size=13, color=AZUL)
    ws2["A2"] = f"Total de requisitos: {rtm['total']}"
    linha = 4
    rotulos = {"por_categoria": "Por categoria", "por_natureza": "Por natureza",
               "por_obrigatoriedade": "Por obrigatoriedade", "por_fonte": "Por documento"}
    for chave, titulo in rotulos.items():
        ws2.cell(row=linha, column=1, value=titulo).font = Font(bold=True, color=AZUL)
        itens = [[kb.categoria(k)["nome"] if chave == "por_categoria" else k, v]
                 for k, v in rtm["resumo"][chave].items()]
        linha = _tabela(ws2, linha + 1, ["Item", "Qtd"], itens) + 2
    _larguras(ws2, [60, 10])

    ws3 = wb.create_sheet("Pendências")
    pend = [r for r in rtm["requisitos"] if r["categoria"] == "nao-classificado" or r["confianca_classificacao"] < 0.4]
    _tabela(ws3, 1, ["ID", "Categoria sugerida", "Confiança", "Bloco", "Requisito"],
            [[r["id"], r["categoria"], r["confianca_classificacao"], r["bloco"], r["texto"]] for r in pend],
            [12, 22, 10, 30, 90], quebra=(4, 5))
    destino = projeto.entregavel("matriz-rtm", "xlsx")
    wb.save(destino)
    return destino


def gerar_xlsx_comparativo(projeto, kb: KB, ranking: dict, gates: dict, extras: dict | None = None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Scorecard"
    ws["A1"] = f"Scorecard — {projeto.cfg['cliente']['nome']}"
    ws["A1"].font = Font(bold=True, size=13, color=AZUL)
    eixos = ranking["eixos"]
    ws["A2"] = "Nota final = " + " + ".join(f"{util.br(p / 100, 2)}·{k}" for k, p in eixos.items()) + \
               " (escala 0–5; aderência convertida para 0–5)"
    cab = ["#", "Fornecedor", "Confiança", "Aderência %", "Aderência (0-5)", "Risco", "Esforço", "Custo",
           "Estratégico", "Nota final", "Gate", "Reprovados", "Em risco"]
    linhas = [[l["posicao"], l["nome"], l["confianca"], l["aderencia_pct"], l["aderencia_5"], l["risco"], l["esforco"],
               l["custo"], l["estrategico"], l["nota_final"], ROTULO_VEREDITO.get(l["status_gate"]),
               l["gates_reprovados"], l["gates_risco"]] for l in ranking["ranking"]]
    fim = _tabela(ws, 4, cab, linhas, [4, 26, 10, 11, 13, 8, 9, 8, 11, 10, 11, 14, 14])
    for r in range(5, fim + 1):
        v = ws.cell(row=r, column=11).value
        chave = next((k for k, rot in ROTULO_VEREDITO.items() if rot == v), None)
        if chave:
            ws.cell(row=r, column=11).fill = PatternFill("solid", fgColor=CORES_VEREDITO[chave])

    ws2 = wb.create_sheet("Aderência por categoria")
    forn = ranking["ranking"]
    cab = ["Categoria", "Peso"] + [l["nome"] for l in forn]
    linhas = [[c["nome"], c["peso"]] + [l["notas"].get(c["id"]) for l in forn] for c in ranking["categorias"]]
    linhas.append(["ADERÊNCIA PONDERADA (%)", round(sum(c["peso"] for c in ranking["categorias"]), 1)] +
                  [l["aderencia_pct"] for l in forn])
    fim = _tabela(ws2, 1, cab, linhas, [46, 7] + [14] * len(forn))
    for r in range(2, fim):
        for c in range(3, 3 + len(forn)):
            cel = ws2.cell(row=r, column=c)
            cel.fill = PatternFill("solid", fgColor=cor_nota(cel.value))
            cel.alignment = Alignment(horizontal="center")
    for c in range(1, len(cab) + 1):
        ws2.cell(row=fim, column=c).font = Font(bold=True)
    ws2.freeze_panes = "C2"

    ws3 = wb.create_sheet("Triagem e gates")
    gates_cfg = gates["gates"]
    cab = ["Fornecedor", "Origem", "Gartner (edição vigente)", "Aderência prévia %"] + \
          [f"{g['id']}{'' if g.get('eliminatorio', True) else ' (não elim.)'}" for g in gates_cfg] + \
          ["Resultado", "Avaliação completa"]
    edicao = kb.edicao_vigente(projeto.data_ref)
    linhas = []
    for t in ranking["triagem"]:
        vg = {l["gate"]: l["veredito"] for l in gates["fornecedores"][t["id"]]["gates"]}
        pos = NOME_QUADRANTE[kb.posicao(edicao, t["id"])] if edicao else "—"
        linhas.append([t["nome"], t["origem"], pos, t["aderencia_previa_pct"]] +
                      [ROTULO_VEREDITO.get(vg.get(g["id"]), "") for g in gates_cfg] +
                      [ROTULO_VEREDITO.get(t["status_gate"]), "Sim" if t["avaliacao_completa"] else "Não"])
    fim = _tabela(ws3, 1, cab, linhas, [26, 18, 16, 12] + [11] * len(gates_cfg) + [12, 12])
    for r in range(2, fim + 1):
        for c in range(5, 6 + len(gates_cfg)):
            v = ws3.cell(row=r, column=c).value
            chave = next((k for k, rot in ROTULO_VEREDITO.items() if rot == v), None)
            if chave:
                ws3.cell(row=r, column=c).fill = PatternFill("solid", fgColor=CORES_VEREDITO[chave])
    linha = fim + 2
    ws3.cell(row=linha, column=1, value="Gates do edital").font = Font(bold=True, color=AZUL)
    _tabela(ws3, linha + 1, ["Gate", "Regra", "Eliminatório", "Cláusula"],
            [[g["id"], g["regra"], "Sim" if g.get("eliminatorio", True) else "Não", g.get("clausula", "")]
             for g in gates_cfg], quebra=(4,))

    ws4 = wb.create_sheet("Fatos e fontes")
    linhas = []
    for fid, dados in gates["fornecedores"].items():
        for l in dados["gates"]:
            for f in l["fatos"]:
                linhas.append([dados["nome"], l["gate"], f["fato"], str(f["valor"]), f["status"], f["fonte"],
                               str(f["verificado_em"] or ""), l["justificativa"]])
    _tabela(ws4, 1, ["Fornecedor", "Gate", "Fato", "Valor", "Status", "Fonte", "Verificado em", "Justificativa"],
            linhas, [22, 7, 26, 22, 11, 60, 13, 70], quebra=(6, 8))

    ws5 = wb.create_sheet("Gartner MQ")
    eds = kb.edicoes(projeto.data_ref)
    cab = ["Fornecedor"] + [str(e["ano"]) for e in eds]
    linhas = [[t["nome"]] + [NOME_QUADRANTE[kb.posicao(e, t["id"])] for e in eds] for t in ranking["triagem"]]
    _tabela(ws5, 1, cab, linhas, [26] + [13] * len(eds))
    _abas_decisao(wb, kb, ranking, extras or {})
    _abas_confianca(wb, kb, util.ler_json(projeto.dir_analise / "confianca.json") or {})
    destino = projeto.entregavel("comparativo", "xlsx")
    wb.save(destino)
    return destino


def _abas_confianca(wb, kb: KB, dados: dict):
    """Confiança por fornecedor e de cada avaliação requisito × fornecedor (quando houver)."""
    if not dados.get("avaliacoes"):
        return
    ws = wb.create_sheet("Confiança")
    _tabela(ws, 1, ["Fornecedor", "Avaliações", "Alta", "Média", "Baixa", "% alta", "Eliminatórios com alta",
                    "Eliminatórios", "Com pendência"],
            [[kb.nome(f), c["total"], c["alta"], c["media"], c["baixa"], c.get("pct_alta"), c["elim_alta"],
              c["elim_total"], c["pendencias"]] for f, c in (dados.get("resumo") or {}).items()],
            [28, 11, 8, 8, 8, 9, 12, 12, 13])
    ws2 = wb.create_sheet("Avaliações")
    _tabela(ws2, 1, ["Requisito", "Fornecedor", "Obrigatoriedade", "Atendimento", "Confiança", "Motivos",
                     "Dúvida", "Fabricante/POC", "Pendências"],
            [[s["id"], kb.nome(s["fornecedor"]), s.get("obrigatoriedade"), s.get("atendimento"), s["nivel"],
              "; ".join(m["texto"] for m in s.get("motivos") or []), s.get("duvida") or "",
              "sim" if s.get("fabricante_ou_poc") else "", "; ".join(s.get("pendencias") or [])]
             for s in dados["avaliacoes"]], [12, 24, 14, 12, 10, 70, 10, 12, 50], quebra=(6, 9))
    for row in range(2, ws2.max_row + 1):
        cel = ws2.cell(row=row, column=5)
        cel.fill = PatternFill("solid", fgColor={"alta": "C6EFCE", "media": "FFF2CC", "baixa": "F8CBAD"}.get(cel.value, "FFFFFF"))
    ws2.freeze_panes = "C2"


def _abas_decisao(wb, kb: KB, ranking: dict, extras: dict):
    """Sensibilidade, cenários de gate, esforço de POC e custo (quando existirem)."""
    nomes = {l["fornecedor"]: l["nome"] for l in ranking.get("ranking") or []}
    nome = lambda f: nomes.get(f) or kb.nome(f)  # noqa: E731
    sens = ranking.get("sensibilidade")
    if sens:
        ws = wb.create_sheet("Sensibilidade")
        ids = [l["fornecedor"] for l in ranking["ranking"] if l.get("nota_final") is not None]
        fim = _tabela(ws, 1, ["Cenário de pesos", "Pesos (%)", "1º", "1º elegível"] + [nome(f) for f in ids],
                      [[c["cenario"], " · ".join(f"{k} {util.br(v, 0)}" for k, v in c["pesos"].items()),
                        nome(c["ordem"][0]), nome(c["primeiro_elegivel"]) if c.get("primeiro_elegivel") else "—"] +
                       [c["notas"].get(f) for f in ids] for c in sens["cenarios"]],
                      [34, 52, 22, 22] + [13] * len(ids), quebra=(2,))
        ws.cell(row=fim + 2, column=1, value=f"1º robusto: {nome(sens['robusto'])} — 1º em "
                                             f"{sens['vitorias'][sens['robusto']]} de {len(sens['cenarios'])} cenários"
                                             + (f"; entre os elegíveis: {nome(sens['robusto_elegivel'])}"
                                                if sens.get("robusto_elegivel") else "")).font = Font(bold=True)
    cen = ranking.get("cenarios_gate") or []
    if len(cen) > 1:
        ws = wb.create_sheet("Cenários de gate")
        _tabela(ws, 1, ["Cenário", "Melhor elegível", "Elegíveis", "Passam a elegíveis", "Reprovados pelo gate"],
                [[c["cenario"], nome(c["melhor"]) if c.get("melhor") else "nenhum",
                  ", ".join(nome(f) for f in c.get("elegiveis") or []) or "—",
                  ", ".join(nome(f) for f in c.get("passam_a_elegiveis") or []) or "—",
                  ", ".join(nome(f) for f in c.get("reprovados_pelo_gate") or []) or "—"] for c in cen],
                [40, 24, 50, 30, 30], quebra=(3, 4, 5))
    esf = extras.get("esforco")
    if esf:
        from .esforco_custo import faixa_texto
        ws = wb.create_sheet("Esforço PoC")
        ids = [f for f, _ in sorted(esf["fornecedores"].items(), key=lambda kv: kv[1]["medio"])]
        fim = _tabela(ws, 1, ["Fornecedor", "Mín (dias)", "Máx (dias)", "Médio", "% em portões", "Risco", "Motivo"],
                      [[nome(f), esf["fornecedores"][f]["min"], esf["fornecedores"][f]["max"],
                        esf["fornecedores"][f]["medio"], esf["fornecedores"][f].get("pct_portoes"),
                        esf["fornecedores"][f].get("risco"), esf["fornecedores"][f].get("motivo_risco")] for f in ids],
                      [26, 11, 11, 9, 12, 10, 60], quebra=(7,))
        _tabela(ws, fim + 3, ["Frente", "Portão"] + [nome(f) for f in ids] + ["Observação"],
                [[f"{fr.get('id') or ''} {fr['nome']}".strip(), "sim" if fr["portao"] else ""] +
                 [faixa_texto(*fr["dias"][f], 0) if f in fr["dias"] else "—" for f in ids] + [fr.get("obs") or ""]
                 for fr in esf["frentes"]], quebra=(1, 3 + len(ids)))
    cus = extras.get("custo")
    if cus:
        ws = wb.create_sheet("Custo")
        ws["A1"] = (f"Estimativa indicativa (list price, {cus['moeda']}) — cenário: {cus['cenario'].get('descricao') or '—'}"
                    + (" — ILUSTRATIVO" if cus["ilustrativo"] else ""))
        ws["A1"].font = Font(bold=True, color=AZUL)
        forn = sorted(cus["fornecedores"].items(), key=lambda kv: kv[1]["mensal_min"])
        fim = _tabela(ws, 3, ["Fornecedor", "Mensal mín", "Mensal máx", "Anual mín", "Anual máx", "Modelo de cobrança",
                              "Ressalva"],
                      [[nome(f), t["mensal_min"], t["mensal_max"], t["anual_min"], t["anual_max"],
                        t.get("modelo_cobranca"), t.get("ressalva")] for f, t in forn],
                      [26, 12, 12, 13, 13, 24, 60], quebra=(7,))
        _tabela(ws, fim + 3, ["Fornecedor", "Componente", "Quantidade", "Unidade", "Preço unitário", "Valor mín/mês",
                              "Valor máx/mês", "Fonte", "Verificado em"],
                [[nome(f), c.get("item"), str(c.get("quantidade") if c.get("quantidade") is not None else ""),
                  c.get("unidade"), str(c.get("preco_unitario") if c.get("preco_unitario") is not None else ""),
                  c["valor_min"], c["valor_max"], c.get("fonte"), str(c.get("verificado_em") or "")]
                 for f, t in forn for c in t["componentes"]], quebra=(2, 8))


def _formatar_params(params) -> str:
    return ", ".join(f"{k}={'/'.join(map(str, v)) if isinstance(v, list) else v}"
                     for k, v in (params or {}).items() if not str(k).startswith("_")) or "—"


def _ambiente(autoescape: bool) -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)),
                      autoescape=select_autoescape(["html", "j2"]) if autoescape else False,
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["br"] = util.br
    env.filters["params"] = _formatar_params
    env.globals.update(classe_nota=classe_nota, classe_veredito=classe_veredito, ROTULO=ROTULO_VEREDITO,
                       NOME_QUADRANTE=NOME_QUADRANTE)
    return env


def _undefined_tolerante():
    from jinja2 import ChainableUndefined

    class Tolerante(ChainableUndefined):
        def __str__(self):
            return "⟨?⟩"

    return Tolerante


def ler_narrativa(projeto, contexto: dict) -> dict:
    """Renderiza 02-analise/narrativa.md (placeholders Jinja2) e separa por seção '## Título'."""
    caminho = projeto.dir_analise / "narrativa.md"
    if not caminho.exists():
        return {}
    bruto = caminho.read_text(encoding="utf-8")
    try:
        env = Environment(undefined=StrictUndefined)
        env.filters["br"] = util.br
        texto = env.from_string(bruto).render(**contexto)
    except Exception as e:  # placeholder inválido não pode derrubar o relatório
        contexto.setdefault("_erros_narrativa", []).append(f"narrativa.md: placeholder inválido ({e}) — exibido como ⟨?⟩")
        env = Environment(undefined=_undefined_tolerante())
        env.filters["br"] = lambda v, casas=1: util.br(v, casas) if isinstance(v, (int, float)) else "⟨?⟩"
        texto = env.from_string(bruto).render(**contexto)
    secoes, atual = {}, None
    for linha in texto.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", linha)
        if m:
            atual = m.group(1)
            secoes[atual] = []
        elif atual:
            secoes[atual].append(linha)
    saida = {}
    for titulo, linhas in secoes.items():
        corpo = re.sub(r"<!--.*?-->", "", "\n".join(linhas), flags=re.S).strip()
        saida[titulo] = corpo
    return saida


def _panorama(ctx: dict) -> list:
    """Indicadores de topo do relatório (cartões): maior aderência, faixa de esforço e custo, gate."""
    cards, lentes, ranking = [], ctx["lentes"], ctx["ranking"]
    if lentes.get("lider_aderencia"):
        cards.append((f"{util.br(lentes['aderencia_pct'])}%", f"maior aderência ({ctx['nome_de'](lentes['lider_aderencia'])})"))
    esf = ctx.get("esforco")
    if esf and esf["fornecedores"]:
        mins = [t["min"] for t in esf["fornecedores"].values()]
        maxs = [t["max"] for t in esf["fornecedores"].values()]
        cards.append((f"{util.br(min(mins), 0)}–{util.br(max(maxs), 0)}", f"dias de POC ({esf['unidade']})"))
    cus = ctx.get("custo")
    if cus and cus["fornecedores"]:
        vals = [t["mensal_min"] for t in cus["fornecedores"].values()] + [t["mensal_max"] for t in cus["fornecedores"].values()]
        cards.append((ctx["dinheiro"](min(vals), max(vals), cus["moeda"]),
                      "custo/mês de produção (list price)" + (" — ilustrativo" if cus["ilustrativo"] else "")))
    cob = ctx.get("cobertura")
    if cob and cob.get("respondidos"):
        cards.append((str(len(cob["eliminatorios_em_risco"])), "eliminatórios com resposta parcial ou negativa"))
    else:
        reprovados = [t for t in ranking.get("triagem") or [] if t.get("status_gate") == "REPROVA"]
        cards.append((f"{len(ranking.get('triagem') or []) - len(reprovados)}/{len(ranking.get('triagem') or [])}",
                      "fornecedores sem gate eliminatório reprovado"))
    return cards


def contexto_relatorio(projeto, kb: KB, rtm: dict, pesos: dict, ranking: dict, gates: dict, pendencias: list) -> dict:
    cfg = projeto.cfg
    r_por_id = {l["fornecedor"]: l for l in ranking["ranking"]}
    t_por_id = {t["id"]: t for t in ranking["triagem"]}
    edicao = kb.edicao_vigente(projeto.data_ref)
    fatos = []
    for fid, dados in gates["fornecedores"].items():
        for l in dados["gates"]:
            for f in l["fatos"]:
                if f.get("fonte"):
                    fatos.append({"fornecedor": dados["nome"], "gate": l["gate"], **f})
    ctx = {
        "kit_versao": __version__, "gerado_em": dt.date.today(), "cfg": cfg, "cliente": cfg["cliente"],
        "modo": cfg["modo"], "proponente": cfg.get("proponente"),
        "proponente_nome": kb.nome(cfg["proponente"]) if cfg.get("proponente") else None,
        "data_referencia": projeto.data_ref, "edicao": edicao, "rtm": rtm, "pesos": pesos, "ranking": ranking,
        "r": r_por_id, "t": t_por_id, "gates": gates, "gates_cfg": gates["gates"], "fatos": fatos,
        "melhor_merito": r_por_id.get(ranking.get("melhor_merito")),
        "melhor_elegivel": r_por_id.get(ranking.get("melhor_elegivel")),
        "posicao_gartner": lambda fid: NOME_QUADRANTE[kb.posicao(edicao, fid)] if edicao else "—",
        "pendencias": pendencias if cfg["relatorio"].get("incluir_pendencias", True) else [],
        "confidencial": cfg["relatorio"].get("confidencial", True),
        "cobertura": None,
    }
    if cfg["modo"] == "proponente" and (projeto.dir_analise / "respostas.json").exists():
        from .respostas import cobertura
        ctx["cobertura"] = cobertura(projeto)
    from . import esforco_custo as ec
    from .analises import battlecards
    ctx["esforco"], ctx["custo"] = ec.resumo_esforco(projeto), ec.resumo_custo(projeto)
    ctx["cruzamento"] = ec.cruzamento(ranking, ctx["esforco"], ctx["custo"])
    ctx["battlecards"] = battlecards(projeto, kb, ranking)
    ctx["sens"] = ranking.get("sensibilidade")
    ctx["lentes"] = ranking.get("lentes") or {}
    ctx["nome_de"] = lambda fid: (r_por_id.get(fid) or {}).get("nome") or kb.nome(fid)
    ctx["cenarios_gate"] = [{**c, "passam_nomes": [ctx["nome_de"](f) for f in c.get("passam_a_elegiveis") or []],
                             "reprovados_nomes": [ctx["nome_de"](f) for f in c.get("reprovados_pelo_gate") or []]}
                            for c in ranking.get("cenarios_gate") or []]
    ctx["dinheiro"], ctx["faixa"] = ec.dinheiro, ec.faixa_texto
    ctx["panorama"] = _panorama(ctx)
    ctx["execucao"] = util.ler_json(projeto.dir_analise / "execucao.json")
    if not ctx["execucao"]:
        from .execucao import estado
        ctx["execucao"] = estado(projeto, kb)
    from . import confianca as conf_mod, independente
    ctx["confianca"] = util.ler_json(projeto.dir_analise / "confianca.json") or conf_mod.calcular(projeto, kb)
    ctx["independente"] = independente.resumo(projeto)
    ctx["confianca_linhas"] = [
        {"fornecedor": fid, "nome": ctx["nome_de"](fid), **c}
        for fid, c in sorted((ctx["confianca"].get("resumo") or {}).items(),
                             key=lambda kv: (kv[0] != cfg.get("proponente"), -(kv[1].get("pct_alta") or 0)))]
    alvo = cfg.get("proponente") if cfg["modo"] == "proponente" else ranking.get("melhor_elegivel")
    c_alvo = (ctx["confianca"].get("resumo") or {}).get(alvo)
    if c_alvo and c_alvo.get("pct_alta") is not None:
        ctx["panorama"].append((f"{util.br(c_alvo['pct_alta'], 0)}%",
                                f"das avaliações de {ctx['nome_de'](alvo)} com confiança alta"
                                + (f" ({c_alvo['elim_alta']}/{c_alvo['elim_total']} eliminatórios)" if c_alvo["elim_total"] else "")))
    narrativa = ler_narrativa(projeto, ctx)
    ctx["narrativa_md"] = narrativa
    ctx["narrativa"] = {k: md_lib.markdown(v, extensions=["tables"]) for k, v in narrativa.items() if v}
    ctx["narrativa_pendente"] = [s for s in SECOES_NARRATIVA if s not in SECOES_OPCIONAIS and not narrativa.get(s)]
    return ctx


def carregar_contexto(projeto, kb: KB | None = None, pendencias: list | None = None) -> dict:
    kb = kb or KB()
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json")
    pesos = util.ler_json(projeto.dir_projeto / "categorias-pesos.json")
    ranking = util.ler_json(projeto.dir_analise / "ranking.json")
    gates = util.ler_json(projeto.dir_analise / "gates.json")
    if not all([rtm, pesos, ranking, gates]):
        raise RuntimeError("Artefatos ausentes — rode 'python kit.py tudo' (ou rtm, pesos, ranking) antes.")
    return contexto_relatorio(projeto, kb, rtm, pesos, ranking, gates, pendencias or [])


def gerar(projeto, kb: KB | None = None, pendencias: list | None = None) -> list:
    kb = kb or KB()
    ctx = carregar_contexto(projeto, kb, pendencias)
    projeto.criar_pastas()
    saidas = [gerar_xlsx_rtm(projeto, ctx["rtm"], kb),
              gerar_xlsx_comparativo(projeto, kb, ctx["ranking"], ctx["gates"],
                                     {"esforco": ctx["esforco"], "custo": ctx["custo"]})]
    html = _ambiente(True).get_template("relatorio.html.j2").render(**ctx)
    destino = projeto.entregavel("relatorio", "html")
    destino.write_text(html, encoding="utf-8")
    saidas.append(destino)
    md = _ambiente(False).get_template("relatorio-executivo.md.j2").render(**ctx)
    destino = projeto.entregavel("relatorio-executivo", "md")
    destino.write_text(md, encoding="utf-8")
    saidas.append(destino)
    saidas.append(_executivo_html(projeto, ctx, md))
    from . import documentos
    saidas += documentos.gerar(projeto, kb, ctx, pdf=bool(projeto.cfg["relatorio"].get("pdf", False)))
    from . import entregas
    saidas.append(entregas.gerar(projeto, ctx, pendencias or []))
    for erro in ctx.get("_erros_narrativa", []):
        print(f"AVISO: {erro}")
    return saidas


def _executivo_html(projeto, ctx: dict, md: str):
    """Versão executiva navegável (a partir do markdown executivo)."""
    linhas = md.splitlines()
    titulo = linhas[0].lstrip("# ").strip() if linhas else "Relatório executivo"
    subtitulo = next((l.strip("_ ") for l in linhas[1:4] if l.startswith("_")), "")
    corpo = md_lib.markdown("\n".join(l for l in linhas[1:] if not (l.startswith("_Referência:"))),
                            extensions=["tables"])
    html = _ambiente(True).get_template("relatorio-executivo.html.j2").render(
        titulo=titulo, subtitulo=subtitulo, corpo=corpo, kit_versao=__version__, gerado_em=ctx["gerado_em"],
        completo=projeto.entregavel("relatorio", "html").name, confidencial=ctx["confidencial"])
    destino = projeto.entregavel("relatorio-executivo", "html")
    destino.write_text(html, encoding="utf-8")
    return destino


def gerar_premissas(projeto, kb: KB | None = None, ranking: dict | None = None):
    kb = kb or KB()
    ranking = ranking or util.ler_json(projeto.dir_analise / "ranking.json") or {}
    env = _ambiente(False)
    ctx = {"cfg": projeto.cfg, "cliente": projeto.cfg["cliente"], "data_referencia": projeto.data_ref,
           "edicao": kb.edicao_vigente(projeto.data_ref), "ranking": ranking, "kb": kb,
           "proponente_nome": kb.nome(projeto.cfg["proponente"]) if projeto.cfg.get("proponente") else None}
    texto = env.get_template("premissas.md.j2").render(**ctx)
    destino = projeto.dir_projeto / "premissas.md"
    destino.write_text(texto, encoding="utf-8")
    return destino
