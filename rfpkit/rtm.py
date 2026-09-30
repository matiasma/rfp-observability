"""Matriz de requisitos canônica (RTM): adaptadores docx/xlsx/pdf + classificação na taxonomia."""
import re
from collections import Counter
from pathlib import Path

from docx import Document
from docx.table import Table

from . import planilhas, util
from .classificacao import NAO_CLASSIFICADO, Classificador
from .extracao import eh_item_lista, iterar_blocos, nivel_titulo, pdf_paginas, tabela_docx_linhas, tipo_entrada
from .kb import KB

NUM_RE = re.compile(r"^\s*(\d{1,3}(?:\.\d{1,3}){1,6})\.?\s*[-–—:)]?\s+(\S.*)$", re.S)
MARCADOR_RE = re.compile(r"^\s*(?:[-•▪◦–*]|[a-z]\)|[ivx]{1,4}\)|\(?[a-z]\))\s+", re.I)

GRUPOS_CABECALHO = {
    "id": ["id", "item", "codigo", "cod", "ref", "referencia", "numero", "no", "n", "#", "req id"],
    "requisito": ["requisito", "requisitos", "descricao", "especificacao", "funcionalidade", "caracteristica",
                  "criterio", "pergunta", "questao", "detalhamento", "exigencia", "metrica"],
    "tipo": ["tipo", "classificacao", "obrigatoriedade", "criticidade", "prioridade", "eliminatorio",
             "natureza do requisito", "obrigatorio"],
    "modulo": ["modulo", "categoria", "grupo", "area", "dominio", "tema", "capacidade", "subcategoria",
               "secao", "nivel", "bloco", "assunto"],
    "resposta": ["resposta", "atendimento", "aderencia", "atende", "status de atendimento", "autoavaliacao",
                 "auto avaliacao", "avaliacao", "avaliacao pelo fornecedor", "avaliacao do fornecedor",
                 "resposta do fornecedor"],
    "justificativa": ["justificativa", "comentario", "comentarios", "observacao", "observacoes", "evidencia",
                      "como atende", "detalhe da resposta"],
    "paginas": ["paginas", "pagina da proposta", "paginas da proposta", "pagina na proposta", "paginas na proposta",
                "referencia na proposta"],
}
_GRUPOS_RE = {g: util.compilar_palavras(ps) for g, ps in GRUPOS_CABECALHO.items()}
ESTRUTURAIS = ("id", "tipo", "modulo")
PRIORIDADE_GRUPOS = ("requisito", "resposta", "justificativa", "paginas", "tipo", "modulo", "id")


def _grupo_do_cabecalho(texto: str):
    """Grupo cuja palavra-chave aparece mais cedo no texto do cabeçalho ("Tipo de requisito" -> tipo)."""
    nt = util.norm(texto)
    if not nt or len(nt) > 60:
        return None
    melhor = None
    for prioridade, grupo in enumerate(PRIORIDADE_GRUPOS):
        posicoes = [m.start() for p in _GRUPOS_RE[grupo] for m in [p.search(nt)] if m]
        if posicoes:
            chave = (min(posicoes), prioridade)
            if melhor is None or chave < melhor[0]:
                melhor = (chave, grupo)
    return melhor[1] if melhor else None


def mapear_cabecalho(celulas: list) -> dict:
    """{grupo: [índices das colunas (0-based)]}, na ordem das colunas."""
    mapa = {}
    for i, c in enumerate(celulas):
        g = _grupo_do_cabecalho(c)
        if g:
            mapa.setdefault(g, []).append(i)
    return mapa


def cabecalho_valido(mapa: dict) -> bool:
    """Tabela de requisitos = coluna de requisito + ao menos uma coluna estrutural (id, tipo ou módulo)."""
    return "requisito" in mapa and any(g in mapa for g in ESTRUTURAIS)


def resolver_colunas(mapa: dict, linhas: list, clf: Classificador) -> dict:
    """Primeira coluna de cada grupo; a coluna de obrigatoriedade é confirmada pelo CONTEÚDO
    (ex.: cabeçalho "Categoria do Requisito" com valores "Eliminatório (Must Have)"); todas as colunas de
    módulo compõem o bloco."""
    col = {g: idx[0] for g, idx in mapa.items() if g != "modulo"}
    fixas = {col.get(g) for g in ("id", "requisito", "resposta", "justificativa", "paginas")}
    amostra = linhas[:40]

    def parece_tipo(j):
        valores = [l[j] for l in amostra if j < len(l) and str(l[j]).strip()]
        return len(valores) >= 3 and sum(1 for v in valores if clf.nivel_explicito(v)) / len(valores) >= 0.6

    if "tipo" not in col or not parece_tipo(col["tipo"]):
        ncol = max((len(l) for l in amostra), default=0)
        achado = next((j for j in range(ncol) if j not in fixas and parece_tipo(j)), None)
        if achado is not None:
            col["tipo"] = achado
    col["modulos"] = [j for j in mapa.get("modulo", []) if j != col.get("tipo")]
    return col


class Segmentador:
    """Transforma um fluxo de parágrafos (com nível de título/lista) em requisitos brutos."""

    def __init__(self, clf: Classificador, fonte: str, min_niveis: int = 3, verbo_livre: bool = True):
        self.clf, self.fonte = clf, fonte
        self.min_niveis, self.verbo_livre = min_niveis, verbo_livre
        self.titulos, self.reqs = {}, []
        self.pai, self.candidato = None, None

    def _bloco(self):
        return self.titulos[max(self.titulos)] if self.titulos else ""

    def _secao(self):
        return self.titulos[min(self.titulos)] if self.titulos else ""

    def titulo(self, nivel: int, texto: str):
        self.titulos = {k: v for k, v in self.titulos.items() if k < nivel}
        self.titulos[nivel] = texto.strip()
        self.pai = None

    def _req(self, texto, id_origem, local, explicito=""):
        r = {"id_origem": id_origem, "fonte": self.fonte, "localizacao": local, "secao": self._secao(),
             "bloco": self._bloco(), "texto": texto.strip(), "tipo_origem": explicito}
        self.reqs.append(r)
        self.pai = r if texto.rstrip().endswith(":") else None
        return r

    def paragrafo(self, texto: str, nivel=None, lista=False, local=""):
        texto = re.sub(r"\s+", " ", texto or "").strip()
        if len(texto) < 3:
            return
        verbo = self.clf.tem_verbo_obrigacao(texto)
        m = NUM_RE.match(texto)
        if m:
            num, corpo = m.group(1).rstrip("."), m.group(2).strip()
            niveis = len(num.split("."))
            c = self.candidato
            if c and num.startswith(c["id_origem"] + ".") and c in self.reqs:
                self.reqs.remove(c)
                self.titulo(len(c["id_origem"].split(".")), c["texto"])
            self.candidato = None
            if not verbo and len(corpo) <= 100:
                if niveis < self.min_niveis or nivel is not None:
                    self.titulo(niveis, corpo)
                    return
                self.candidato = self._req(corpo, num, local)
                return
            self._req(corpo, num, local)
            return
        if nivel is not None:
            if not verbo and len(texto) <= 120:
                self.titulo(nivel, texto)
                return
            if ":" in texto[:80]:
                rotulo, _, resto = texto.partition(":")
                if resto.strip() and self.clf.tem_verbo_obrigacao(resto) and len(rotulo) <= 80:
                    self.titulo(nivel + 1, rotulo)
                    self._req(resto, None, local)
                    return
            self._req(texto, None, local)
            return
        if (lista or MARCADOR_RE.match(texto)) and self.pai is not None:
            pai = self.pai
            pai["_filhos"] = pai.get("_filhos", 0) + 1
            filho = {**{k: v for k, v in pai.items() if not k.startswith("_")},
                     "id_origem": f"{pai['id_origem']}.{pai['_filhos']}" if pai["id_origem"] else None,
                     "texto": f"{pai['texto'].rstrip(':')}: {MARCADOR_RE.sub('', texto)}",
                     "localizacao": local}
            self.reqs.append(filho)
            return
        if verbo and len(texto) >= 25 and self.verbo_livre:
            self._req(texto, None, local)

    def tabela(self, linhas: list, local=""):
        """Tabela com cabeçalho reconhecível (coluna de requisito + estrutural) vira uma lista de requisitos."""
        self.pai = None
        if len(linhas) < 2:
            return
        mapa = mapear_cabecalho(linhas[0])
        if not cabecalho_valido(mapa):
            return
        col = resolver_colunas(mapa, linhas[1:], self.clf)
        modulos_atuais = {j: "" for j in col["modulos"]}
        for i, linha in enumerate(linhas[1:], start=2):
            cel = lambda g: (linha[col[g]] if g in col and col[g] < len(linha) else "").strip()
            for j in modulos_atuais:
                if j < len(linha) and linha[j]:
                    modulos_atuais[j] = linha[j]
            texto = cel("requisito")
            if len(texto) < 5:
                continue
            bloco = " / ".join(v for v in modulos_atuais.values() if v) or self._bloco()
            self.reqs.append({"id_origem": cel("id") or None, "fonte": self.fonte, "localizacao": f"{local} linha {i}",
                              "secao": self._secao(), "bloco": bloco, "texto": texto, "tipo_origem": cel("tipo")})

    def resultado(self) -> list:
        return [{k: v for k, v in r.items() if not k.startswith("_")} for r in self.reqs if not r.get("_filhos")]


def ler_docx(caminho: Path, entrada: dict, clf: Classificador) -> list:
    seg = Segmentador(clf, caminho.name, int(entrada.get("min_niveis_numeracao", 3)),
                      bool(entrada.get("detectar_paragrafos_com_verbo", True)))
    n_tab = 0
    for bloco in iterar_blocos(Document(str(caminho))):
        if isinstance(bloco, Table):
            n_tab += 1
            seg.tabela(tabela_docx_linhas(bloco), f"tabela {n_tab}")
        else:
            seg.paragrafo(bloco.text, nivel_titulo(bloco), eh_item_lista(bloco), "")
    return seg.resultado()


def _paragrafos_de_texto(texto: str) -> list:
    """Reconstrói parágrafos de texto corrido (PDF): quebra em numeração, marcador ou fim de frase."""
    saida, atual = [], ""
    for linha in (texto or "").splitlines():
        linha = linha.strip()
        if not linha:
            if atual:
                saida.append(atual)
            atual = ""
            continue
        novo = NUM_RE.match(linha) or MARCADOR_RE.match(linha) or atual.endswith((".", ";", ":"))
        if atual and novo:
            saida.append(atual)
            atual = linha
        else:
            atual = f"{atual} {linha}".strip()
    if atual:
        saida.append(atual)
    return saida


def ler_pdf(caminho: Path, entrada: dict, clf: Classificador) -> list:
    seg = Segmentador(clf, caminho.name, int(entrada.get("min_niveis_numeracao", 3)),
                      bool(entrada.get("detectar_paragrafos_com_verbo", True)))
    for i, pagina in enumerate(pdf_paginas(caminho, bool(entrada.get("ocr"))), start=1):
        for par in _paragrafos_de_texto(pagina):
            seg.paragrafo(par, None, bool(MARCADOR_RE.match(par)), f"página {i}")
    return seg.resultado()


def ler_xlsx(caminho: Path, entrada: dict, clf: Classificador, avisos: list) -> list:
    import warnings

    import openpyxl
    from openpyxl.utils import column_index_from_string, get_column_letter

    with warnings.catch_warnings():  # openpyxl avisa (e ignora) a extensão x14; lemos os dropdowns direto do XML
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(str(caminho), data_only=True)
    dvs_xml = planilhas.validacoes(caminho)
    abas_cfg = {a["nome"]: a for a in entrada.get("abas") or []}
    abas_lidas = [wb[n] for n in abas_cfg if n in wb.sheetnames] if abas_cfg else \
        [ws for ws in wb.worksheets if ws.sheet_state == "visible"]
    for nome in abas_cfg:
        if nome not in wb.sheetnames:
            avisos.append(f"{caminho.name}: aba '{nome}' não existe")
    reqs = []
    for ws in abas_lidas:
        cfg = abas_cfg.get(ws.title, {})
        linhas = [["" if v is None else str(v).strip() for v in linha]
                  for linha in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)]
        if cfg.get("colunas"):
            linha_cab = int(cfg.get("linha_cabecalho") or 1)
            mapa = {g: [column_index_from_string(str(l)) - 1] for g, l in cfg["colunas"].items()}
        elif cfg.get("linha_cabecalho"):
            linha_cab = int(cfg["linha_cabecalho"])
            mapa = mapear_cabecalho(linhas[linha_cab - 1]) if linha_cab <= len(linhas) else {}
        else:
            linha_cab, mapa = None, {}
            for r, valores in enumerate(linhas[:25], start=1):
                m = mapear_cabecalho(valores)
                if cabecalho_valido(m) and len(m) > len(mapa):
                    linha_cab, mapa = r, m
        if linha_cab is None or "requisito" not in mapa:
            avisos.append(f"{caminho.name}: aba '{ws.title}' sem cabeçalho de requisitos reconhecível — ignorada "
                          "(configure 'abas' com 'colunas' no rfp.yaml se for uma aba de requisitos)")
            continue
        dados, vazias = [], 0
        for r in range(linha_cab + 1, len(linhas) + 1):
            dados.append((r, linhas[r - 1]))
            vazias = 0 if any(linhas[r - 1]) else vazias + 1
            if vazias >= 30:
                break
        if cfg.get("colunas"):
            col = {g: idx[0] for g, idx in mapa.items() if g != "modulo"} | {"modulos": mapa.get("modulo", [])}
        else:
            col = resolver_colunas(mapa, [l for _, l in dados], clf)
        natureza_aba = cfg.get("natureza") or entrada.get("natureza") or ""
        escala_cfg = cfg.get("escala") or entrada.get("escala") or []
        cache_escala, sem_lista = {}, False
        modulos_atuais = {j: "" for j in col["modulos"]}
        for r, linha in dados:
            cel = lambda g: (linha[col[g]] if g in col and col[g] < len(linha) else "").strip()
            for j in modulos_atuais:
                if j < len(linha) and linha[j]:
                    modulos_atuais[j] = linha[j]
            texto = cel("requisito")
            if len(texto) < 5:
                continue
            coord = lambda g: f"{get_column_letter(col[g] + 1)}{r}" if g in col else None
            letra = lambda g: f"{ws.title}!{coord(g)}" if g in col else None
            escala = list(escala_cfg)
            if not escala and "resposta" in col:
                dv = planilhas.dv_da_celula(dvs_xml.get(ws.title, []), coord("resposta"))
                if dv is not None:
                    chave = (ws.title, dv["formula1"])
                    if chave not in cache_escala:
                        cache_escala[chave] = planilhas.valores_da_lista(wb, ws, dv["formula1"])
                    escala = cache_escala[chave]
                    sem_lista = sem_lista or not escala
            reqs.append({"id_origem": cel("id") or None, "fonte": caminho.name, "localizacao": f"{ws.title}!L{r}",
                         "secao": ws.title, "bloco": " / ".join(v for v in modulos_atuais.values() if v),
                         "texto": texto, "tipo_origem": cel("tipo"), "dica_natureza": natureza_aba or ws.title,
                         "celula_resposta": letra("resposta"), "celula_justificativa": letra("justificativa"),
                         "celula_paginas": letra("paginas"), "escala_resposta": escala})
        if sem_lista:
            avisos.append(f"{caminho.name}: aba '{ws.title}' tem dropdown de resposta cuja lista não pôde ser lida "
                          "(lista dinâmica ou externa) — informe 'escala' em entradas[].abas[] no rfp.yaml")
    return reqs


def _sigla_fonte(nome: str) -> str:
    palavras = [p for p in re.split(r"[^A-Za-z0-9]+", Path(nome).stem) if p]
    sigla = "".join(p[0] for p in palavras).upper()[:4]
    return sigla or "DOC"


def construir_rtm(projeto, kb: KB | None = None) -> dict:
    kb = kb or KB()
    cfg = projeto.cfg
    clf = Classificador(kb.taxonomia, (cfg.get("classificacao") or {}).get("mapa_blocos"))
    brutos, avisos = [], []
    for entrada in cfg["entradas"]:
        caminho = projeto.pasta_cliente / entrada["arquivo"]
        if not caminho.exists():
            avisos.append(f"entrada não encontrada: {entrada['arquivo']}")
            continue
        tipo = tipo_entrada(entrada, caminho)
        if tipo == "docx":
            lidos = ler_docx(caminho, entrada, clf)
        elif tipo in ("xlsx", "xlsm"):
            lidos = ler_xlsx(caminho, entrada, clf, avisos)
        elif tipo == "pdf":
            lidos = ler_pdf(caminho, entrada, clf)
        else:
            avisos.append(f"tipo não suportado: {entrada['arquivo']}")
            continue
        for r in lidos:
            r.setdefault("dica_natureza", entrada.get("natureza") or "")
            r["arquivo"] = entrada["arquivo"]
        brutos += lidos

    vistos, reqs, ids = set(), [], Counter()
    for r in brutos:
        chave = (r.get("arquivo") or r["fonte"], r.get("id_origem") or "", r.get("bloco") or "", util.norm(r["texto"]))
        if chave in vistos:
            continue
        vistos.add(chave)
        reqs.append(r)

    manual = {m.get("id"): m for m in util.ler_csv(projeto.dir_analise / "classificacao-manual.csv") if m.get("id")}
    from .revisao import ajustes as ajustes_revisao
    revisados = ajustes_revisao(projeto)
    revisados_texto = {}                   # errata que renumera: a correção segue o texto do requisito (se único)
    for texto_rev, campos_rev in revisados.values():
        revisados_texto.setdefault(util.norm(texto_rev), []).append(campos_rev)
    fontes = {r["fonte"] for r in reqs}
    seq = Counter()
    saida = []
    for r in reqs:
        sigla = _sigla_fonte(r["fonte"])
        if r.get("id_origem"):
            base = str(r["id_origem"]) if len(fontes) == 1 else f"{sigla}:{r['id_origem']}"
        else:
            seq[sigla] += 1
            base = f"{sigla}-{seq[sigla]:04d}"
        ids[base] += 1
        rid = base if ids[base] == 1 else f"{base}~{ids[base]}"
        cat, conf, origem = clf.categoria(r["texto"], r.get("bloco", ""), r.get("secao", ""))
        item = {
            "id": rid,
            "id_origem": r.get("id_origem") or "",
            "fonte": r["fonte"],
            "arquivo": r.get("arquivo") or r["fonte"],
            "localizacao": r.get("localizacao") or "",
            "secao": r.get("secao") or "",
            "bloco": r.get("bloco") or "",
            "texto": r["texto"],
            "categoria": cat,
            "confianca_classificacao": conf,
            "origem_classificacao": origem,
            "natureza": clf.natureza(r["texto"], r.get("bloco", ""), r.get("dica_natureza") or r.get("secao", "")),
            "obrigatoriedade": clf.obrigatoriedade(r["texto"], r.get("tipo_origem") or ""),
            "tipo_origem": r.get("tipo_origem") or "",
            "celula_resposta": r.get("celula_resposta") or "",
            "celula_justificativa": r.get("celula_justificativa") or "",
            "celula_paginas": r.get("celula_paginas") or "",
            "escala_resposta": r.get("escala_resposta") or [],
        }
        item["categoria_auto"], item["natureza_auto"], item["obrigatoriedade_auto"] = (
            item["categoria"], item["natureza"], item["obrigatoriedade"])
        llm = revisados.get(rid)
        if llm and util.norm(llm[0]) == util.norm(item["texto"]):
            campos_llm = llm[1]
        else:
            cand = revisados_texto.get(util.norm(item["texto"])) or []
            campos_llm = cand[0] if len(cand) == 1 else None
        if campos_llm:
            for campo, valor in campos_llm.items():
                item[campo] = valor
            if campos_llm.get("categoria"):
                item["origem_classificacao"], item["confianca_classificacao"] = "revisao-llm", 1.0
        m = manual.get(rid)
        if m:
            for campo in ("categoria", "natureza", "obrigatoriedade"):
                if m.get(campo):
                    item[campo] = m[campo]
            if m.get("categoria"):
                item["origem_classificacao"], item["confianca_classificacao"] = "manual", 1.0
        saida.append(item)

    ids_cat = {c["id"] for c in kb.categorias} | {NAO_CLASSIFICADO}
    for rid, m in manual.items():
        if m.get("categoria") and m["categoria"] not in ids_cat:
            avisos.append(f"classificacao-manual.csv: categoria desconhecida '{m['categoria']}' (id {rid})")
    ids_rtm = {i["id"] for i in saida}
    orfaos = [rid for rid in manual if rid not in ids_rtm]
    if orfaos:
        avisos.append(f"classificacao-manual.csv: {len(orfaos)} id(s) não encontrados na RTM (ex.: {orfaos[:3]})")

    rtm = {"total": len(saida), "fontes": sorted(fontes), "avisos": avisos, "requisitos": saida,
           "resumo": resumo(saida, (cfg.get("pesos") or {}).get("naturezas"))}
    projeto.criar_pastas()
    util.gravar_json(projeto.dir_projeto / "rtm.json", rtm)
    colunas = ["id", "id_origem", "fonte", "arquivo", "localizacao", "secao", "bloco", "categoria",
               "confianca_classificacao", "origem_classificacao", "natureza", "obrigatoriedade", "tipo_origem", "texto"]
    util.gravar_csv(projeto.dir_projeto / "rtm.csv", saida, colunas)
    consideradas = set((cfg.get("pesos") or {}).get("naturezas") or [])
    pend = [i for i in saida if i["natureza"] in consideradas and
            (i["categoria"] == NAO_CLASSIFICADO or i["confianca_classificacao"] < 0.4)]
    util.gravar_csv(projeto.dir_analise / "pendencias-classificacao.csv", pend,
                    ["id", "categoria", "confianca_classificacao", "natureza", "obrigatoriedade", "bloco", "texto"])
    return rtm


def resumo(reqs: list, naturezas_consideradas=None) -> dict:
    consideradas = set(naturezas_consideradas or [])
    relevantes = [r for r in reqs if r["natureza"] in consideradas]
    return {
        "por_categoria": dict(sorted(Counter(r["categoria"] for r in reqs).items())),
        "por_natureza": dict(sorted(Counter(r["natureza"] for r in reqs).items())),
        "por_obrigatoriedade": dict(sorted(Counter(r["obrigatoriedade"] for r in reqs).items())),
        "por_fonte": dict(sorted(Counter(r["fonte"] for r in reqs).items())),
        "nao_classificados": sum(1 for r in reqs if r["categoria"] == NAO_CLASSIFICADO),
        "relevantes_para_pesos": len(relevantes),
        "nao_classificados_relevantes": sum(1 for r in relevantes if r["categoria"] == NAO_CLASSIFICADO),
    }
