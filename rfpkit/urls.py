"""Validação das URLs de evidência: HTTP 200 + título + palavras-chave que sustentam a afirmação."""
import datetime as dt
import html as html_lib
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from . import util

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
URL_RE = re.compile(r"https?://[^\s;,)\]\"'<>]+")
BLOQUEIO = (401, 403, 429, 999)


def buscar(url: str, timeout: int = 25) -> dict:
    """GET com User-Agent de navegador. Retorna status, URL final e HTML (até 2 MB)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept-Language": "en-US,en;q=0.8,pt-BR;q=0.6"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.getcode(), "final": r.geturl(), "html": r.read(2_000_000).decode("utf-8", "ignore"),
                    "erro": ""}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final": url, "html": "", "erro": f"HTTP {e.code}"}
    except Exception as e:  # rede, TLS, timeout, URL malformada
        return {"status": 0, "final": url, "html": "", "erro": type(e).__name__}


def _redirecionou(url: str, final: str) -> bool:
    a, b = urlparse(url), urlparse(final or url)
    return a.netloc.lower() != b.netloc.lower() or a.path.rstrip("/").lower() != b.path.rstrip("/").lower()


def conferir_citacoes(texto_pagina: str, citacoes) -> tuple[list, list, list]:
    """(conferidas, ausentes, inverificaveis): a citação vale se TODOS os seus trechos literais aparecem na página;
    citação sem nenhum trecho conferível (muito curta, ex.: "SLA 99.9%") não conta como conferida."""
    pagina = util.norm_literal(texto_pagina)
    conferidas, ausentes, inverificaveis = [], [], []
    for c in citacoes or []:
        trechos = util.trechos_citacao(c)
        if not trechos:
            inverificaveis.append(str(c))
            continue
        (conferidas if all(t in pagina for t in trechos) else ausentes).append(str(c))
    return conferidas, ausentes, inverificaveis


def verificar(url: str, palavras=None, navegador: bool = False, citacoes=None, citacoes_flex=None) -> dict:
    """situacao: OK (200, sem redirecionamento, palavras-chave presentes e citações literais encontradas) |
    CITACAO_AUSENTE (a página está no ar, mas a citação que sustenta a evidência não está mais nela — o conteúdo
    mudou ou a citação não é literal) | REDIRECIONADA (outra página — exige conferência humana) | SEM_PALAVRAS |
    BLOQUEADA (401/403/429: o site recusa robôs; conferir no navegador) | NAVEGADOR (evidência marcada
    'verificacao: navegador': página montada por JavaScript; conferir as citações no navegador do VS Code) |
    QUEBRADA (404/410/5xx/erro de rede). 'citacoes_flex' são citações de um item que cita várias páginas: podem estar
    em qualquer uma delas, então só são registradas (não mudam a situação desta URL)."""
    r = buscar(url)
    html = r["html"]
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    titulo = re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip()[:120] if m else ""
    bruto = html_lib.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)))
    texto = util.norm(bruto)
    palavras = [p for p in (palavras or []) if p]
    achadas = [p for p in palavras if util.norm(p) in texto]
    faltam = [p for p in palavras if p not in achadas]
    conferidas, ausentes, inverif = conferir_citacoes(bruto, citacoes) if r["status"] == 200 else ([], [], [])
    conf_flex, aus_flex, inv_flex = conferir_citacoes(bruto, citacoes_flex) if r["status"] == 200 else ([], [], [])
    redir = r["final"] if r["status"] == 200 and _redirecionou(url, r["final"]) else ""
    if r["status"] in BLOQUEIO:
        situacao = "BLOQUEADA"
    elif r["status"] != 200:
        situacao = "QUEBRADA"
    elif redir:
        situacao = "REDIRECIONADA"
    elif (palavras and not achadas) or ausentes:
        situacao = "NAVEGADOR" if navegador else ("CITACAO_AUSENTE" if ausentes else "SEM_PALAVRAS")
    else:
        situacao = "OK"
    return {"url": url, "status": r["status"], "ok": situacao == "OK", "situacao": situacao,
            "redirecionada_para": redir, "titulo": titulo, "palavras_encontradas": ", ".join(achadas),
            "palavras_faltantes": ", ".join(faltam), "citacoes_conferidas": len(conferidas) + len(conf_flex),
            "citacoes_ausentes": " | ".join(c[:120] for c in ausentes), "_conferidas": conferidas + conf_flex,
            "_ausentes": ausentes + aus_flex, "_inverificaveis": inverif + inv_flex, "erro": r["erro"],
            "verificado_em": dt.date.today().isoformat()}


INCONCLUSIVAS = ("BLOQUEADA", "NAVEGADOR")


def verificar_varias(alvos: dict, paralelo: int = 8) -> list:
    """alvos: {url: {"palavras": [...], "usos": [...], "navegador": bool, "citacoes": [...]}} -> resultados."""
    urls = list(alvos)
    with ThreadPoolExecutor(max_workers=paralelo) as ex:
        resultados = list(ex.map(lambda u: verificar(u, alvos[u].get("palavras"), alvos[u].get("navegador"),
                                                     alvos[u].get("citacoes"), alvos[u].get("citacoes_flex")), urls))
    for res in resultados:
        res["usado_por"] = ", ".join(sorted(set(alvos[res["url"]].get("usos") or [])))
    return resultados


def urls_do_texto(texto: str) -> list:
    return [u.rstrip(".") for u in URL_RE.findall(texto or "")]


def alvos_do_estudo(projeto, kb) -> dict:
    """URLs citadas no estudo: evidências das respostas (ids EV resolvidos + URLs diretas) e cases de referência."""
    alvos = {}

    def add(url, uso, palavras=None, navegador=False, citacoes=None, flex=False):
        a = alvos.setdefault(url, {"palavras": [], "usos": [], "citacoes": [], "citacoes_flex": []})
        a["usos"].append(uso)
        a["navegador"] = a.get("navegador") or bool(navegador)
        for p in palavras or []:
            if p not in a["palavras"]:
                a["palavras"].append(p)
        destino = a["citacoes_flex"] if flex else a["citacoes"]
        for c in citacoes or []:
            if c and c not in destino:
                destino.append(c)

    def add_ev(ev_id, uso):
        item = kb.evidencia(ev_id)
        if item:
            add(item["url"], uso, item.get("palavras_chave"), item.get("verificacao") == "navegador",
                citacoes_da_evidencia(item))
        return item

    for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
        if not r.get("resposta"):
            continue
        for ev in r.get("evidencias") or []:
            item = add_ev(ev, f"{r['id']} ({ev})")
            if not item:
                for u in urls_do_texto(str(ev)):
                    add(u, r["id"])
        for u in urls_do_texto(r.get("justificativa", "")):
            add(u, r["id"])
    for c in util.ler_yaml(projeto.dir_analise / "cases-referencia.yaml", []) or []:
        if not isinstance(c, dict):   # entradas malformadas são apontadas por 'validar'
            continue
        ref = kb.referencia(c.get("kb")) if c.get("kb") else None
        nome = c.get("organizacao") or (ref or {}).get("organizacao") or c.get("kb") or ""
        for u in urls_do_texto(str(c.get("url") or (ref or {}).get("url") or ""))[:1]:
            add(u, f"case: {nome}".strip(), c.get("palavras_chave") or (ref or {}).get("palavras_chave"),
                (c.get("verificacao") or (ref or {}).get("verificacao")) == "navegador")
    for e in util.ler_yaml(projeto.dir_analise / "registro-evidencias.yaml", []) or []:
        if not isinstance(e, dict):
            continue
        item = kb.evidencia(e.get("kb")) if e.get("kb") else None
        cit = e.get("citacoes") if isinstance(e.get("citacoes"), list) else ([e["citacoes"]] if e.get("citacoes") else [])
        fontes = urls_do_texto(str(e.get("fonte") or "")) or ([item["url"]] if item else [])
        for u in fontes:
            add(u, f"registro {e.get('id')}", e.get("palavras_chave") or (item or {}).get("palavras_chave"),
                (e.get("verificacao") or (item or {}).get("verificacao")) == "navegador",
                cit or (citacoes_da_evidencia(item) if item and u == item["url"] else []), flex=bool(cit) and len(fontes) > 1)
    from .esforco_custo import urls_de_preco
    for u, uso in urls_de_preco(projeto):
        for url in urls_do_texto(u)[:1]:
            add(url, uso)
    from .investigacao import avaliacoes
    for a in avaliacoes(projeto):
        uso = f"{a['id']} × {a['fornecedor']}"
        evs = a.get("evidencias") if isinstance(a.get("evidencias"), list) else []
        diretas = [u for ev in evs if not kb.evidencia(ev) for u in urls_do_texto(str(ev))[:1]]
        cit = [c for c in (a.get("citacoes") if isinstance(a.get("citacoes"), list) else []) if isinstance(c, str)]
        for ev in evs:
            add_ev(ev, uso)
        for u in diretas:          # várias páginas: a citação pode estar em qualquer uma (conferida item a item)
            add(u, uso, citacoes=cit, flex=len(diretas) > 1)
    return alvos


def citacoes_da_evidencia(ev: dict) -> list:
    cit = ev.get("citacoes") if isinstance(ev.get("citacoes"), list) else []
    if not cit and ev.get("citacao"):
        cit = [ev["citacao"]]
    return [c for c in cit if c]


def alvos_da_kb(kb, fornecedor=None) -> dict:
    """Evidências e cases da KB (com palavras-chave) e fontes dos fatos das fichas."""
    alvos = {}
    for colecoes, chave in ((kb.bibliotecas, "evidencias"), (kb.cases, "referencias")):
        for fid, bib in colecoes.items():
            if fornecedor and fid != fornecedor:
                continue
            for ev in bib.get(chave) or []:
                a = alvos.setdefault(ev["url"], {"palavras": [], "usos": [], "citacoes": []})
                a["usos"].append(ev["id"])
                a["navegador"] = a.get("navegador") or ev.get("verificacao") == "navegador"
                a["palavras"] += [p for p in ev.get("palavras_chave") or [] if p not in a["palavras"]]
                if chave == "evidencias":
                    a["citacoes"] += [c for c in citacoes_da_evidencia(ev) if c not in a["citacoes"]]
    for fid, forn in kb.fornecedores.items():
        if fornecedor and fid != fornecedor:
            continue
        for nome, f in (forn.get("fatos") or {}).items():
            for u in urls_do_texto(str((f or {}).get("fonte") or "")):
                alvos.setdefault(u, {"palavras": [], "usos": []})["usos"].append(f"{fid}:{nome}")
    return alvos


COLUNAS = ["ok", "situacao", "status", "url", "redirecionada_para", "titulo", "palavras_encontradas",
           "palavras_faltantes", "citacoes_conferidas", "citacoes_ausentes", "erro", "usado_por", "verificado_em"]


def atualizar_bibliotecas(kb, resultados: list) -> int:
    """Grava status/verificado_em nas bibliotecas de evidências e de cases: VALIDADA (e citacao_conferida_em quando
    as citações literais da evidência estão na página), QUEBRADA, ou A_VALIDAR com 'mudanca_detectada' quando a
    página redireciona, perdeu as palavras-chave ou não contém mais a citação. Preserva o cabeçalho do arquivo."""
    por_url = {r["url"]: r for r in resultados}
    hoje = dt.date.today().isoformat()
    alteradas = 0
    for colecoes, chave in ((kb.bibliotecas, "evidencias"), (kb.cases, "referencias")):
        for bib in colecoes.values():
            mudou = False
            for ev in bib.get(chave) or []:
                r = por_url.get(ev.get("url"))
                if not r or r.get("situacao") in INCONCLUSIVAS:   # inconclusivo: mantém o status atual
                    continue
                situacao = r.get("situacao")
                proprias = citacoes_da_evidencia(ev) if chave == "evidencias" else []
                faltando = [c for c in proprias if c in (r.get("_ausentes") or [])]
                conferidas = [c for c in proprias if c in (r.get("_conferidas") or [])]
                if situacao == "CITACAO_AUSENTE" and not faltando:
                    situacao = "OK"                                   # a citação ausente era de outra evidência
                novo = {"OK": "VALIDADA", "QUEBRADA": "QUEBRADA"}.get(situacao, "A_VALIDAR")
                antes = (ev.get("status"), str(ev.get("verificado_em")), ev.get("citacao_conferida_em"),
                         ev.get("mudanca_detectada"))
                ev["status"] = novo
                if novo == "VALIDADA":
                    ev["verificado_em"] = r["verificado_em"]
                    if conferidas and not faltando:
                        ev["citacao_conferida_em"] = hoje
                    ev.pop("mudanca_detectada", None)
                elif situacao == "CITACAO_AUSENTE":
                    ev["mudanca_detectada"] = f"{hoje}: citação não encontrada na página — {faltando[0][:100]}"
                elif situacao in ("REDIRECIONADA", "SEM_PALAVRAS"):
                    ev["mudanca_detectada"] = f"{hoje}: {situacao.lower()} " + (r.get("redirecionada_para") or "")
                if (ev.get("status"), str(ev.get("verificado_em")), ev.get("citacao_conferida_em"),
                        ev.get("mudanca_detectada")) != antes:
                    mudou, alteradas = True, alteradas + 1
            if mudou:
                caminho = bib["_arquivo"]
                with open(caminho, encoding="utf-8") as f:
                    cabecalho = "".join(l for l in f.readlines() if l.startswith("#"))
                dados = {k: v for k, v in bib.items() if not k.startswith("_")}
                dados["atualizado_em"] = dt.date.today().isoformat()
                import yaml
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(cabecalho + yaml.safe_dump(dados, allow_unicode=True, sort_keys=False, width=140))
    return alteradas


def gravar_relatorio(resultados: list, caminho_csv, caminho_md=None, titulo="Validação de URLs", caminho_json=None):
    util.gravar_csv(caminho_csv, resultados, COLUNAS)
    if caminho_json:              # com as citações completas: a confiança confere cada item/evidência pelas suas citações
        util.gravar_json(caminho_json, [{k: r.get(k) for k in COLUNAS + ["_conferidas", "_ausentes", "_inverificaveis"]}
                                        for r in resultados])
    if caminho_md:
        falhas = [r for r in resultados if not r["ok"]]
        linhas = [f"# {titulo}", "", f"_{len(resultados)} URL(s) verificadas em {dt.date.today()}; "
                                     f"{len(falhas)} a conferir._", "",
                  "| Situação | HTTP | URL | Destino do redirecionamento | Palavras faltantes | Citações conferidas | Citações ausentes | Usado por |",
                  "|---|:--:|---|---|---|:--:|---|---|"]
        for r in sorted(resultados, key=lambda x: (x["ok"], x["url"])):
            ausentes = str(r.get("citacoes_ausentes") or "").replace("|", "/")
            linhas.append(f"| {'✅ ' if r['ok'] else '❌ '}{r.get('situacao', '')} | {r['status'] or r['erro']} | "
                          f"{r['url']} | {r.get('redirecionada_para', '')} | {r['palavras_faltantes']} | "
                          f"{r.get('citacoes_conferidas', '')} | {ausentes} | {r['usado_por']} |")
        caminho_md.write_text("\n".join(linhas) + "\n", encoding="utf-8")
