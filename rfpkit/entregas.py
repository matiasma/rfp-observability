"""Índice das entregas (03-entregas/README-ENTREGAS.md): o que vai para o cliente, o que é fonte de verdade, o que é
análise interna, o resultado em números, a rastreabilidade das evidências, as pendências e os próximos passos."""
import re

from . import __version__, util

INTERNOS = (
    ("confianca.md", "Confiança de cada avaliação requisito × fornecedor, pendências de encaminhamento, inconsistências e mudanças"),
    ("eliminatorios.md", "Gates de qualificação (quem elimina quem, leitura estrita × flexibilizada) e requisitos eliminatórios"),
    ("ranking.md", "Ranking de mérito: matriz de aderência, scorecard, duas lentes, sensibilidade, cenários e battlecards"),
    ("esforco-custo.md", "Esforço de POC por frente e estimativa de custo (list price), com o cruzamento"),
    ("duvidas-interna.md", "Versão estratégica das dúvidas (por que perguntamos, resposta desejada, impacto, retiradas)"),
    ("cases-referencia-maturidade.md", "Cases pontuados pela rubrica de maturidade e verificação das URLs"),
    ("armadilhas-duvidas.md", "Cláusulas capciosas, ambíguas ou direcionadas e mapa das dúvidas"),
    ("direcionamento.md", "Sinais de direcionamento e inteligência competitiva"),
    ("red-team.md", "Auditoria de confiança, ataques à conclusão e riscos"),
    ("plano-poc.md", "Plano da POC/POV"),
    ("roteiro-defesa-parciais.md", "Roteiro de defesa das respostas parciais/negativas"),
    ("pente-fino-evidencias.md", "Pente-fino humano das evidências"),
    ("pente-fino-automatico.md", "Sinais automáticos por resposta (sem evidência, URL genérica, reuso, justificativa curta…)"),
    ("cobertura-respostas.md", "Cobertura das respostas por escala e eliminatórios em risco"),
    ("verificacao-planilhas.md", "Conferência da planilha RESPONDIDA/PREENCHIDO contra o original"),
    ("validacao-urls.md", "Checagem HTTP + palavras-chave das URLs citadas"),
    ("validacao.md", "Verificações de qualidade do estudo (ERRO/AVISO)"),
)


def _descricao(nome: str, sigla: str, modo: str) -> tuple[str, bool]:
    """(descrição, vai para o cliente?)"""
    n = nome.lower()
    proponente = modo == "proponente"
    if " - respondida " in n:
        return "Planilha oficial do edital respondida (resposta + observação com justificativa, método e referências); original intacto", True
    if n.startswith("memorial-tecnico"):
        return "Memorial técnico: metodologia, resumo quantitativo, arquitetura, respostas por requisito, maturidade (cases) e anexo de evidências", True
    if n.startswith("sumario-executivo"):
        return "Sumário executivo para decisores", True
    if " - preenchido" in n:
        return "Modelo de envio de dúvidas do edital preenchido", True
    if n.startswith("duvidas-"):
        return "Dúvidas enviáveis em formato genérico (conferência)", not proponente
    if n.startswith("relatorio-executivo") and n.endswith(".html"):
        return "Relatório executivo navegável" + (" (inteligência competitiva — interno)" if proponente else ""), not proponente
    if n.startswith("relatorio-executivo"):
        return "Relatório executivo em markdown" + (" (interno)" if proponente else ""), not proponente
    if n.startswith("relatorio-"):
        return ("Relatório completo navegável: recomendação, gates, cenários, scorecard, sensibilidade, aderência, "
                "esforço/custo, fatores e metodologia" + (" (interno)" if proponente else "")), not proponente
    if n.startswith("comparativo-"):
        return "Comparativo: scorecard, aderência, gates, fatos e fontes, Gartner, sensibilidade, cenários, esforço e custo", not proponente
    if n.startswith("matriz-rtm-"):
        return "Matriz de requisitos classificada (RTM) + resumo + pendências de classificação", not proponente
    if n.startswith("matriz-respostas-"):
        return "Respostas, cobertura, evidências e pente-fino (conferência interna)", False
    return "", False


def gerar(projeto, ctx: dict, pendencias: list) -> "Path":
    cfg, ranking = projeto.cfg, ctx["ranking"]
    proponente = cfg["modo"] == "proponente"
    nome_de = ctx["nome_de"]
    titulo = (f"Resposta técnica — {ctx['proponente_nome']}" if proponente else "Estudo de seleção de observabilidade")
    L = [f"# Entregas — {titulo} · {cfg['cliente']['nome']}", "",
         f"_{'Modo proponente' if proponente else 'Estudo vendor-neutro'} · referência {projeto.data_ref.isoformat()} · "
         f"gerado pelo kit v{__version__} em {ctx['gerado_em']}. Premissas: "
         "[`../00-projeto/premissas.md`](../00-projeto/premissas.md) — prevalecem em caso de conflito. "
         "**Índice interno — este arquivo não vai para o cliente.**_", ""]
    ex = ctx.get("execucao") or {}
    if ex.get("assistida"):
        L += [("> ✅ **Execução assistida completa** (VS Code + LLM): KB dos fornecedores do campo e Gartner revisados, "
               f"{(ex.get('revisao') or {}).get('revisados')} requisito(s) revisados por LLM, URLs verificadas em "
               f"{(ex.get('urls') or {}).get('verificadas_em') or '—'}.") if ex.get("completa") else
              "> ⚠️ **PRELIMINAR — execução assistida incompleta:** " + "; ".join(ex.get("pendencias") or []) + ".", ""]
    elif ex:
        L += ["> Execução não assistida (exemplo/diagnóstico): sem atualização da KB nem revisão dos requisitos por LLM.", ""]
    rec = (ctx.get("narrativa_md") or {}).get("Recomendação") or ""
    primeiro = re.split(r"\n\s*\n", rec.strip())[0] if rec.strip() else ""
    if primeiro:
        L += ["> **Conclusão:** " + " ".join(primeiro.split()), ""]
    elif ctx.get("melhor_elegivel"):
        L += [f"> **Pelo cálculo:** melhor elegível no gate — **{ctx['melhor_elegivel']['nome']}** "
              f"(aderência {util.br(ctx['melhor_elegivel']['aderencia_pct'])}%). Narrativa pendente.", ""]

    arquivos = sorted(p for p in projeto.dir_entregas.iterdir() if p.is_file() and p.name != "README-ENTREGAS.md"
                      and not p.name.startswith("~$"))
    rtm_arq = projeto.dir_projeto / "rtm.json"
    limite = rtm_arq.stat().st_mtime - 2 if rtm_arq.exists() else None
    cliente, apoio, antigos = [], [], []
    for p in arquivos:
        if limite is not None and p.stat().st_mtime < limite:   # sobra de execução anterior à RTM atual
            antigos.append(f"`{p.name}`")
            continue
        desc, externo = _descricao(p.name, projeto.sigla, cfg["modo"])
        (cliente if externo else apoio).append([f"`{p.name}`", desc])
    L += [f"## 1. Peças para {'submissão ao cliente' if proponente else 'decisão (cliente)'}", "",
          "| Arquivo | Descrição |", "|---|---|"] + [f"| {a} | {d} |" for a, d in cliente]
    if apoio:
        L += ["", "## 2. Peças de apoio — uso interno", "", "| Arquivo | Descrição |", "|---|---|"]
        L += [f"| {a} | {d} |" for a, d in apoio]
    if antigos:
        L += ["", "> ⚠️ **Arquivos de execuções anteriores** (mais antigos que a RTM atual — não enviar; remova ou "
                  "regenere): " + ", ".join(antigos)]

    rtm = ctx["rtm"]
    fontes = [("../00-projeto/rtm.json` / `rtm.csv", f"RTM estruturada — {rtm.get('total')} requisitos"),
              ("../00-projeto/categorias-pesos.json", "Categorias e pesos do edital"),
              ("../02-analise/gates.json", "Vereditos dos gates com os fatos usados"),
              ("../02-analise/ranking.json` / `ranking.csv", "Triagem, notas, scorecard, sensibilidade e cenários"),
              ("../00-projeto/evidencias/", "Dossiês de evidências (retrato da KB na data de referência)")]
    if proponente and (projeto.dir_analise / "respostas.json").exists():
        fontes.append(("../02-analise/respostas.json", "Respostas item a item (resposta, justificativa, evidências, método, POC)"))
    registro = util.ler_yaml(projeto.dir_analise / "registro-evidencias.yaml", []) or []
    if isinstance(registro, list) and registro:
        fontes.append(("../02-analise/registro-evidencias.yaml", f"{len(registro)} alegação(ões) com fonte, citação e impacto"))
    L += ["", "## 3. Fontes de verdade (dados estruturados)", "", "| Arquivo | Conteúdo |", "|---|---|"]
    L += [f"| `{a}` | {d} |" for a, d in fontes]

    internos = [(n, d) for n, d in INTERNOS if (projeto.dir_analise / n).exists()]
    if internos:
        L += ["", "## 4. Análises internas (`../02-analise/`) — NÃO enviar ao cliente", "", "| Arquivo | Conteúdo |",
              "|---|---|"] + [f"| [`{n}`](../02-analise/{n}) | {d} |" for n, d in internos]

    L += ["", "## 5. Resultado", "",
          f"- **{rtm.get('total')} requisitos** extraídos; {(rtm.get('resumo') or {}).get('relevantes_para_pesos', '—')} "
          f"entram nos pesos."]
    forn = ranking.get("ranking") or []
    if forn:
        L.append("- **Aderência ponderada:** " + " · ".join(f"{l['nome']} {util.br(l.get('aderencia_pct'))}%" for l in forn) + ".")
        L.append("- **Nota final (0–5):** " + " · ".join(f"{l['nome']} {util.br(l.get('nota_final'), 2)}" for l in forn) + ".")
    reprov = [t["nome"] for t in ranking.get("triagem") or [] if t.get("status_gate") == "REPROVA"]
    eleg = [t["nome"] for t in ranking.get("triagem") or [] if t.get("status_gate") != "REPROVA"]
    L.append(f"- **Gate estrito:** elegíveis — {', '.join(eleg) or 'nenhum'}; reprovados — {', '.join(reprov) or 'nenhum'}.")
    if ctx.get("sens"):
        L.append(f"- **1º robusto (sensibilidade):** {nome_de(ctx['sens']['robusto'])}"
                 + (f"; entre os elegíveis: {nome_de(ctx['sens']['robusto_elegivel'])}" if ctx["sens"].get("robusto_elegivel") else "") + ".")
    cob = ctx.get("cobertura")
    if cob and cob.get("respondidos"):
        L.append(f"- **Respostas:** {cob['respondidos']} de {cob['total']} requisitos; por resposta: "
                 + ", ".join(f"{k} {v}" for k, v in cob["por_resposta"].items())
                 + f"; eliminatórios com resposta parcial/negativa: {len(cob['eliminatorios_em_risco'])}.")
    if ctx.get("confianca_linhas"):
        L.append("- **Confiança (regras do kit):** " + " · ".join(
            f"{c['nome']} {util.br(c['pct_alta'])}% alta ({c['elim_alta']}/{c['elim_total']} eliminatórios)"
            for c in ctx["confianca_linhas"]) + ".")
        ind = ctx.get("independente") or {}
        if ind.get("amostra"):
            L.append(f"- **Verificação independente:** {ind['verificados']}/{ind['amostra']} da amostra, concordância "
                     f"{util.br(ind['concordancia_pct'])}%, {ind['divergencias_abertas']} divergência(s) sem decisão.")
    if ctx.get("cruzamento"):
        L.append("- **Esforço de POC × custo:** " + " · ".join(f"{c['nome']} {c['esforco']} dias / {c['custo_mensal']} por mês"
                                                          for c in ctx["cruzamento"]) + ".")

    urls = util.ler_csv(projeto.dir_analise / "validacao-urls.csv")
    L += ["", "## 6. Rastreabilidade de evidências", ""]
    if urls:
        ok = sum(1 for u in urls if (u.get("situacao") or "") == "OK")
        L.append(f"- {len(urls)} URL(s) citadas verificadas por HTTP em {urls[0].get('verificado_em')}: {ok} OK, "
                 f"{len(urls) - ok} a conferir — [`validacao-urls.md`](../02-analise/validacao-urls.md).")
    else:
        L.append("- URLs ainda não verificadas neste estudo — rode `python kit.py validar-urls` (ou `tudo --urls`).")
    L.append("- Fatos, notas e evidências por fornecedor: [`../00-projeto/evidencias/indice.md`](../00-projeto/evidencias/indice.md).")

    erros = [p for p in pendencias if p.get("nivel") == "ERRO"]
    avisos = [p for p in pendencias if p.get("nivel") != "ERRO"]
    L += ["", "## 7. Pendências", "",
          f"- Validação: **{len(erros)} erro(s)**, {len(avisos)} aviso(s) — [`validacao.md`](../02-analise/validacao.md)."]
    L += [f"  - {p['nivel']} [{p['codigo']}] {p['mensagem']}" for p in (erros + avisos)[:8]]
    from .duvidas import carregar, enviavel
    duv = [d for d in carregar(projeto) if enviavel(d)]
    if duv:
        L.append(f"- Dúvidas a enviar: {len(duv)} — status: " + ", ".join(
            f"{s} {sum(1 for d in duv if (d.get('status') or 'PENDENTE') == s)}"
            for s in sorted({d.get('status') or 'PENDENTE' for d in duv})) + ".")
    prox = (ctx.get("narrativa_md") or {}).get("Próximos passos")
    if prox:
        L += ["", "## 8. Próximos passos", "", prox.strip()]
    destino = projeto.dir_entregas / "README-ENTREGAS.md"
    destino.write_text("\n".join(L).rstrip() + "\n", encoding="utf-8")
    return destino
