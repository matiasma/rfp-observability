"""Gates (critérios eliminatórios) avaliados automaticamente contra os fatos da KB, com override justificado."""
import datetime as dt
import re

from . import util
from .kb import KB, NOME_QUADRANTE

VEREDITOS = ("PASSA", "RISCO", "NAO", "INDEFINIDO")
ENUM_PARA_VEREDITO = {"SIM": "PASSA", "NAO": "NAO", "PARCIAL": "RISCO", "PREVIEW": "RISCO",
                      "NAO_CONFIRMADO": "RISCO", "NAO_DOCUMENTADO": "RISCO"}


class Contexto:
    def __init__(self, kb: KB, data_ref: dt.date):
        self.kb, self.data_ref = kb, data_ref
        self.usados = []

    def fato(self, fid, nome):
        f = self.kb.fato(fid, nome, self.data_ref)
        self.usados.append(f)
        return f


def _indisponivel(f):
    if f["status"] == "SEM_FICHA":
        return "INDEFINIDO", "fornecedor sem ficha na KB (kb/fornecedores)"
    if f["status"] == "AUSENTE":
        return "INDEFINIDO", (f"sem evidência pública de '{f['fato']}' na KB — pesquisar fonte oficial (vai para a KB) "
                              "ou tratar neste edital com dúvida/confirmação do fabricante (02-analise/gates-override.yaml)")
    if f["status"] == "SEM_DATA":
        return "INDEFINIDO", f"fato '{f['fato']}' sem data de verificação na KB — revalidar"
    if f["status"] == "VENCIDO":
        return "INDEFINIDO", (f"fato '{f['fato']}' vencido (verificado em {f['verificado_em']}; "
                              f"valor anterior: {f['valor']}) — revalidar")
    return None


def regra_gartner_lider(ctx, fid, params):
    anos = int(params.get("anos", 3))
    consecutivos = params.get("consecutivos", True)
    eds = ctx.kb.edicoes(ctx.data_ref)
    if len(eds) < anos:
        return "INDEFINIDO", f"kb/gartner-mq.yaml tem só {len(eds)} edição(ões) até {ctx.data_ref}", []
    janela = eds[:anos] if consecutivos else eds
    posicoes = [(int(e["ano"]), ctx.kb.posicao(e, fid)) for e in janela]
    texto = " · ".join(f"{a}: {NOME_QUADRANTE[p]}" for a, p in sorted(posicoes))
    lider = sum(1 for _, p in posicoes if p == "lider")
    ok = lider == anos if consecutivos else lider >= anos
    nomes = {e.get("titulo") for e in janela}
    aviso = ""
    clausula = util.norm(params.get("_clausula", ""))
    if ("application performance" in clausula or "apm" in clausula) and any("Observability Platforms" in (n or "")
                                                                            for n in nomes):
        aviso = " — atenção: o edital cita o nome antigo do MQ (APM and Observability), renomeado para " \
                "Observability Platforms em 2024; registrar dúvida de continuidade"
    fatos = [{"fato": "gartner_mq", "valor": texto, "status": "OK", "fonte": "kb/gartner-mq.yaml",
              "verificado_em": janela[0].get("data_publicacao")}]
    return ("PASSA" if ok else "NAO"), texto + aviso, fatos


def regra_integracoes_min(ctx, fid, params):
    f = ctx.fato(fid, "integracoes_nativas")
    if (ind := _indisponivel(f)):
        return ind[0], ind[1], [f]
    minimo = int(params.get("min", 1000))
    valor = int(f["valor"])
    estrito = params.get("estrito", True)
    ok = (valor > minimo or (valor == minimo and f.get("qualificador") == "mais de")) if estrito else valor >= minimo
    desc = f"{(f.get('qualificador') + ' ') if f.get('qualificador') else ''}{valor} integrações"
    return ("PASSA" if ok else "NAO"), f"{desc} (exigido: {'>' if estrito else '≥'} {minimo})", [f]


def regra_sla_min(ctx, fid, params):
    f = ctx.fato(fid, "sla_disponibilidade_pct")
    if (ind := _indisponivel(f)):
        return ind[0], ind[1], [f]
    exigido = float(params.get("pct", 99.8))
    ok = float(f["valor"]) >= exigido
    return ("PASSA" if ok else "NAO"), f"SLA publicado {util.br(f['valor'], 2)}% (exigido ≥ {util.br(exigido, 2)}%)", [f]


def _regra_enum(nome, rotulo):
    def regra(ctx, fid, params):
        f = ctx.fato(fid, nome)
        if (ind := _indisponivel(f)):
            return ind[0], ind[1], [f]
        veredito = ENUM_PARA_VEREDITO.get(str(f["valor"]), "INDEFINIDO")
        detalhe = f"{rotulo}: {f['valor']}" + (f" — {f['obs']}" if f.get("obs") else "")
        return veredito, detalhe, [f]
    return regra


def regra_retencao_metricas_min(ctx, fid, params):
    f = ctx.fato(fid, "retencao_metricas_meses")
    if (ind := _indisponivel(f)):
        return ind[0], ind[1], [f]
    meses = float(params.get("meses", 13))
    if float(f["valor"]) < meses:
        return "NAO", f"retenção máxima {f['valor']} meses (exigido ≥ {util.br(meses, 0)})", [f]
    if not params.get("integral"):
        return "PASSA", f"retenção {f['valor']} meses (exigido ≥ {util.br(meses, 0)})", [f]
    g = ctx.fato(fid, "retencao_metricas_integral")
    if (ind := _indisponivel(g)):
        return ind[0], ind[1], [f, g]
    veredito = ENUM_PARA_VEREDITO.get(str(g["valor"]), "INDEFINIDO")
    return veredito, f"retenção {f['valor']} meses; granularidade integral: {g['valor']}", [f, g]


def _regra_lista(nome, param, normalizar=False):
    """normalizar=True compara sem pontuação/espaços e por prefixo ("SOC2" casa "SOC 2 Type II")."""
    def chave(x):
        return re.sub(r"[^a-z0-9]", "", util.norm(x)) if normalizar else str(x).lower()

    def regra(ctx, fid, params):
        f = ctx.fato(fid, nome)
        if (ind := _indisponivel(f)):
            return ind[0], ind[1], [f]
        exigidos = [str(x) for x in params.get(param) or []]
        tem = [chave(x) for x in f["valor"] or []]
        casa = (lambda e: any(t.startswith(chave(e)) for t in tem)) if normalizar else (lambda e: chave(e) in tem)
        faltam = [x for x in exigidos if not casa(x)]
        if faltam:
            return "NAO", f"não cobre: {', '.join(faltam)}", [f]
        return "PASSA", f"cobre: {', '.join(exigidos)}", [f]
    return regra


OPERADORES = {
    "==": lambda a, b: a == b, "!=": lambda a, b: a != b, ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, "<": lambda a, b: a < b, "in": lambda a, b: a in b,
    "contem": lambda a, b: b in (a or []),
}


def regra_fato(ctx, fid, params):
    nome, op, alvo = params.get("fato"), params.get("operador", "=="), params.get("valor")
    f = ctx.fato(fid, nome)
    if (ind := _indisponivel(f)):
        return ind[0], ind[1], [f]
    try:
        ok = OPERADORES[op](f["valor"], alvo)
    except (KeyError, TypeError):
        return "INDEFINIDO", f"regra 'fato' mal configurada (operador {op!r})", [f]
    return ("PASSA" if ok else "NAO"), f"{nome}={f['valor']} ({op} {alvo})", [f]


def regra_manual(ctx, fid, params):
    return "INDEFINIDO", "avaliação manual — registrar veredito em 02-analise/gates-override.yaml", []


REGRAS = {
    "gartner_lider": regra_gartner_lider,
    "integracoes_min": regra_integracoes_min,
    "sla_min": regra_sla_min,
    "suporte_ptbr": _regra_enum("suporte_ptbr", "suporte em português"),
    "regiao_brasil": _regra_enum("regiao_dados_brasil", "região de dados no Brasil"),
    "agente_open_source": _regra_enum("agente_open_source", "agente open source/auditável"),
    "opentelemetry": _regra_enum("opentelemetry", "OpenTelemetry"),
    "self_managed": _regra_enum("self_managed", "implantação self-managed"),
    "rum_mobile": _regra_enum("rum_mobile", "RUM mobile nativo"),
    "session_replay": _regra_enum("session_replay", "session replay"),
    "retencao_metricas_min": regra_retencao_metricas_min,
    "so_suportados": _regra_lista("so_suportados", "so"),
    "certificacoes": _regra_lista("certificacoes", "lista", normalizar=True),
    "fato": regra_fato,
    "manual": regra_manual,
}


def carregar_overrides(projeto) -> tuple[dict, list]:
    dados = util.ler_yaml(projeto.dir_analise / "gates-override.yaml", []) or []
    validos, problemas = {}, []
    for o in dados:
        chave = (o.get("fornecedor"), o.get("gate"))
        if o.get("veredito") not in ("PASSA", "RISCO", "NAO"):
            problemas.append(f"override {chave}: veredito deve ser PASSA, RISCO ou NAO")
        elif not str(o.get("justificativa") or "").strip():
            problemas.append(f"override {chave}: justificativa obrigatória — override ignorado")
        else:
            validos[chave] = o
    return validos, problemas


def avaliar(projeto, fornecedores: list, kb: KB | None = None) -> dict:
    kb = kb or KB()
    gates_cfg = projeto.cfg.get("gates") or []
    overrides, problemas = carregar_overrides(projeto)
    resultado = {"data_referencia": projeto.data_ref, "gates": gates_cfg, "problemas": problemas, "fornecedores": {}}
    for fid in fornecedores:
        linhas = []
        for g in gates_cfg:
            regra = REGRAS.get(g["regra"])
            ctx = Contexto(kb, projeto.data_ref)
            if regra is None:
                veredito, just, fatos = "INDEFINIDO", f"regra desconhecida: {g['regra']}", []
            else:
                params = {**(g.get("params") or {}), "_clausula": g.get("clausula", "")}
                veredito, just, fatos = regra(ctx, fid, params)
            linha = {"gate": g["id"], "regra": g["regra"], "veredito": veredito, "justificativa": just,
                     "eliminatorio": bool(g.get("eliminatorio", True)), "override": False,
                     "fatos": [{k: f.get(k) for k in ("fato", "valor", "status", "fonte", "verificado_em")}
                               for f in (fatos or ctx.usados)]}
            o = overrides.get((fid, g["id"]))
            if o:
                linha.update({"veredito": o["veredito"], "override": True,
                              "justificativa": f"[override] {o['justificativa']}" +
                                               (f" (fonte: {o['fonte']})" if o.get("fonte") else ""),
                              "veredito_automatico": veredito})
            linhas.append(linha)
        resultado["fornecedores"][fid] = {"nome": kb.nome(fid), "gates": linhas, **status(linhas)}
    util.gravar_json(projeto.dir_analise / "gates.json", resultado)
    return resultado


def status(linhas: list) -> dict:
    elim = [l for l in linhas if l["eliminatorio"]]
    reprovados = [l["gate"] for l in elim if l["veredito"] == "NAO"]
    riscos = [l["gate"] for l in elim if l["veredito"] in ("RISCO", "INDEFINIDO")]
    situacao = "REPROVA" if reprovados else ("RISCO" if riscos else "PASSA")
    return {"status": situacao, "reprovados": reprovados, "riscos": riscos}
