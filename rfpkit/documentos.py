"""Documentos Word para submissão: sumário executivo (ambos os modos) e memorial técnico (modo proponente),
com conversão opcional para PDF (Word via COM no Windows ou LibreOffice)."""
import datetime as dt
import re
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import respostas as resp_mod
from . import util
from .kb import KB

AZUL = RGBColor(0x1F, 0x4E, 0x78)
CINZA = RGBColor(0x5B, 0x6B, 0x7F)
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))")


def _documento() -> Document:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2)
        s.top_margin = s.bottom_margin = Cm(1.8)
    for nivel in (1, 2, 3):
        doc.styles[f"Heading {nivel}"].font.color.rgb = AZUL
    return doc


def _inline(par, texto: str):
    for parte in INLINE.split(texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            par.add_run(parte[2:-2]).bold = True
        elif parte.startswith("*") and parte.endswith("*"):
            par.add_run(parte[1:-1]).italic = True
        elif parte.startswith("["):
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", parte)
            par.add_run(f"{m.group(1)} ({m.group(2)})")
        else:
            par.add_run(parte)


def markdown(doc, texto: str):
    """Markdown simples (parágrafos, listas, ### títulos, negrito/itálico/links) -> parágrafos Word."""
    buffer = []

    def fechar():
        if buffer:
            _inline(doc.add_paragraph(), " ".join(buffer))
            buffer.clear()

    for linha in (texto or "").splitlines():
        s = linha.strip()
        if not s:
            fechar()
            continue
        m_titulo = re.match(r"^(#{3,6})\s+(.*)", s)
        m_bullet = re.match(r"^[-*•]\s+(.*)", s)
        m_num = re.match(r"^\d+[.)]\s+(.*)", s)
        if m_titulo:
            fechar()
            doc.add_heading(m_titulo.group(2), level=3)
        elif m_bullet:
            fechar()
            _inline(doc.add_paragraph(style="List Bullet"), m_bullet.group(1))
        elif m_num:
            fechar()
            _inline(doc.add_paragraph(style="List Number"), m_num.group(1))
        else:
            buffer.append(s)
    fechar()


def _sombrear(celula, cor_hex: str):
    tc_pr = celula._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor_hex)
    tc_pr.append(shd)


def tabela(doc, cabecalho: list, linhas: list, larguras_cm: list | None = None, fonte: int = 8, cores: dict | None = None):
    t = doc.add_table(rows=1, cols=len(cabecalho))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, titulo in enumerate(cabecalho):
        c = t.rows[0].cells[i]
        c.text = ""
        run = c.paragraphs[0].add_run(str(titulo))
        run.bold, run.font.size, run.font.color.rgb = True, Pt(fonte), RGBColor(0xFF, 0xFF, 0xFF)
        _sombrear(c, "1F4E78")
    for linha in linhas:
        cels = t.add_row().cells
        for i, valor in enumerate(linha):
            cels[i].text = ""
            run = cels[i].paragraphs[0].add_run("" if valor is None else str(valor))
            run.font.size = Pt(fonte)
            if cores and i in cores and cores[i](valor):
                _sombrear(cels[i], cores[i](valor))
    if larguras_cm:
        for row in t.rows:
            for i, w in enumerate(larguras_cm):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def _cor_resposta():
    mapa = {"pleno": "C6EFCE", "parcial": "FFF2CC", "nao": "F8CBAD", "na": "EDEDED"}
    return lambda valor: mapa.get(resp_mod.nivel(str(valor), []))


def _capa(doc, titulo: str, subtitulo: str, cliente: dict, confidencial: bool, preliminar: str = ""):
    doc.add_paragraph()
    if preliminar:
        p = doc.add_paragraph()
        r = p.add_run(f"PRELIMINAR — {preliminar}")
        r.bold, r.font.size, r.font.color.rgb = True, Pt(11), RGBColor(0xC0, 0x39, 0x2B)
    p = doc.add_paragraph()
    r = p.add_run(titulo)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(24), AZUL
    p = doc.add_paragraph()
    r = p.add_run(subtitulo)
    r.font.size, r.font.color.rgb = Pt(13), CINZA
    p = doc.add_paragraph()
    r = p.add_run(f"{cliente.get('nome', '')} · {dt.date.today().strftime('%d/%m/%Y')}")
    r.font.size = Pt(11)
    if confidencial:
        p = doc.add_paragraph()
        r = p.add_run("Documento confidencial — uso restrito ao processo de contratação.")
        r.italic, r.font.size, r.font.color.rgb = True, Pt(9), CINZA


def _secao_narrativa(doc, narrativa: dict, chave: str, titulo: str | None = None, nivel: int = 1):
    if narrativa.get(chave):
        doc.add_heading(titulo or chave, level=nivel)
        markdown(doc, narrativa[chave])


def _preliminar(ctx: dict) -> str:
    """Texto da marca PRELIMINAR quando a execução assistida (KB, revisão por LLM, URLs) não se completou."""
    ex = ctx.get("execucao") or {}
    if ex.get("assistida") and not ex.get("completa"):
        return "execução assistida incompleta: " + "; ".join(ex.get("pendencias") or [])[:300]
    return ""


def gerar_sumario(projeto, ctx: dict) -> Path:
    cfg = projeto.cfg
    doc = _documento()
    proponente = ctx.get("proponente_nome")
    titulo = "Sumário Executivo"
    sub = (f"{proponente} — resposta à RFP de observabilidade" if cfg["modo"] == "proponente"
           else "Estudo de seleção de solução de observabilidade")
    _capa(doc, titulo, sub, cfg["cliente"], cfg["relatorio"].get("confidencial", True), _preliminar(ctx))
    narrativa = ctx.get("narrativa_md") or {}
    _secao_narrativa(doc, narrativa, "Recomendação", "Mensagem principal" if proponente else "Recomendação")
    cob = ctx.get("cobertura")
    if cfg["modo"] == "proponente":
        # peça do cliente: nunca leva o scorecard dos concorrentes (inteligência competitiva é interna)
        doc.add_heading("Quadro-resumo da aderência", level=1)
        if cob and cob["respondidos"]:
            doc.add_paragraph(f"{cob['respondidos']} de {cob['total']} requisitos respondidos.")
            for t in cob["tabelas"]:
                doc.add_paragraph(t["abas"]).runs[0].bold = True
                tabela(doc, ["Obrigatoriedade"] + t["escala"], t["linhas"], fonte=9)
        else:
            doc.add_paragraph("⚠️ Respostas ainda não preenchidas (02-analise/respostas.json) — quadro pendente.")
    elif ctx.get("ranking"):
        doc.add_heading("Scorecard", level=1)
        tabela(doc, ["#", "Fornecedor", "Aderência %", "Nota final", "Gate"],
               [[l["posicao"], l["nome"], util.br(l["aderencia_pct"]), util.br(l["nota_final"], 2), l["status_gate"]]
                for l in ctx["ranking"]["ranking"]], fonte=9)
    _secao_narrativa(doc, narrativa, "Fatores estratégicos", "Destaques" if proponente else None)
    _secao_narrativa(doc, narrativa, "Ressalvas")
    _secao_narrativa(doc, narrativa, "Próximos passos")
    destino = projeto.dir_entregas / f"Sumario-Executivo-{projeto.sigla}.docx"
    doc.save(str(destino))
    return destino


def gerar_memorial(projeto, kb: KB, ctx: dict) -> Path | None:
    cfg = projeto.cfg
    todas = [r for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []
             if r.get("resposta") and not r.get("_orfa")]
    if cfg["modo"] != "proponente" or not todas:
        return None
    rtm = {r["id"]: r for r in util.ler_json(projeto.dir_projeto / "rtm.json")["requisitos"]}
    respostas = [r for r in todas if r["id"] in rtm]
    cob = ctx.get("cobertura") or resp_mod.cobertura(projeto)
    narrativa = ctx.get("narrativa_md") or {}
    proponente = ctx.get("proponente_nome") or cfg.get("proponente")
    doc = _documento()
    _capa(doc, "Memorial Técnico", f"{proponente} — resposta à RFP de observabilidade", cfg["cliente"],
          cfg["relatorio"].get("confidencial", True), _preliminar(ctx))
    doc.add_page_break()

    _secao_narrativa(doc, narrativa, "Recomendação", "1. Sumário executivo")
    doc.add_heading("2. Metodologia e premissas", level=1)
    validacao = util.ler_csv(projeto.dir_analise / "validacao-urls.csv")
    escalas = "; ".join(f"{t['abas']}: {' / '.join(t['escala'])}" for t in cob["tabelas"])
    for item in [
        f"Cada requisito do edital recebeu uma autoavaliação na escala da própria planilha ({escalas}).",
        "Somente recursos em disponibilidade geral (GA) com SLA sustentam respostas plenas; recursos em preview não pontuam.",
        "'Atende parcialmente' só com base GA demonstrável; sem caminho oficial suportado, a resposta é 'Não atende'.",
        "Toda resposta cita evidência na documentação oficial do fabricante (Anexo A)"
        + (f"; {len(validacao)} URLs verificadas por HTTP em {validacao[0].get('verificado_em', '')}." if validacao else "."),
        f"Data de referência do estudo: {projeto.data_ref.strftime('%d/%m/%Y')}.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("3. Resumo quantitativo", level=1)
    doc.add_paragraph(f"{cob['respondidos']} de {cob['total']} requisitos respondidos.")
    for t in cob["tabelas"]:
        doc.add_paragraph(t["abas"]).runs[0].bold = True
        tabela(doc, ["Obrigatoriedade"] + t["escala"], t["linhas"], fonte=9)
    if cob["eliminatorios_em_risco"]:
        doc.add_paragraph("Requisitos eliminatórios com resposta parcial ou negativa:").runs[0].bold = True
        for n in cob["eliminatorios_em_risco"]:
            doc.add_paragraph(f"{n['id']} — {n['resposta']}: {n['requisito']}", style="List Bullet")

    _secao_narrativa(doc, narrativa, "Arquitetura", "4. Arquitetura da solução")

    doc.add_heading("5. Respostas por requisito", level=1)
    grupos = {}
    for r in respostas:
        base = rtm[r["id"]]
        grupos.setdefault(f"{base['fonte']} — {base['secao']}".strip(" —"), {}).setdefault(
            base["bloco"] or "Geral", []).append((base, r))
    for titulo_grupo, blocos in grupos.items():
        doc.add_heading(titulo_grupo, level=2)
        for bloco, itens in blocos.items():
            doc.add_heading(bloco, level=3)
            linhas = []
            for base, r in itens:
                extras = []
                if util.norm(r.get("metodo") or "nativo") != "nativo":
                    extras.append(f"[Método: {r['metodo']}.]")
                if r.get("poc"):
                    extras.append("[Comprovação em POC.]")
                evs = [str(e) for e in r.get("evidencias") or [] if kb.evidencia(e)]
                urls = [str(e) for e in r.get("evidencias") or [] if str(e).startswith("http")]
                if evs:
                    extras.append("Evidências: " + ", ".join(evs))
                if urls:
                    extras.append("Ref.: " + "; ".join(urls))
                linhas.append([r["id"], base["texto"], base["obrigatoriedade"], r["resposta"],
                               " ".join([r.get("justificativa") or ""] + extras).strip()])
            tabela(doc, ["ID", "Requisito", "Obrig.", "Resposta", "Justificativa e evidências"], linhas,
                   [1.6, 5.2, 1.7, 2.2, 6.3], fonte=8, cores={3: _cor_resposta()})

    from .analises import nota_case
    from .evidencias import referencias_do_estudo
    refs = [c for c in referencias_do_estudo(projeto, kb) if not c["_kb_ausente"]]
    cases = sorted([c for c in refs if c.get("tipo") != "arquitetura"], key=lambda c: -(nota_case(c) or -1))
    arquiteturas = [c for c in refs if c.get("tipo") == "arquitetura"]
    n = 6
    if refs:
        doc.add_heading(f"{n}. Maturidade da solução — casos de referência", level=1)
        doc.add_paragraph("Casos de clientes e arquiteturas de referência publicados pelo fabricante, com a relação de "
                          "cada um com o cenário deste edital. Resultados reproduzidos como publicados.")
        if cases:
            doc.add_heading(f"{n}.1 Casos de clientes (publicados)", level=2)
            com_nota = any(nota_case(c) is not None for c in cases)
            tabela(doc, ["Organização", "Setor / país", "Cenário e resultados", "Relação com este edital"]
                   + (["Aderência (0–10)"] if com_nota else []) + ["Fonte"],
                   [[c.get("organizacao"), " / ".join(str(x) for x in (c.get("setor"), c.get("pais")) if x),
                     " ".join([str(c.get("cenario") or "")] + [f"• {r}" for r in c.get("resultados") or []]).strip(),
                     c.get("relacao") or ""] + ([util.br(nota_case(c), 1)] if com_nota else [])
                    + [f"{c.get('fonte') or ''} {c.get('url') or ''}".strip()] for c in cases],
                   [2.4, 2.2, 5.2, 3.4] + ([1.4] if com_nota else []) + [3.2], fonte=8)
        if arquiteturas:
            doc.add_heading(f"{n}.2 Arquiteturas de referência oficiais", level=2)
            tabela(doc, ["Referência", "Cenário", "Relação com este edital", "URL"],
                   [[c.get("organizacao"), c.get("cenario"), c.get("relacao") or "", c.get("url")] for c in arquiteturas],
                   [3.2, 5.4, 4, 5], fonte=8)
        n += 1
    for chave, rotulo in (("Fatores estratégicos", "Diferenciais"), ("Ressalvas", "Ressalvas e lacunas assumidas"),
                          ("Próximos passos", "Próximos passos")):
        if narrativa.get(chave):
            _secao_narrativa(doc, narrativa, chave, f"{n}. {rotulo}")
            n += 1

    doc.add_heading("Anexo A — Evidências oficiais", level=1)
    status_url = {v["url"]: v for v in validacao}
    usadas = sorted({str(e) for r in respostas for e in r.get("evidencias") or [] if kb.evidencia(e)})
    linhas = []
    for eid in usadas:
        e = kb.evidencia(eid)
        v = status_url.get(e["url"])
        linhas.append([eid, e["capacidade"], e["url"],
                       (v.get("verificado_em") if v else str(e.get("verificado_em") or "")) or ""])
    diretas = sorted({str(e) for r in respostas for e in r.get("evidencias") or [] if str(e).startswith("http")})
    linhas += [["—", "Referência direta", u, (status_url.get(u) or {}).get("verificado_em", "")] for u in diretas]
    tabela(doc, ["ID", "Capacidade", "URL", "Verificado em"], linhas, [2, 5.5, 8, 2], fonte=8)

    destino = projeto.dir_entregas / f"Memorial-Tecnico-{util.nome_arquivo_seguro(proponente).replace(' ', '-')}-{projeto.sigla}.docx"
    doc.save(str(destino))
    return destino


def converter_pdf(caminhos: list) -> list:
    """DOCX -> PDF: Word via COM (Windows) ou LibreOffice (soffice). Sem nenhum dos dois, apenas avisa."""
    caminhos = [Path(c).resolve() for c in caminhos if c]
    if not caminhos:
        return []
    saidas = []
    try:
        import win32com.client  # type: ignore
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        try:
            for c in caminhos:
                pdf = c.with_suffix(".pdf")
                doc = word.Documents.Open(str(c), ReadOnly=True)
                doc.SaveAs(str(pdf), FileFormat=17)
                doc.Close(False)
                saidas.append(pdf)
        finally:
            word.Quit()
        return saidas
    except ImportError:
        pass
    except Exception as e:
        print(f"AVISO: conversão via Word falhou ({type(e).__name__}); tentando LibreOffice")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        for c in caminhos:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(c.parent), str(c)],
                           capture_output=True, timeout=180)
            if c.with_suffix(".pdf").exists():
                saidas.append(c.with_suffix(".pdf"))
        return saidas
    print("AVISO: PDF não gerado — instale o Microsoft Word (pywin32) ou o LibreOffice.")
    return saidas


def gerar(projeto, kb: KB | None = None, ctx: dict | None = None, pdf: bool = False) -> list:
    kb = kb or KB()
    projeto.criar_pastas()
    docs = [gerar_sumario(projeto, ctx or {}), gerar_memorial(projeto, kb, ctx or {})]
    docs = [d for d in docs if d]
    return docs + (converter_pdf(docs) if pdf else [])
