"""Extração fiel dos documentos do edital (docx, xlsx, pdf) para markdown em 01-extracao/."""
import re
from pathlib import Path

from docx import Document
from docx.document import Document as _Documento
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from . import util

_TITULO_RE = re.compile(r"^(heading|titulo|ttulo)(\d)$")
_LISTA_RE = re.compile(r"^(list|lista|bullet|marcador|commarcador|numerad)")


def iterar_blocos(pai):
    """Parágrafos e tabelas na ordem do documento."""
    elemento = pai.element.body if isinstance(pai, _Documento) else pai._tc
    for filho in elemento.iterchildren():
        if isinstance(filho, CT_P):
            yield Paragraph(filho, pai)
        elif isinstance(filho, CT_Tbl):
            yield Table(filho, pai)


def nivel_titulo(p: Paragraph):
    """Nível de título (1..9) pelo estilo (Heading/Título/Ttulo) ou outline level; None se não for título."""
    estilo = p.style
    for nome in (getattr(estilo, "name", "") or "", getattr(estilo, "style_id", "") or ""):
        n = util.norm(nome).replace(" ", "")
        m = _TITULO_RE.match(n)
        if m:
            return int(m.group(2))
        if n in ("title", "titulo"):
            return 1
    for alvo in (p._p, getattr(estilo, "element", None)):
        if alvo is None:
            continue
        try:
            val = alvo.xpath("./w:pPr/w:outlineLvl/@w:val")
        except Exception:
            val = []
        if val and val[0].isdigit() and int(val[0]) < 9:
            return int(val[0]) + 1
    return None


def eh_item_lista(p: Paragraph) -> bool:
    try:
        if p._p.xpath("./w:pPr/w:numPr"):
            return True
    except Exception:
        pass
    nome = util.norm(getattr(p.style, "name", "") or "").replace(" ", "")
    return bool(_LISTA_RE.match(nome))


def texto_celula(celula: _Cell) -> str:
    partes = [p.text.strip() for p in celula.paragraphs if p.text.strip()]
    return " ".join(partes).strip()


def tabela_docx_linhas(tabela: Table) -> list:
    linhas = []
    for linha in tabela.rows:
        try:
            linhas.append([texto_celula(c) for c in linha.cells])
        except Exception:
            continue
    return linhas


def _md_tabela(linhas: list) -> str:
    if not linhas:
        return ""
    ncol = max(len(l) for l in linhas)
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", "<br>")
    saida = ["| " + " | ".join(esc(c) for c in (linhas[0] + [""] * (ncol - len(linhas[0])))) + " |",
             "| " + " | ".join(["---"] * ncol) + " |"]
    for l in linhas[1:]:
        saida.append("| " + " | ".join(esc(c) for c in (l + [""] * (ncol - len(l)))) + " |")
    return "\n".join(saida)


def docx_para_markdown(caminho: Path, dir_imagens: Path) -> tuple[str, dict]:
    doc = Document(str(caminho))
    n_img = 0
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                n_img += 1
                dir_imagens.mkdir(parents=True, exist_ok=True)
                ext = Path(rel.target_ref).suffix or ".png"
                (dir_imagens / f"{caminho.stem}__img{n_img:03d}{ext}").write_bytes(rel.target_part.blob)
            except Exception:
                continue
    partes, n_par, n_tab = [], 0, 0
    for bloco in iterar_blocos(doc):
        if isinstance(bloco, Table):
            n_tab += 1
            partes += ["", _md_tabela(tabela_docx_linhas(bloco)), ""]
            continue
        texto = bloco.text.strip()
        if not texto:
            continue
        n_par += 1
        nivel = nivel_titulo(bloco)
        if nivel:
            partes.append("#" * min(nivel + 1, 6) + " " + texto)
        elif eh_item_lista(bloco):
            partes.append("- " + texto)
        else:
            partes.append(texto)
    return "\n".join(partes), {"paragrafos": n_par, "tabelas": n_tab, "imagens": n_img}


def xlsx_para_markdown(caminho: Path, max_linhas: int = 3000) -> tuple[str, dict]:
    import openpyxl
    from openpyxl.utils import get_column_letter

    wb = openpyxl.load_workbook(str(caminho), data_only=True, read_only=True)
    partes, stats = [], {}
    for ws in wb.worksheets:
        linhas = []
        for r_idx, linha in enumerate(ws.iter_rows(values_only=True), start=1):
            if r_idx > max_linhas:
                break
            valores = ["" if v is None else str(v).strip() for v in linha]
            if any(valores):
                linhas.append((r_idx, valores))
        stats[ws.title] = len(linhas)
        partes.append(f"\n## Aba: {ws.title}\n")
        if not linhas:
            partes.append("_(vazia)_")
            continue
        ncol = max(max((i for i, v in enumerate(vals, 1) if v), default=0) for _, vals in linhas)
        cab = ["Linha"] + [get_column_letter(i) for i in range(1, ncol + 1)]
        tabela = [cab] + [[str(r)] + vals[:ncol] + [""] * (ncol - len(vals[:ncol])) for r, vals in linhas]
        partes.append(_md_tabela(tabela))
    wb.close()
    return "\n".join(partes), {"linhas_por_aba": stats}


MIN_CHARS_PAGINA = 20


def _ocr_pagina(doc, indice: int, idioma: str, dir_imagens: Path | None, prefixo: str):
    """(texto, confiança média) da página via Tesseract. O executável pode vir de TESSERACT_CMD e os dados de
    idioma de TESSDATA_PREFIX. A imagem renderizada fica em 01-extracao/imagens/ para conferência."""
    import os

    import pytesseract
    from PIL import Image
    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    pix = doc[indice].get_pixmap(dpi=200)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if dir_imagens is not None:
        dir_imagens.mkdir(parents=True, exist_ok=True)
        img.save(dir_imagens / f"{prefixo}__p{indice + 1:03d}.png")
    texto = pytesseract.image_to_string(img, lang=idioma).strip()
    dados = pytesseract.image_to_data(img, lang=idioma, output_type=pytesseract.Output.DICT)
    confs = [float(c) for c in dados.get("conf", []) if str(c).strip() not in ("", "-1")]
    return texto, (round(sum(confs) / len(confs), 1) if confs else None)


def pdf_paginas(caminho: Path, ocr: bool = False, idioma: str = "por+eng", dir_imagens: Path | None = None) -> list:
    """[{pagina, texto, chars, ocr, ocr_conf}] por página. OCR opcional nas páginas sem texto (requer pymupdf,
    pytesseract e o Tesseract instalado)."""
    from pypdf import PdfReader

    paginas = [{"pagina": i, "texto": (p.extract_text() or "").strip(), "ocr": False, "ocr_conf": None}
               for i, p in enumerate(PdfReader(str(caminho)).pages, start=1)]
    candidatas = [p for p in paginas if len(p["texto"]) < MIN_CHARS_PAGINA]
    if ocr and candidatas:
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(caminho))
            for p in candidatas:
                texto, conf = _ocr_pagina(doc, p["pagina"] - 1, idioma, dir_imagens, Path(caminho).stem)
                if texto:
                    p.update({"texto": texto, "ocr": True, "ocr_conf": conf})
        except ImportError:
            print(f"AVISO: OCR indisponível para {Path(caminho).name} — instale pymupdf e pytesseract e o Tesseract "
                  "(TESSERACT_CMD aponta o executável)")
        except Exception as e:  # Tesseract ausente/sem idioma (TesseractNotFoundError, TesseractError…)
            print(f"AVISO: OCR falhou em {Path(caminho).name} ({type(e).__name__}: {str(e)[:120]}) — páginas "
                  "seguem sem texto; confira TESSERACT_CMD/TESSDATA_PREFIX e ocr_idioma")
    for p in paginas:
        p["chars"] = len(p["texto"])
    return paginas


def pdf_para_markdown(caminho: Path, ocr: bool = False, idioma: str = "por+eng",
                      dir_imagens: Path | None = None) -> tuple[str, dict]:
    paginas = pdf_paginas(caminho, ocr, idioma, dir_imagens)
    partes = []
    for p in paginas:
        partes.append(f"\n## Página {p['pagina']}" + (f" (OCR, confiança {p['ocr_conf']})" if p["ocr"] else "") + "\n")
        partes.append(p["texto"] if p["chars"] >= MIN_CHARS_PAGINA else (
            (p["texto"] + "\n\n") if p["texto"] else "") +
            "_(página sem texto extraível — provavelmente escaneada; use ocr: true ou OCR externo)_")
    sem_texto = [p["pagina"] for p in paginas if p["chars"] < MIN_CHARS_PAGINA]
    return "\n".join(partes), {"paginas": len(paginas), "paginas_sem_texto": len(sem_texto),
                               "paginas_sem_texto_lista": sem_texto,
                               "paginas_ocr": [p["pagina"] for p in paginas if p["ocr"]],
                               "ocr_confianca": {p["pagina"]: p["ocr_conf"] for p in paginas if p["ocr"]},
                               "caracteres": sum(p["chars"] for p in paginas),
                               "caracteres_por_pagina": [p["chars"] for p in paginas]}


def tipo_entrada(entrada: dict, caminho: Path) -> str:
    return (entrada.get("tipo") or caminho.suffix.lower().lstrip(".")).lower()


def extrair(projeto) -> list:
    """Gera 01-extracao/<arquivo>.md para cada entrada do rfp.yaml. Retorna estatísticas."""
    projeto.criar_pastas()
    resultados = []
    for entrada in projeto.cfg["entradas"]:
        caminho = projeto.pasta_cliente / entrada["arquivo"]
        if not caminho.exists():
            resultados.append({"arquivo": entrada["arquivo"], "erro": "arquivo não encontrado"})
            continue
        tipo = tipo_entrada(entrada, caminho)
        if tipo == "docx":
            md, stats = docx_para_markdown(caminho, projeto.dir_extracao / "imagens")
        elif tipo in ("xlsx", "xlsm"):
            md, stats = xlsx_para_markdown(caminho)
        elif tipo == "pdf":
            md, stats = pdf_para_markdown(caminho, bool(entrada.get("ocr")), entrada.get("ocr_idioma") or "por+eng",
                                          projeto.dir_extracao / "imagens")
        else:
            resultados.append({"arquivo": entrada["arquivo"], "erro": f"tipo não suportado: {tipo}"})
            continue
        destino = projeto.dir_extracao / f"{caminho.stem}.md"
        cabecalho = f"# {caminho.name} — extração fiel\n\n_Fonte: {caminho.name} · extração automática pelo kit_\n\n"
        destino.write_text(cabecalho + md, encoding="utf-8")
        resultados.append({"arquivo": entrada["arquivo"], "tipo": tipo, "saida": str(destino), **stats})
    util.gravar_json(projeto.dir_extracao / "extracao-qa.json",
                     [{k: v for k, v in r.items() if k != "saida"} for r in resultados])
    return resultados
