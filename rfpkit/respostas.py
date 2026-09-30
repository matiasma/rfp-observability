"""Modo proponente: respostas requisito a requisito, cobertura, preenchimento da matriz oficial do cliente
(resposta + observação com justificativa e referências), extensão de dropdowns e verificação pós-gravação."""
import re
import warnings
import zipfile
from collections import Counter, defaultdict
from urllib.parse import urlparse

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from . import planilhas, util
from .kb import KB
from .relatorios import _larguras, _tabela

CORES = {"pleno": "C6EFCE", "parcial": "FFF2CC", "nao": "F8CBAD", "na": "EDEDED"}
CAMPOS_RESPOSTA = ("resposta", "justificativa", "evidencias", "metodo", "poc", "paginas")
MARKETING = re.compile(r"\b(melhor do mercado|lider de mercado|lider absoluto|unica do mercado|revolucion\w*|"
                       r"incompar\w*|best[- ]in[- ]class|world[- ]class|diferencial competitivo)\b")
PREVIEW = re.compile(r"\b(preview|versao previa|beta|early access|acesso antecipado|private preview)\b")
PLACEHOLDER = re.compile(r"^(selecione|escolha|select|choose|-+|\.+)\b")
PLENO = ("plenamente", "totalmente", "integralmente", "nativamente")
PARCIAL = ("parcial", "extensao", "desenvolver", "customiz", "roadmap")


def escala_do_item(projeto, item: dict) -> list:
    return list(item.get("escala_resposta") or item.get("escala") or projeto.cfg["respostas"]["escala"])


def _classe(nv: str):
    if not nv or PLACEHOLDER.match(nv):
        return ""
    if "nao se aplica" in nv or "nao aplicavel" in nv or nv in ("n/a", "na", "nsa"):
        return "na"
    if nv.startswith("nao") or "nao atend" in nv or "nao fornec" in nv:
        return "nao"
    if any(p in nv for p in PARCIAL):
        return "parcial"
    if any(p in nv for p in PLENO) or nv in ("sim", "atende", "atendido", "yes"):
        return "pleno"
    return None


def nivel(valor: str, escala: list) -> str:
    """pleno | parcial | nao | na ('' se vazio/placeholder). Termos explícitos decidem ("Atende Totalmente" = pleno,
    "Não Aplicável" = na); sem termo explícito, o primeiro valor positivo da escala é o pleno — vale para escalas
    em ordem crescente e para listas que começam com "Selecione"."""
    nv = util.norm(valor)
    classe = _classe(nv)
    if classe is not None:
        return classe
    pleno = next((e for e in escala or [] if _classe(util.norm(e)) in (None, "pleno")), None)
    return "pleno" if pleno and util.norm(pleno) == nv else "parcial"


def preparar(projeto) -> dict:
    """Cria ou sincroniza 02-analise/respostas.json com a RTM. Uma resposta só é mantida no mesmo id se o texto do
    requisito for o mesmo; se o edital mudou (errata que desloca linhas), ela segue o texto para o novo id ou vira
    órfã para revisão — nunca é colada em outro requisito."""
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json")
    if not rtm:
        raise RuntimeError("rtm.json não encontrado — rode 'python kit.py rtm' antes.")
    destino = projeto.dir_analise / "respostas.json"
    criado = not destino.exists()
    anteriores = [r for r in util.ler_json(destino, []) or [] if isinstance(r, dict)]
    por_id = {r.get("id"): r for r in anteriores if not r.get("_orfa")}
    por_texto = defaultdict(list)
    for r in anteriores:
        if r.get("resposta") and r.get("requisito"):
            por_texto[util.norm(r["requisito"])].append(r)
    usados, itens, novos, movidas = set(), [], 0, 0
    for req in rtm["requisitos"]:
        item = {"id": req["id"], "requisito": req["texto"], "categoria": req["categoria"],
                "obrigatoriedade": req["obrigatoriedade"], "natureza": req["natureza"], "fonte": req["fonte"],
                "localizacao": req["localizacao"], "escala": escala_do_item(projeto, req)}
        atual = por_id.get(req["id"])
        if atual and (not atual.get("requisito") or util.norm(atual["requisito"]) == util.norm(req["texto"])):
            origem = atual
        else:
            candidatos = [c for c in por_texto.get(util.norm(req["texto"]), []) if id(c) not in usados]
            origem = candidatos[0] if len(candidatos) == 1 else None
            movidas += 1 if origem else 0
        if origem:
            usados.add(id(origem))
            item.update({k: origem.get(k) for k in CAMPOS_RESPOSTA if k in origem})
        else:
            item.update({"resposta": "", "justificativa": "", "evidencias": [], "metodo": "Nativo", "poc": False,
                         "paginas": ""})
            novos += 1
        itens.append(item)
    orfas = [dict(r, _orfa=True) for r in anteriores if r.get("resposta") and id(r) not in usados]
    util.gravar_json(destino, itens + orfas)
    if movidas or orfas:
        print(f"AVISO: {movidas} resposta(s) acompanharam o texto do requisito para outro id; {len(orfas)} órfã(s) "
              "sem requisito correspondente (marcadas com _orfa no respostas.json) — revise antes de exportar")
    return {"caminho": destino, "criado": criado, "novos": novos, "orfas": len(orfas), "movidas": movidas,
            "respondidos": sum(1 for i in itens if i.get("resposta"))}


def urls_das_evidencias(item: dict, kb: KB) -> list:
    urls = []
    for ev in item.get("evidencias") or []:
        e = kb.evidencia(ev)
        if e:
            urls.append(e["url"])
        elif str(ev).startswith("http"):
            urls.append(str(ev).strip())
    return list(dict.fromkeys(urls))


def texto_observacao(item: dict, kb: KB, opcoes: dict | None = None) -> str:
    """Justificativa + [Método] (se não nativo) + [Comprovação em POC] + 'Ref.: url; url'."""
    op = {"metodo": True, "poc": True, "referencias": True, "prefixo_referencias": "Ref.:", **(opcoes or {})}
    partes = [str(item.get("justificativa") or "").strip()]
    metodo = str(item.get("metodo") or "").strip()
    if op["metodo"] and metodo and util.norm(metodo) != "nativo":
        partes.append(f"[Método: {metodo}.]")
    if op["poc"] and item.get("poc"):
        partes.append("[Comprovação em POC.]")
    urls = urls_das_evidencias(item, kb)
    if op["referencias"] and urls:
        partes.append(f"{op['prefixo_referencias']} " + "; ".join(urls))
    return " ".join(p for p in partes if p)


def validar_respostas(projeto, kb: KB | None = None) -> list:
    """[(nível, mensagem)] — escala, justificativa, evidências e pente-fino automático."""
    kb = kb or KB()
    rtm_ids = {r["id"] for r in (util.ler_json(projeto.dir_projeto / "rtm.json") or {}).get("requisitos", [])}
    prob = []
    for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
        if not r.get("resposta"):
            continue
        rid = r.get("id")
        if r.get("_orfa") or (rtm_ids and rid not in rtm_ids):
            prob.append(("ERRO", f"{rid}: resposta sem requisito correspondente na RTM (órfã)"))
            continue
        escala = r.get("escala") or projeto.cfg["respostas"]["escala"]
        if planilhas.normalizar_na_escala(r["resposta"], escala) is None:
            prob.append(("ERRO", f"{rid}: resposta '{r['resposta']}' fora da escala {escala}"))
            continue
        nv = nivel(r["resposta"], escala)
        just = util.norm(r.get("justificativa"))
        if nv != "pleno" and not just:
            prob.append(("ERRO", f"{rid}: '{r['resposta']}' sem justificativa"))
        for ev in r.get("evidencias") or []:
            if re.match(r"^EV-", str(ev)):
                e = kb.evidencia(ev)
                if not e:
                    prob.append(("ERRO", f"{rid}: evidência {ev} não existe em kb/evidencias"))
                elif nv == "pleno" and e.get("ga") is False:
                    prob.append(("AVISO", f"{rid}: 'Atende' sustentado por {ev}, que não é GA"))
                elif kb.status_evidencia(e, projeto.data_ref) in ("QUEBRADA", "VENCIDA", "A_VALIDAR"):
                    prob.append(("AVISO", f"{rid}: evidência {ev} com status "
                                          f"{kb.status_evidencia(e, projeto.data_ref)} — revalidar"))
            elif not str(ev).startswith("http"):
                prob.append(("ERRO", f"{rid}: evidência '{ev}' não é id EV nem URL"))
        if nv in ("pleno", "parcial") and not urls_das_evidencias(r, kb):
            prob.append(("AVISO", f"{rid}: '{r['resposta']}' sem evidência (pente-fino)"))
        if MARKETING.search(just):
            prob.append(("AVISO", f"{rid}: linguagem de marketing na justificativa (pente-fino)"))
        if nv == "pleno" and PREVIEW.search(just):
            prob.append(("AVISO", f"{rid}: justificativa cita preview/beta em resposta plena (GA apenas)"))
    pf = pente_fino(projeto, kb)
    params = pf["parametros"]
    for flag, texto in (("justificativa_curta", f"justificativa curta (< {params['justificativa_min']} caracteres)"),
                        ("url_generica", "evidência em URL genérica (página de visão geral/landing)")):
        if pf["resumo"].get(flag):
            prob.append(("AVISO", f"pente-fino: {pf['resumo'][flag]} resposta(s) com {texto} — ver "
                                  "02-analise/pente-fino-automatico.md"))
    return prob


def url_generica(url: str) -> bool:
    """Página de visão geral/landing/hub: sustenta mal uma afirmação específica."""
    u = urlparse(str(url))
    partes = [s for s in u.path.split("/") if s and not re.fullmatch(r"[a-z]{2}(-[a-z]{2,4})?", s.lower())]
    if len(partes) <= 1:
        return True
    if partes[-1].lower().split(".")[0] in ("overview", "index", "introduction", "intro", "home", "docs", "welcome"):
        return True
    if len(partes) <= 2 and (u.path.endswith("/") or partes[0].lower() in
                             ("products", "product", "solutions", "platform", "pricing", "features")):
        return True
    return False


def pente_fino(projeto, kb: KB | None = None) -> dict:
    """Pente-fino automático das respostas (sinais para revisão humana, não erros): sem evidência, URL genérica,
    reuso alto da mesma URL, justificativa curta, marketing, preview em resposta plena, evidência não validada."""
    kb = kb or KB()
    cfg = {"justificativa_min": 90, "reuso_url": 5, **(projeto.cfg["respostas"].get("pente_fino") or {})}
    minimo, limiar = int(cfg["justificativa_min"]), int(cfg["reuso_url"])
    itens = [r for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []
             if r.get("resposta") and not r.get("_orfa")]
    uso = Counter(u for r in itens for u in urls_das_evidencias(r, kb))
    resumo = Counter()
    sinalizados = []
    for r in itens:
        escala = r.get("escala") or projeto.cfg["respostas"]["escala"]
        nv = nivel(r["resposta"], escala)
        urls = urls_das_evidencias(r, kb)
        just = str(r.get("justificativa") or "").strip()
        flags = []
        if nv in ("pleno", "parcial") and not urls:
            flags.append("sem_evidencia")
        if any(url_generica(u) for u in urls):
            flags.append("url_generica")
        reuso = max((uso[u] for u in urls), default=0)
        if reuso >= limiar:
            flags.append(f"reuso_url={reuso}")
        if nv in ("pleno", "parcial") and len(just) < minimo:
            flags.append("justificativa_curta")
        if MARKETING.search(util.norm(just)):
            flags.append("marketing")
        if nv == "pleno" and PREVIEW.search(util.norm(just)):
            flags.append("preview")
        evs = [kb.evidencia(e) for e in r.get("evidencias") or [] if kb.evidencia(e)]
        if any(kb.status_evidencia(e, projeto.data_ref) != "VALIDADA" for e in evs):
            flags.append("evidencia_nao_validada")
        if nv == "pleno" and any(e.get("ga") is False for e in evs):
            flags.append("nao_ga")
        for f in flags:
            resumo[f.split("=")[0]] += 1
        if flags:
            sinalizados.append({"id": r["id"], "resposta": r["resposta"], "nivel": nv, "flags": flags,
                                "just_len": len(just), "n_ev": len(r.get("evidencias") or []), "urls": urls})
    return {"parametros": {"justificativa_min": minimo, "reuso_url": limiar},
            "resumo": {"total_itens": len(itens), "sinalizados": len(sinalizados), **dict(resumo)},
            "top_urls_reuso": [[u, n] for u, n in uso.most_common(10)],
            "itens_sinalizados": sinalizados}


LEGENDA_PENTE_FINO = {
    "sem_evidencia": "resposta positiva/parcial sem URL oficial",
    "url_generica": "evidência é página de visão geral/landing — prefira a página que sustenta a afirmação",
    "reuso_url": "a mesma URL sustenta muitos itens — confira se ela cobre cada um",
    "justificativa_curta": "justificativa curta para uma resposta positiva/parcial",
    "marketing": "linguagem de marketing (use fatos verificáveis)",
    "preview": "cita preview/beta em resposta plena (só GA)",
    "evidencia_nao_validada": "evidência da KB vencida, a validar ou quebrada",
    "nao_ga": "resposta plena sustentada por evidência não GA",
}


def gravar_pente_fino(projeto, pf: dict) -> list:
    util.gravar_json(projeto.dir_analise / "pente-fino-automatico.json", pf)
    res, par = pf["resumo"], pf["parametros"]
    linhas = ["# Pente-fino automático das respostas", "",
              f"{res['sinalizados']} de {res['total_itens']} resposta(s) com algum sinal para revisão humana "
              f"(justificativa mínima: {par['justificativa_min']} caracteres; reuso alto: ≥ {par['reuso_url']} itens "
              "por URL). Sinais não são erros: cada um pede uma checagem.", "",
              "| Sinal | Itens | O que conferir |", "|---|--:|---|"]
    linhas += [f"| {k} | {res.get(k, 0)} | {v} |" for k, v in LEGENDA_PENTE_FINO.items()]
    if pf["top_urls_reuso"]:
        linhas += ["", "## URLs mais reutilizadas", "", "| URL | Itens |", "|---|--:|"]
        linhas += [f"| {u} | {n} |" for u, n in pf["top_urls_reuso"]]
    if pf["itens_sinalizados"]:
        linhas += ["", "## Itens sinalizados", "", "| ID | Resposta | Sinais | Justificativa (caracteres) | URLs |",
                   "|---|---|---|--:|---|"]
        linhas += [f"| {i['id']} | {i['resposta']} | {', '.join(i['flags'])} | {i['just_len']} | "
                   f"{'<br>'.join(i['urls']) or '—'} |" for i in pf["itens_sinalizados"]]
    destino = projeto.dir_analise / "pente-fino-automatico.md"
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return [projeto.dir_analise / "pente-fino-automatico.json", destino]


def cobertura(projeto) -> dict:
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json") or {"requisitos": []}
    respostas = {r["id"]: r for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []
                 if r.get("resposta") and not r.get("_orfa")}
    por_resposta, negativos, grupos = Counter(), [], {}
    for req in rtm["requisitos"]:
        r = respostas.get(req["id"])
        if not r:
            continue
        escala = list(r.get("escala") or projeto.cfg["respostas"]["escala"])
        valor = planilhas.normalizar_na_escala(r["resposta"], escala) or r["resposta"]
        por_resposta[valor] += 1
        g = grupos.setdefault(tuple(escala), {"escala": escala, "matriz": defaultdict(Counter), "respondidos": 0,
                                              "abas": set()})
        g["matriz"][req["obrigatoriedade"]][valor] += 1
        g["respondidos"] += 1
        g["abas"].add(req["secao"] or req["fonte"])
        if req["obrigatoriedade"] == "eliminatorio" and nivel(valor, escala) in ("nao", "parcial"):
            negativos.append({"id": req["id"], "resposta": valor, "requisito": req["texto"]})
    tabelas = []
    for g in grupos.values():
        linhas = [[ob] + [g["matriz"][ob].get(e, 0) for e in g["escala"]]
                  for ob in ("eliminatorio", "obrigatorio", "desejavel") if ob in g["matriz"]]
        tabelas.append({"escala": g["escala"], "linhas": linhas, "respondidos": g["respondidos"],
                        "abas": ", ".join(sorted(g["abas"]))})
    return {"total": len(rtm["requisitos"]), "respondidos": len(respostas), "por_resposta": dict(por_resposta),
            "tabelas": tabelas, "eliminatorios_em_risco": negativos}


def gravar_cobertura(projeto, cob: dict):
    linhas = ["# Cobertura das respostas", "", f"{cob['respondidos']} de {cob['total']} requisitos respondidos."]
    for t in cob["tabelas"]:
        linhas += ["", f"**{t['abas']}** — {t['respondidos']} resposta(s)", "",
                   "| Obrigatoriedade | " + " | ".join(t["escala"]) + " |", "|---|" + ":--:|" * len(t["escala"])]
        linhas += ["| " + " | ".join(str(v) for v in l) + " |" for l in t["linhas"]]
    if cob["eliminatorios_em_risco"]:
        linhas += ["", "## Eliminatórios com resposta parcial ou negativa", ""]
        linhas += [f"- **{n['id']}** — {n['resposta']}: {n['requisito']}" for n in cob["eliminatorios_em_risco"]]
    (projeto.dir_analise / "cobertura-respostas.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def exportar(projeto, kb: KB | None = None) -> list:
    kb = kb or KB()
    cfg = projeto.cfg
    proponente = kb.nome(cfg.get("proponente") or "")
    rtm = {r["id"]: r for r in util.ler_json(projeto.dir_projeto / "rtm.json")["requisitos"]}
    respostas = []
    for r in util.ler_json(projeto.dir_analise / "respostas.json", []) or []:
        if not r.get("resposta") or r.get("_orfa") or r["id"] not in rtm:
            continue
        exato = planilhas.normalizar_na_escala(r["resposta"], r.get("escala") or cfg["respostas"]["escala"])
        if exato is None:
            print(f"AVISO: {r['id']} ignorado — resposta fora da escala")
            continue
        respostas.append({**r, "resposta": exato})
    if not respostas:
        raise RuntimeError("02-analise/respostas.json sem respostas preenchidas (ver prompts/09-respostas-matriz.md).")
    opcoes = cfg["respostas"].get("observacao") or {}
    saidas = []

    wb = Workbook()
    ws = wb.active
    ws.title = "Respostas"
    linhas = []
    for r in respostas:
        base = rtm[r["id"]]
        linhas.append([r["id"], base["fonte"], base["localizacao"], base["categoria"], base["obrigatoriedade"],
                       base["texto"], r["resposta"], r.get("justificativa", ""), r.get("metodo", ""),
                       "Sim" if r.get("poc") else "", ", ".join(map(str, r.get("evidencias") or [])),
                       "\n".join(urls_das_evidencias(r, kb)), r.get("paginas", "")])
    fim = _tabela(ws, 1, ["ID", "Fonte", "Localização", "Categoria", "Obrigatoriedade", "Requisito",
                          f"Resposta ({proponente})", "Justificativa", "Método", "POC", "Evidências", "URLs",
                          "Páginas"], linhas, [12, 16, 14, 18, 13, 60, 18, 60, 12, 6, 16, 50, 10], quebra=(6, 8, 12))
    for i, r in enumerate(respostas, start=2):
        ws.cell(row=i, column=7).fill = PatternFill("solid", fgColor=CORES.get(nivel(r["resposta"], r.get("escala")), "FFFFFF"))
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = f"A1:M{fim}"

    cob = cobertura(projeto)
    gravar_cobertura(projeto, cob)
    ws2 = wb.create_sheet("Resumo")
    ws2["A1"] = f"Cobertura: {cob['respondidos']} de {cob['total']} requisitos respondidos"
    ws2["A1"].font = Font(bold=True, size=12)
    fim = 1
    for t in cob["tabelas"]:
        ws2.cell(row=fim + 2, column=1, value=t["abas"]).font = Font(bold=True)
        fim = _tabela(ws2, fim + 3, ["Obrigatoriedade"] + t["escala"], t["linhas"])
    ws2.cell(row=fim + 2, column=1, value="Eliminatórios com resposta parcial ou negativa").font = Font(bold=True)
    _tabela(ws2, fim + 3, ["ID", "Resposta", "Requisito"],
            [[n["id"], n["resposta"], n["requisito"]] for n in cob["eliminatorios_em_risco"]], quebra=(3,))
    _larguras(ws2, [22] + [18] * max([len(t["escala"]) for t in cob["tabelas"]] or [1]))

    ws3 = wb.create_sheet("Evidências")
    usadas = sorted({str(ev) for r in respostas for ev in r.get("evidencias") or [] if kb.evidencia(ev)})
    _tabela(ws3, 1, ["ID", "Capacidade", "URL", "Status", "Verificado em"],
            [[e, kb.evidencia(e)["capacidade"], kb.evidencia(e)["url"],
              kb.status_evidencia(kb.evidencia(e), projeto.data_ref), str(kb.evidencia(e).get("verificado_em") or "")]
             for e in usadas], [12, 60, 70, 12, 13], quebra=(2, 3))
    pf = pente_fino(projeto, kb)
    ws4 = wb.create_sheet("Pente-fino")
    _tabela(ws4, 1, ["ID", "Resposta", "Sinais", "Justificativa (caracteres)", "URLs"],
            [[i["id"], i["resposta"], ", ".join(i["flags"]), i["just_len"], "\n".join(i["urls"])]
             for i in pf["itens_sinalizados"]], [12, 22, 40, 14, 70], quebra=(3, 5))
    destino = projeto.entregavel("matriz-respostas", "xlsx")
    wb.save(destino)
    saidas.append(destino)
    saidas += gravar_pente_fino(projeto, pf)

    saidas += preencher_matrizes(projeto, kb, respostas, rtm, proponente, opcoes)
    return saidas


def preencher_matrizes(projeto, kb, respostas, rtm, proponente, opcoes) -> list:
    """Grava as respostas numa CÓPIA da planilha do edital, alterando só as células respondidas (gravação cirúrgica),
    e confere a cópia: valores, dropdown (cobertura e pertencimento à lista) e integridade do restante do pacote."""
    por_arquivo = defaultdict(list)
    for r in respostas:
        base = rtm[r["id"]]
        if base.get("celula_resposta"):
            por_arquivo[base.get("arquivo") or base["fonte"]].append((base, r))
    saidas, verificacao = [], ["# Verificação das planilhas respondidas", ""]
    for arquivo, itens in por_arquivo.items():
        origem = projeto.pasta_cliente / arquivo
        if not origem.exists():
            print(f"AVISO: planilha do edital não encontrada para preencher: {origem}")
            continue
        alvo = projeto.dir_entregas / f"{origem.stem} - RESPONDIDA {util.nome_arquivo_seguro(proponente)}{origem.suffix}"
        valores, respostas_por_aba = defaultdict(dict), defaultdict(list)
        for base, r in itens:
            aba, cel = base["celula_resposta"].rsplit("!", 1)
            valores[aba][cel] = r["resposta"]
            respostas_por_aba[aba].append(cel)
            if base.get("celula_justificativa"):
                aba_j, cel_j = base["celula_justificativa"].rsplit("!", 1)
                texto = texto_observacao(r, kb, opcoes)
                if texto:
                    valores[aba_j][cel_j] = texto
            if base.get("celula_paginas") and r.get("paginas"):
                aba_p, cel_p = base["celula_paginas"].rsplit("!", 1)
                valores[aba_p][cel_p] = str(r["paginas"])
        info = planilhas.gravar_celulas(origem, alvo, dict(valores), dict(respostas_por_aba))
        saidas.append(alvo)
        verificacao += [f"## {alvo.name}"] + conferir_copia(origem, alvo, info) + [""]
    if len(verificacao) > 2:
        (projeto.dir_analise / "verificacao-planilhas.md").write_text("\n".join(verificacao), encoding="utf-8")
    return saidas


def conferir_copia(origem, alvo, info: dict) -> list:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = load_workbook(str(alvo), keep_vba=str(alvo).lower().endswith(".xlsm"))
    divergentes = [f"{a}!{c}" for a, cels in info.get("gravadas", {}).items() for c, v in cels.items()
                   if str(wb[a][c].value or "") != planilhas._limpar(v or "")]
    dvs = planilhas.validacoes(alvo)
    fora_dropdown, fora_lista, sem_lista = [], [], set()
    for aba, coords in info.get("respostas", {}).items():
        for c in coords:
            dv = planilhas.dv_da_celula(dvs.get(aba, []), c)
            if dv is None:
                sem_lista.add(aba)
                continue
            if not planilhas._cobre(dv["sqref"], c):
                fora_dropdown.append(f"{aba}!{c}")
            lista = planilhas.valores_da_lista(wb, wb[aba], dv["formula1"])
            if lista and str(wb[aba][c].value or "") not in lista:
                fora_lista.append(f"{aba}!{c}")
    diferencas = planilhas.comparar_pacotes(origem, alvo, info["partes_alteradas"])
    with zipfile.ZipFile(origem) as z:
        total = len(z.namelist())
    linhas = [f"- células gravadas: {info['escritas']} · divergentes: {len(divergentes)}"
              + (f" {divergentes[:5]}" if divergentes else ""),
              f"- dropdown: {info['estendidas']} célula(s) incluída(s); fora do dropdown: {len(fora_dropdown)}; "
              f"valor fora da lista: {len(fora_lista)}" + (f" {fora_lista[:5]}" if fora_lista else ""),
              f"- pacote: {total - len(info['partes_alteradas']) - len(diferencas)} de "
              f"{total - len(info['partes_alteradas'])} partes preservadas byte a byte (imagens, formas, validações, "
              f"estilos); alteradas de propósito: {', '.join(info['partes_alteradas'])}"]
    if info["mescladas"]:
        linhas.append(f"- células mescladas gravadas na superior esquerda: {len(info['mescladas'])}")
    if info["conflitos"]:
        linhas.append(f"- CONFLITOS (mesma célula mesclada com respostas diferentes): {info['conflitos']}")
    if sem_lista:
        linhas.append(f"- abas sem dropdown na coluna de resposta: {', '.join(sorted(sem_lista))}")
    if divergentes or fora_dropdown or fora_lista or diferencas or info["conflitos"]:
        print(f"AVISO: verificação de {alvo.name}: divergentes={len(divergentes)} fora_dropdown={len(fora_dropdown)} "
              f"fora_lista={len(fora_lista)} partes_diferentes={diferencas[:3]} conflitos={len(info['conflitos'])}")
    return linhas
