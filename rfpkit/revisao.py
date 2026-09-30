"""Revisão de TODOS os requisitos por LLM (execução assistida no VS Code).

O classificador por palavras-chave é só o ponto de partida. A cada execução, a skill do GitHub Copilot divide os
requisitos em lotes (02-analise/revisao/lote-NN.json), subagentes preenchem cada lote seguindo
prompts/14-revisar-requisitos.md, e o kit consolida em 02-analise/revisao-requisitos.json:

- categoria, natureza e obrigatoriedade confirmadas ou corrigidas (aplicadas na RTM; classificacao-manual.csv
  continua prevalecendo);
- entendimento do que o requisito exige, parâmetros citados (volumes, versões, prazos, SLAs) e clareza;
- lacuna: informação do cliente que falta para avaliar com confiança alta — e a pergunta de esclarecimento, que o kit
  transforma em dúvida em 02-analise/duvidas.yaml (anexo de dúvidas) ligada ao requisito.
"""
import re

import yaml

from . import util
from .classificacao import NATUREZAS, NAO_CLASSIFICADO

CAMPOS_LLM = ("categoria", "natureza", "obrigatoriedade", "entendimento", "parametros", "clareza", "lacuna",
              "duvida_sugerida", "duvida", "obs", "revisado")
CAMPOS_KIT = ("revisado_em", "reabrir", "reabrir_por", "respostas_incorporadas", "resposta_cliente", "ids_anteriores")
CLAREZAS = ("clara", "ambigua", "incompleta")
OBRIGATORIEDADES = ("eliminatorio", "obrigatorio", "desejavel")
VAZIO = {"categoria": "", "natureza": "", "obrigatoriedade": "", "entendimento": "", "parametros": "",
         "clareza": "", "lacuna": "", "duvida_sugerida": "", "duvida": "", "obs": "", "revisado": False}


def arquivo(projeto):
    return projeto.dir_analise / "revisao-requisitos.json"


def dir_lotes(projeto):
    return projeto.dir_analise / "revisao"


def carregar(projeto) -> list:
    dados = util.ler_json(arquivo(projeto), []) or []
    return [r for r in dados if isinstance(r, dict)] if isinstance(dados, list) else []


def _mesmo_texto(a, b) -> bool:
    return util.norm(a or "") == util.norm(b or "")


def _mesclar_lotes(projeto, itens: list, problemas: list | None = None) -> tuple[int, int]:
    """Aplica nos itens o que os subagentes preencheram nos lotes (mesmo id e mesmo texto do requisito). Item
    concluído no lote (revisado: true) vale inteiro — inclusive para limpar campos; item parcial só acrescenta o que foi
    preenchido. Lote ilegível é isolado como .invalido e reportado."""
    idx = {i.get("id"): i for i in itens}
    aplicados = ignorados = 0
    for lote in sorted(dir_lotes(projeto).glob("lote-*.json")):
        dados, erro = util.ler_lote(lote)
        if erro:
            if problemas is not None:
                problemas.append(f"{lote.name}: {erro} — isolado como .invalido")
            util.isolar_lote(lote)
            continue
        for r in dados:
            alvo = idx.get(r.get("id"))
            if not alvo or not _mesmo_texto(alvo.get("requisito"), r.get("requisito")):
                ignorados += 1
                continue
            concluido = r.get("revisado") is True
            novos = {k: r[k] for k in CAMPOS_LLM if k in r and (concluido or r[k] != VAZIO.get(k))}
            mudou = any(v != alvo.get(k) for k, v in novos.items())
            alvo.update(novos)
            aplicados += 1 if mudou else 0
    return aplicados, ignorados


def preparar(projeto, tamanho: int = 40) -> dict:
    """Junta o que já foi preenchido nos lotes, sincroniza revisao-requisitos.json com a RTM (a revisão acompanha o
    texto do requisito, como nas respostas), cria as dúvidas sugeridas e gera novos lotes só com os pendentes.
    Nada preenchido se perde: rodar de novo antes de consolidar apenas incorpora os lotes."""
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json")
    if not rtm:
        raise RuntimeError("rtm.json não encontrado — rode 'python kit.py rtm' antes.")
    from .duvidas import ciclo_resposta, ligadas_por_requisito, respondidas
    import datetime as dt
    anteriores = carregar(projeto)
    problemas = []
    aplicados, ignorados = _mesclar_lotes(projeto, anteriores, problemas)
    resp, ligadas, hoje = respondidas(projeto), ligadas_por_requisito(projeto), dt.date.today().isoformat()
    por_id = {r.get("id"): r for r in anteriores}
    exatos = {(r["id"], util.norm(r["texto"])) for r in rtm["requisitos"]}
    por_texto = {}                                   # errata que renumera: a revisão segue o texto (se for único)
    for r in anteriores:
        chave = (r.get("id"), util.norm(r.get("requisito") or ""))
        if chave not in exatos and (r.get("revisado") or r.get("reabrir_por")):
            por_texto.setdefault(chave[1], []).append(r)
    usados = set()
    itens = []
    for req in rtm["requisitos"]:
        item = {"id": req["id"], "requisito": req["texto"], "fonte": req["fonte"], "localizacao": req["localizacao"],
                "bloco": req.get("bloco") or "",
                "automatico": {"categoria": req.get("categoria_auto", req["categoria"]),
                               "natureza": req.get("natureza_auto", req["natureza"]),
                               "obrigatoriedade": req.get("obrigatoriedade_auto", req["obrigatoriedade"]),
                               "confianca": req.get("confianca_classificacao")}}
        ant = por_id.get(req["id"])
        if not (ant and _mesmo_texto(ant.get("requisito"), req["texto"])):
            cand = [c for c in por_texto.get(util.norm(req["texto"]), []) if id(c) not in usados]
            ant = cand[0] if len(cand) == 1 else None
        if ant:
            usados.add(id(ant))
        item.update({k: (ant.get(k, VAZIO[k]) if ant else VAZIO[k]) for k in CAMPOS_LLM})
        item.update({k: ant[k] for k in CAMPOS_KIT if ant and k in ant})
        if ant and ant.get("id") != req["id"]:
            item["ids_anteriores"] = sorted((set(ant.get("ids_anteriores") or []) | {ant.get("id")}) - {req["id"]})
        ciclo_resposta(item, "revisado", "revisado_em", [req["id"], *(item.get("ids_anteriores") or [])],
                       resp, ligadas, hoje)
        itens.append(item)
    novas = criar_duvidas(projeto, itens)
    util.gravar_json(arquivo(projeto), itens)
    pasta = dir_lotes(projeto)
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("lote-*.json"):
        antigo.unlink()
    pendentes = [i for i in itens if not i.get("revisado")]
    tamanho = max(1, int(tamanho))
    lotes = []
    for n, ini in enumerate(range(0, len(pendentes), tamanho), start=1):
        destino = pasta / f"lote-{n:02d}.json"
        util.gravar_json(destino, pendentes[ini:ini + tamanho])
        lotes.append(destino)
    return {"total": len(itens), "revisados": len(itens) - len(pendentes), "pendentes": len(pendentes),
            "lotes": lotes, "aplicados": aplicados, "ignorados": ignorados, "duvidas_criadas": novas,
            "problemas": problemas}


def consolidar(projeto, tamanho: int = 40) -> dict:
    """Incorpora os lotes preenchidos (mesmo que preparar) e devolve também a cobertura."""
    info = preparar(projeto, tamanho)
    return {**info, **cobertura(projeto)}


def _proximo_id(ids: list) -> tuple[str, int, int]:
    """(prefixo, próximo número, largura) seguindo o padrão dos ids existentes (ex.: DUV-007 -> DUV-, 8, 3)."""
    melhor = ("DUV-", 0, 3)
    for i in ids:
        m = re.match(r"^(.*?)(\d+)$", str(i or ""))
        if m and int(m.group(2)) >= melhor[1]:
            melhor = (m.group(1), int(m.group(2)), len(m.group(2)))
    return melhor[0], melhor[1] + 1, melhor[2]


def criar_duvidas(projeto, itens: list, origem: str = "revisao-llm") -> int:
    """Cada 'duvida_sugerida' ainda sem dúvida vira um item em duvidas.yaml (sem duplicar perguntas iguais); a dúvida
    guarda os requisitos ligados, o que fecha o ciclo quando o cliente responder."""
    caminho = projeto.dir_analise / "duvidas.yaml"
    bruto = util.ler_yaml(caminho, []) or []
    existentes = [d for d in bruto if isinstance(d, dict)] if isinstance(bruto, list) else []
    por_texto = {util.norm(d.get("pergunta") or ""): d.get("id") for d in existentes}
    prefixo, numero, largura = _proximo_id([d.get("id") for d in existentes])
    novas = []
    for it in itens:
        sugerida = str(it.get("duvida_sugerida") or "").strip()
        if not sugerida or it.get("duvida"):
            continue
        chave = util.norm(sugerida)
        if chave in por_texto:
            it["duvida"] = por_texto[chave]
            continue
        did = f"{prefixo}{numero:0{largura}d}"
        numero += 1
        auto = it.get("automatico") or {}
        obrig = it.get("obrigatoriedade") or auto.get("obrigatoriedade")
        novas.append({"id": did, "documento": it.get("fonte"),
                      "referencia": " ".join(x for x in (it.get("localizacao"), f"({it['id']})") if x),
                      "tema": it.get("categoria") or auto.get("categoria"), "pergunta": sugerida,
                      "objetivo": f"interno: lacuna em {it['id']} — {it.get('lacuna') or 'informação insuficiente'}",
                      "impacto": "Sem a resposta, a avaliação deste requisito não chega a confiança alta.",
                      "requisitos": [it["id"]], "prioridade": "Alta" if obrig == "eliminatorio" else "Média",
                      "status": "PENDENTE", "enviar": True, "origem": origem})
        por_texto[chave] = did
        it["duvida"] = did
    if novas:
        texto = caminho.read_text(encoding="utf-8") if caminho.exists() else ""
        bloco = yaml.safe_dump(novas, allow_unicode=True, sort_keys=False, width=120)
        linhas = texto.rstrip().splitlines()
        if not existentes and linhas and linhas[-1].strip() == "[]":
            linhas = linhas[:-1]
        caminho.write_text("\n".join(linhas + [bloco.rstrip()]) + "\n", encoding="utf-8")
    return len(novas)


def cobertura(projeto) -> dict:
    rtm = util.ler_json(projeto.dir_projeto / "rtm.json") or {"requisitos": []}
    itens = {i["id"]: i for i in carregar(projeto)}
    revisados = [r["id"] for r in rtm["requisitos"]
                 if (itens.get(r["id"]) or {}).get("revisado") and _mesmo_texto(itens[r["id"]]["requisito"], r["texto"])]
    lacunas = [i for i in itens.values() if i.get("revisado") and str(i.get("lacuna") or "").strip()]
    sem_duvida = [i["id"] for i in lacunas if not i.get("duvida")]
    return {"total": len(rtm["requisitos"]), "revisados": len(revisados),
            "pendentes": len(rtm["requisitos"]) - len(revisados), "com_lacuna": len(lacunas),
            "lacunas_sem_duvida": sem_duvida,
            "ambiguos": sum(1 for i in itens.values() if i.get("revisado") and i.get("clareza") in ("ambigua", "incompleta"))}


def ajustes(projeto) -> dict:
    """{id: (texto, {categoria/natureza/obrigatoriedade corrigidas pela revisão})} para a RTM aplicar."""
    saida = {}
    for i in carregar(projeto):
        if not (i.get("revisado") or i.get("reabrir_por")):   # reaberto por resposta: vale a revisão anterior
            continue
        campos = {k: i[k] for k in ("categoria", "natureza", "obrigatoriedade") if str(i.get(k) or "").strip()}
        if campos:
            saida[i["id"]] = (i.get("requisito") or "", campos)
    return saida


def validar(projeto, kb) -> list:
    ids_cat = {c["id"] for c in kb.categorias} | {NAO_CLASSIFICADO}
    prob = []
    for i in carregar(projeto):
        if not i.get("revisado"):
            continue
        rid = i.get("id")
        if i.get("categoria") and i["categoria"] not in ids_cat:
            prob.append(("ERRO", f"revisão {rid}: categoria '{i['categoria']}' não existe na taxonomia"))
        if i.get("natureza") and i["natureza"] not in NATUREZAS:
            prob.append(("ERRO", f"revisão {rid}: natureza '{i['natureza']}' fora de {'/'.join(NATUREZAS)}"))
        if i.get("obrigatoriedade") and i["obrigatoriedade"] not in OBRIGATORIEDADES:
            prob.append(("ERRO", f"revisão {rid}: obrigatoriedade '{i['obrigatoriedade']}' fora de "
                                 f"{'/'.join(OBRIGATORIEDADES)}"))
        if i.get("clareza") and i["clareza"] not in CLAREZAS:
            prob.append(("AVISO", f"revisão {rid}: clareza '{i['clareza']}' fora de {'/'.join(CLAREZAS)}"))
        if not str(i.get("entendimento") or "").strip():
            prob.append(("AVISO", f"revisão {rid}: revisado sem 'entendimento'"))
        if i.get("clareza") in ("ambigua", "incompleta") and not str(i.get("lacuna") or "").strip():
            prob.append(("AVISO", f"revisão {rid}: requisito {i['clareza']} sem 'lacuna' descrita"))
    return prob
