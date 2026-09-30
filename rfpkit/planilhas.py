"""Planilhas do cliente: leitura de dropdowns (inclusive a extensão x14 do Excel 2010+) e gravação CIRÚRGICA —
só as células respondidas são alteradas no XML da aba; todas as demais partes do pacote (imagens EMF, formas,
cabeçalhos, formatação condicional, validações x14, macros) são copiadas byte a byte."""
import re
import zipfile

from lxml import etree
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string, get_column_letter, range_boundaries
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

from . import util

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
NS_XM = "http://schemas.microsoft.com/office/excel/2006/main"
XML_ESPACO = "{http://www.w3.org/XML/1998/namespace}space"
CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
DINAMICA = re.compile(r"\b(OFFSET|DESLOC|INDIRECT|INDIRETO|INDEX|ÍNDICE|INDICE)\s*\(", re.I)


# ---------------------------------------------------------------- pacote xlsx
def mapa_abas(z: zipfile.ZipFile) -> dict:
    """{nome da aba: caminho da parte XML} a partir de workbook.xml e seus relacionamentos."""
    wb = etree.fromstring(z.read("xl/workbook.xml"))
    rels = etree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    alvos = {r.get("Id"): r.get("Target") for r in rels}
    abas = {}
    for s in wb.iter(f"{{{NS}}}sheet"):
        alvo = alvos.get(s.get(f"{{{NS_R}}}id"), "")
        abas[s.get("name")] = alvo.lstrip("/") if alvo.startswith("/") else f"xl/{alvo}"
    return abas


def validacoes(caminho) -> dict:
    """{aba: [{"tipo", "sqref", "formula1", "x14"}]} — validações clássicas e as da extensão x14."""
    saida = {}
    with zipfile.ZipFile(caminho) as z:
        for aba, parte in mapa_abas(z).items():
            if parte not in z.namelist():
                continue
            raiz = etree.fromstring(z.read(parte))
            dvs = []
            for dv in raiz.iter(f"{{{NS}}}dataValidation"):
                f1 = dv.find(f"{{{NS}}}formula1")
                dvs.append({"tipo": dv.get("type", ""), "sqref": dv.get("sqref", ""), "x14": False,
                            "formula1": (f1.text or "") if f1 is not None else ""})
            for dv in raiz.iter(f"{{{NS_X14}}}dataValidation"):
                f1 = dv.find(f"{{{NS_X14}}}formula1/{{{NS_XM}}}f")
                sq = dv.find(f"{{{NS_XM}}}sqref")
                dvs.append({"tipo": dv.get("type", ""), "sqref": (sq.text or "") if sq is not None else "", "x14": True,
                            "formula1": (f1.text or "") if f1 is not None else ""})
            saida[aba] = dvs
    return saida


def _cobre(sqref: str, coord: str) -> bool:
    try:
        return coord in MultiCellRange(sqref)
    except (ValueError, TypeError):
        return False


def _coluna_em(sqref: str, coluna: str) -> bool:
    idx = column_index_from_string(coluna)
    try:
        return any(cr.min_col <= idx <= cr.max_col for cr in MultiCellRange(sqref).ranges)
    except (ValueError, TypeError):
        return False


def dv_da_celula(dvs: list, coord: str):
    """Validação de lista que cobre a célula; senão, a que cobre outra parte da mesma coluna (dropdown curto)."""
    listas = [d for d in dvs or [] if d["tipo"] == "list" and d["formula1"]]
    col = coordinate_from_string(coord)[0]
    return next((d for d in listas if _cobre(d["sqref"], coord)), None) or \
        next((d for d in listas if _coluna_em(d["sqref"], col)), None)


# ---------------------------------------------------------------- valores da lista
def _separar_aba(ref: str):
    if "!" not in ref:
        return None, ref
    aba, intervalo = ref.rsplit("!", 1)
    if aba.startswith("'") and aba.endswith("'"):
        aba = aba[1:-1].replace("''", "'")
    return aba, intervalo


def _valores_intervalo(wb, ref: str, ws_padrao=None) -> list:
    aba, intervalo = _separar_aba(ref.strip().lstrip("="))
    ws = wb[aba] if aba and aba in wb.sheetnames else (ws_padrao if not aba else None)
    if ws is None:
        return []
    try:
        min_col, min_row, max_col, max_row = range_boundaries(intervalo.replace("$", ""))
    except (ValueError, TypeError):
        return []
    valores = []
    for linha in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=True):
        valores += [str(v).strip() for v in linha if v not in (None, "")]
    return valores


def _nome_definido(wb, ws, nome: str):
    for colecao in (getattr(ws, "defined_names", None) or {}, wb.defined_names):
        try:
            dn = colecao.get(nome)
        except Exception:
            dn = None
        if dn is not None:
            return dn
    return None


def valores_da_lista(wb, ws, formula1: str) -> list:
    """Resolve o formula1 de uma validação de lista: literal "A,B", intervalo (inclusive em outra aba) ou nome
    definido. Listas dinâmicas (OFFSET/INDIRECT…) não são resolvidas: retorna []."""
    f = str(formula1 or "").strip().lstrip("=")
    if not f or DINAMICA.search(f):
        return []
    if f.startswith('"') and f.endswith('"'):
        return [v.strip() for v in f[1:-1].split(",") if v.strip()]
    dn = _nome_definido(wb, ws, f)
    if dn is not None:
        if DINAMICA.search(str(dn.attr_text or "")):
            return []
        valores = []
        try:
            for aba, intervalo in dn.destinations:
                valores += _valores_intervalo(wb, f"'{aba.replace(chr(39), chr(39) * 2)}'!{intervalo}")
        except Exception:
            return []
        return valores
    return _valores_intervalo(wb, f, ws)


def normalizar_na_escala(valor: str, escala: list):
    """Valor exato da escala que corresponde a 'valor' ignorando maiúsculas/acentos; None se não houver."""
    alvo = util.norm(valor)
    return next((e for e in escala or [] if util.norm(e) == alvo), None)


# ---------------------------------------------------------------- gravação cirúrgica
def _limpar(texto) -> str:
    return CONTROLE.sub("", str(texto))


def _linhas(sheet_data):
    """(número, elemento) de cada <row>, tolerando o atributo 'r' ausente (numeração implícita)."""
    n = 0
    for r in sheet_data.findall(f"{{{NS}}}row"):
        n = int(r.get("r")) if r.get("r") else n + 1
        yield n, r


def _gravar_celula(sheet_data, coord: str, valor):
    col, linha_n = coordinate_from_string(coord)
    ci = column_index_from_string(col)
    linha = None
    for n, r in _linhas(sheet_data):
        if n == linha_n:
            linha = r
            break
        if n > linha_n:
            linha = etree.Element(f"{{{NS}}}row", r=str(linha_n))
            r.addprevious(linha)
            break
    if linha is None:
        linha = etree.SubElement(sheet_data, f"{{{NS}}}row", r=str(linha_n))
    cel = None
    for c in linha.findall(f"{{{NS}}}c"):
        ref = c.get("r")
        if not ref:
            continue
        cci = column_index_from_string(coordinate_from_string(ref)[0])
        if cci == ci:
            cel = c
            break
        if cci > ci:
            cel = etree.Element(f"{{{NS}}}c", r=coord)
            c.addprevious(cel)
            break
    if cel is None:
        cel = etree.SubElement(linha, f"{{{NS}}}c", r=coord)
    linha.attrib.pop("spans", None)
    for filho in list(cel):
        cel.remove(filho)
    if valor in (None, ""):
        cel.attrib.pop("t", None)
        return
    cel.set("t", "inlineStr")
    t = etree.SubElement(etree.SubElement(cel, f"{{{NS}}}is"), f"{{{NS}}}t")
    t.text = _limpar(valor)
    t.set(XML_ESPACO, "preserve")


def _topo_mesclado(raiz, coord: str) -> str:
    col, linha = coordinate_from_string(coord)
    ci = column_index_from_string(col)
    for m in raiz.iter(f"{{{NS}}}mergeCell"):
        cr = CellRange(m.get("ref"))
        if cr.min_row <= linha <= cr.max_row and cr.min_col <= ci <= cr.max_col:
            return f"{get_column_letter(cr.min_col)}{cr.min_row}"
    return coord


def _estender(raiz, coords: list) -> int:
    """Inclui no dropdown (clássico ou x14) da coluna as células respondidas que ele ainda não cobre."""
    alvos = []
    for dv in raiz.iter(f"{{{NS}}}dataValidation"):
        if dv.get("type") == "list":
            alvos.append((lambda d=dv: d.get("sqref", ""), lambda s, d=dv: d.set("sqref", s)))
    for dv in raiz.iter(f"{{{NS_X14}}}dataValidation"):
        sq = dv.find(f"{{{NS_XM}}}sqref")
        if dv.get("type") == "list" and sq is not None:
            alvos.append((lambda e=sq: e.text or "", lambda s, e=sq: setattr(e, "text", s)))
    incluidas = 0
    for coord in coords:
        col = coordinate_from_string(coord)[0]
        if any(_cobre(ler(), coord) for ler, _ in alvos):
            continue
        for ler, gravar in alvos:
            if _coluna_em(ler(), col):
                gravar(f"{ler()} {coord}".strip())
                incluidas += 1
                break
    return incluidas


def gravar_celulas(origem, destino, valores: dict, estender: dict | None = None) -> dict:
    """valores: {aba: {coord: texto ou None}}; estender: {aba: [coords de resposta]}.
    Células mescladas são gravadas na célula superior esquerda (uma vez por intervalo)."""
    info = {"escritas": 0, "estendidas": 0, "mescladas": [], "conflitos": [], "partes_alteradas": []}
    with zipfile.ZipFile(origem) as zin:
        abas = mapa_abas(zin)
        novas = {}
        for aba, celulas in valores.items():
            parte = abas[aba]
            raiz = etree.fromstring(zin.read(parte))
            sheet_data = raiz.find(f"{{{NS}}}sheetData")
            gravadas = {}
            for coord, valor in celulas.items():
                alvo = _topo_mesclado(raiz, coord)
                if alvo != coord:
                    info["mescladas"].append(f"{aba}!{coord}->{alvo}")
                if alvo in gravadas and gravadas[alvo] != valor:
                    info["conflitos"].append(f"{aba}!{coord} (célula mesclada {alvo} já recebeu outro valor)")
                    continue
                gravadas[alvo] = valor
            for coord, valor in gravadas.items():
                _gravar_celula(sheet_data, coord, valor)
                info["escritas"] += 1
            coords_dv = sorted({_topo_mesclado(raiz, c) for c in (estender or {}).get(aba, [])})
            info["estendidas"] += _estender(raiz, coords_dv)
            info.setdefault("gravadas", {})[aba] = dict(gravadas)
            info.setdefault("respostas", {})[aba] = coords_dv
            novas[parte] = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
            info["partes_alteradas"].append(parte)
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                zout.writestr(item, novas.get(item.filename) or zin.read(item.filename))
    return info


def comparar_pacotes(original, copia, alteradas: list) -> list:
    """Partes do pacote (exceto as alteradas de propósito) que diferem ou sumiram na cópia."""
    with zipfile.ZipFile(original) as a, zipfile.ZipFile(copia) as b:
        nomes_b = set(b.namelist())
        return [n for n in a.namelist() if n not in alteradas and (n not in nomes_b or a.read(n) != b.read(n))]
