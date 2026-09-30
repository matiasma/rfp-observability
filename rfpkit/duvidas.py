"""Dúvidas ao cliente: fonte estruturada (02-analise/duvidas.yaml) -> planilha genérica e, se houver,
preenchimento (gravação cirúrgica) de uma cópia do modelo de envio de dúvidas do próprio edital."""
import re
import warnings

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from . import planilhas, util
from .relatorios import _tabela

CAMPOS = ("id", "documento", "referencia", "tema", "pergunta")
GRUPOS = {
    "id": ["identificador", "id", "codigo", "numero", "no", "item"],
    "documento": ["nome anexo", "anexo", "documento", "arquivo", "edital"],
    "referencia": ["pagina", "aba", "clausula", "secao", "referencia", "localizacao", "item do edital"],
    "tema": ["classificacao", "tema", "assunto", "categoria", "topico"],
    "pergunta": ["duvida", "pergunta", "questionamento", "esclarecimento", "questao"],
}
_RE = {g: util.compilar_palavras(ps) for g, ps in GRUPOS.items()}
PRIORIDADE = ("pergunta", "documento", "referencia", "tema", "id")
MARCADORES = re.compile(r"^(preencha|n/?a|exemplo|informe)\b", re.I)


def carregar(projeto) -> list:
    return [d for d in util.ler_yaml(projeto.dir_analise / "duvidas.yaml", []) or [] if isinstance(d, dict)]


STATUS_DUVIDA = ("PENDENTE", "ENVIADA", "RESPONDIDA", "RETIRADA")


def enviavel(d: dict) -> bool:
    """Vai para o cliente: enviar != false e status diferente de RETIRADA."""
    return bool(d.get("enviar", True)) and str(d.get("status") or "").strip().upper() != "RETIRADA"


# ---------------------------------------------------------------- ciclo de respostas do cliente
CAMPOS_CICLO = ("reabrir", "reabrir_por", "respostas_incorporadas", "resposta_cliente")


def id_duvida(valor) -> str:
    """Id de dúvida como texto (7 e "7" são a mesma dúvida); vazio para valores que não são id."""
    if valor is None or isinstance(valor, bool) or not isinstance(valor, (str, int, float)):
        return ""
    return str(valor).strip()


def respondidas(projeto) -> dict:
    """{id: dúvida} das dúvidas que o cliente já respondeu (status RESPONDIDA com resposta_cliente)."""
    return {id_duvida(d.get("id")): d for d in carregar(projeto)
            if id_duvida(d.get("id")) and str(d.get("status") or "").upper() == "RESPONDIDA"
            and str(d.get("resposta_cliente") or "").strip()}


def ligadas_por_requisito(projeto) -> dict:
    """{id do requisito: [ids das dúvidas]} a partir do campo 'requisitos' de cada dúvida."""
    saida = {}
    for d in carregar(projeto):
        did = id_duvida(d.get("id"))
        reqs = d.get("requisitos") if isinstance(d.get("requisitos"), list) else []
        for rid in reqs if did else []:
            saida.setdefault(str(rid).strip(), []).append(did)
    return saida


def ids_de_duvida(valor) -> list:
    """'duvida' pode vir como id ou lista de ids (valores inválidos são ignorados; ids viram texto)."""
    if isinstance(valor, list):
        return [i for i in map(id_duvida, valor) if i]
    i = id_duvida(valor)
    return [i] if i else []


def ciclo_resposta(item: dict, flag: str, campo_data: str, requisito, resp: dict, ligadas: dict,
                   hoje: str) -> bool:
    """Ciclo de esclarecimento de um item de revisão/investigação, por ENTREGA (não por data):
    1. item concluído que recebeu respostas no lote -> as respostas entregues viram 'respostas_incorporadas';
    2. respostas do cliente ligadas ao item e ainda não incorporadas -> vão TODAS para o lote ('resposta_cliente',
       'reabrir_por'); se o item já estava concluído, ele é reaberto (flag False).
    'requisito' é o id atual ou a lista [id atual, ids anteriores] (errata que renumerou o requisito).
    Devolve True quando reabre um item concluído."""
    if item.get(flag) and item.get("reabrir_por"):
        entregues = ids_de_duvida(item["reabrir_por"])
        incorporadas = item.setdefault("respostas_incorporadas", [])
        for did in entregues:
            if did not in incorporadas:
                incorporadas.append(did)
        for k in ("reabrir_por", "reabrir", "resposta_cliente"):
            item.pop(k, None)
        item[campo_data] = hoje
    elif item.get(flag) and not item.get(campo_data):
        item[campo_data] = hoje
    reqs = [requisito] if isinstance(requisito, str) else list(requisito or [])
    ligados = ids_de_duvida(item.get("duvida")) + [d for r in reqs for d in ligadas.get(r, [])]
    incorporadas = ids_de_duvida(item.get("respostas_incorporadas"))
    novas = [d for d in dict.fromkeys(ligados) if d in resp and d not in incorporadas]
    if not novas:
        return False
    reabre = bool(item.get(flag))
    item.update({flag: False, "reabrir_por": novas,
                 "resposta_cliente": " | ".join(f"{d}: {resp[d].get('resposta_cliente')}" for d in novas),
                 "reabrir": f"cliente respondeu {', '.join(novas)} — avaliar com a resposta"})
    return reabre


def validar(projeto) -> list:
    prob, vistos = [], set()
    enviaveis = [d for d in carregar(projeto) if enviavel(d)]
    ids_gates = {g.get("id") for g in projeto.cfg.get("gates") or [] if isinstance(g, dict)}
    for d in carregar(projeto):
        if not str(d.get("pergunta") or "").strip():
            prob.append(("ERRO", f"dúvida {d.get('id')}: sem pergunta"))
        if d.get("id") in vistos:
            prob.append(("ERRO", f"dúvida {d.get('id')}: id repetido"))
        vistos.add(d.get("id"))
        if d.get("status") and str(d["status"]).upper() not in STATUS_DUVIDA:
            prob.append(("AVISO", f"dúvida {d.get('id')}: status '{d['status']}' fora de {'/'.join(STATUS_DUVIDA)}"))
        if str(d.get("status") or "").upper() == "RETIRADA" and d.get("enviar", True):
            prob.append(("AVISO", f"dúvida {d.get('id')}: status RETIRADA — não será enviada (marque enviar: false "
                                  "e registre motivo_retirada)"))
        gates = d.get("gates") or []
        if not isinstance(gates, list) or any(not isinstance(g, str) for g in gates):
            prob.append(("ERRO", f"dúvida {d.get('id')}: 'gates' deve ser lista de ids (ex.: [G1, G2])"))
        elif any(g not in ids_gates for g in gates):
            prob.append(("AVISO", f"dúvida {d.get('id')}: gate(s) {[g for g in gates if g not in ids_gates]} "
                                  "não existem no rfp.yaml"))
        if d.get("status") and str(d["status"]).upper() == "RESPONDIDA" and not d.get("resposta_cliente"):
            prob.append(("AVISO", f"dúvida {d.get('id')}: RESPONDIDA sem 'resposta_cliente'"))
    numeros = [int(m.group(1)) for d in enviaveis if (m := re.search(r"(\d+)$", str(d.get("id") or "")))]
    if numeros and numeros != list(range(numeros[0], numeros[0] + len(numeros))):
        prob.append(("AVISO", "dúvidas enviáveis com numeração não contígua — renumere antes de enviar"))
    return prob


def _grupo(texto: str):
    nt = util.norm(texto)
    if not nt or len(nt) > 60:
        return None
    melhor = None
    for pri, g in enumerate(PRIORIDADE):
        pos = [m.start() for p in _RE[g] for m in [p.search(nt)] if m]
        if pos and (melhor is None or (min(pos), pri) < melhor[0]):
            melhor = ((min(pos), pri), g)
    return melhor[1] if melhor else None


def localizar_modelo(wb):
    """(aba, linha do cabeçalho, {campo: coluna 1-based}) da tabela de dúvidas do modelo do cliente."""
    melhor = None
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        for r in range(1, min(ws.max_row, 30) + 1):
            mapa = {}
            for c in range(1, min(ws.max_column, 30) + 1):
                g = _grupo(str(ws.cell(r, c).value or ""))
                if g and g not in mapa:
                    mapa[g] = c
            if "pergunta" in mapa and len(mapa) >= 2 and (melhor is None or len(mapa) > len(melhor[2])):
                melhor = (ws.title, r, mapa)
    return melhor


def exportar(projeto) -> list:
    enviaveis = [d for d in carregar(projeto) if enviavel(d)]
    if not enviaveis:
        raise RuntimeError("02-analise/duvidas.yaml sem dúvidas enviáveis (ver prompts/05-armadilhas-duvidas.md).")
    saidas = []
    wb = Workbook()
    ws = wb.active
    ws.title = "Dúvidas"
    _tabela(ws, 1, ["ID", "Documento", "Referência", "Tema", "Pergunta"],
            [[d.get(c, "") for c in CAMPOS] for d in enviaveis], [10, 28, 28, 20, 90], quebra=(2, 3, 5))
    destino = projeto.entregavel("duvidas", "xlsx")
    wb.save(destino)
    saidas.append(destino)

    modelo = (projeto.cfg.get("duvidas") or {}).get("modelo")
    if modelo:
        origem = projeto.pasta_cliente / modelo
        if not origem.exists():
            print(f"AVISO: modelo de dúvidas não encontrado: {origem}")
            return saidas
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb2 = load_workbook(str(origem))
        achado = localizar_modelo(wb2)
        if not achado:
            print(f"AVISO: não encontrei a tabela de dúvidas em {origem.name} (coluna 'Dúvida/Pergunta')")
            return saidas
        aba, linha_cab, mapa = achado
        ws2 = wb2[aba]
        valores = {}
        for i, d in enumerate(enviaveis, start=linha_cab + 1):
            for campo, col in mapa.items():
                atual = str(ws2.cell(i, col).value or "")
                if campo == "id" and atual and not MARCADORES.match(atual):
                    continue
                valores[f"{get_column_letter(col)}{i}"] = str(d.get(campo, "") or "")
        for i in range(linha_cab + 1 + len(enviaveis), ws2.max_row + 1):
            for campo, col in mapa.items():
                if campo != "id" and MARCADORES.match(str(ws2.cell(i, col).value or "")):
                    valores[f"{get_column_letter(col)}{i}"] = None
        alvo = projeto.dir_entregas / f"{origem.stem} - PREENCHIDO{origem.suffix}"
        info = planilhas.gravar_celulas(origem, alvo, {aba: valores})
        diferencas = planilhas.comparar_pacotes(origem, alvo, info["partes_alteradas"])
        if diferencas or info["conflitos"]:
            print(f"AVISO: {alvo.name}: partes alteradas sem querer={diferencas[:3]} conflitos={info['conflitos'][:3]}")
        saidas.append(alvo)
    return saidas
