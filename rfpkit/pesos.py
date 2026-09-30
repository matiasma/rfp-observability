"""Pesos das categorias = massa de requisitos do edital (ponderada por obrigatoriedade), normalizada para 100."""
from collections import defaultdict

from . import util
from .kb import KB


def calcular_pesos(projeto, kb: KB | None = None, rtm: dict | None = None) -> dict:
    kb = kb or KB()
    rtm = rtm or util.ler_json(projeto.dir_projeto / "rtm.json")
    if not rtm:
        raise RuntimeError("rtm.json não encontrado — rode 'python kit.py rtm' antes.")
    cfg = projeto.cfg["pesos"]
    mult = cfg.get("multiplicadores") or {}
    naturezas = set(cfg.get("naturezas") or [])
    excluidas = set(cfg.get("categorias_excluidas") or [])
    override = {k: float(v) for k, v in (cfg.get("override") or {}).items()}

    contagem, ponderado = defaultdict(int), defaultdict(float)
    for r in rtm["requisitos"]:
        if r["natureza"] not in naturezas:
            continue
        contagem[r["categoria"]] += 1
        ponderado[r["categoria"]] += float(mult.get(r["obrigatoriedade"], 1.0))

    elegiveis = [c for c in kb.categorias_produto if c["id"] not in excluidas]
    brutos = {c["id"]: ponderado.get(c["id"], 0.0) for c in elegiveis}
    fixos = {k: v for k, v in override.items() if k in brutos}
    restante = max(0.0, 100.0 - sum(fixos.values()))
    soma_livre = sum(v for k, v in brutos.items() if k not in fixos)
    pesos = {}
    for cid, bruto in brutos.items():
        if cid in fixos:
            pesos[cid] = fixos[cid]
        else:
            pesos[cid] = restante * bruto / soma_livre if soma_livre else 0.0
    pesos = _arredondar_para_100(pesos)

    categorias = []
    for c in elegiveis:
        categorias.append({
            "id": c["id"], "nome": c["nome"], "requisitos": contagem.get(c["id"], 0),
            "requisitos_ponderados": round(ponderado.get(c["id"], 0.0), 2), "peso": pesos[c["id"]],
            "fixado": c["id"] in fixos,
        })
    resultado = {
        "criterio": "Peso = soma dos requisitos da categoria (naturezas consideradas) × multiplicador de "
                    "obrigatoriedade, normalizada para 100; categorias com 'override' têm peso fixado.",
        "naturezas_consideradas": sorted(naturezas),
        "multiplicadores": mult,
        "categorias_excluidas": sorted(excluidas),
        "nao_classificados_considerados": contagem.get("nao-classificado", 0),
        "fora_da_aderencia": {k: v for k, v in contagem.items() if k in excluidas},
        "categorias": categorias,
        "soma": round(sum(pesos.values()), 1),
    }
    util.gravar_json(projeto.dir_projeto / "categorias-pesos.json", resultado)
    return resultado


def _arredondar_para_100(pesos: dict) -> dict:
    total = sum(pesos.values())
    if total <= 0:
        return {k: 0.0 for k in pesos}
    arred = {k: round(v * 100.0 / total, 1) for k, v in pesos.items()}
    diferenca = round(100.0 - sum(arred.values()), 1)
    if diferenca and arred:
        maior = max(arred, key=arred.get)
        arred[maior] = round(arred[maior] + diferenca, 1)
    return arred
