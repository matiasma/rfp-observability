"""Verificações de qualidade antes de entregar: coerência entre rfp.yaml, KB, RTM, gates, notas e narrativa."""
import re

from . import util
from .gates import REGRAS, carregar_overrides
from .kb import KB

ESCALA_EIXO = (0.0, 5.0)


def _p(nivel, codigo, mensagem):
    return {"nivel": nivel, "codigo": codigo, "mensagem": mensagem}


def validar(projeto, kb: KB | None = None) -> list:
    kb = kb or KB()
    cfg = projeto.cfg
    p = []

    for fid in cfg["fornecedores"].get("obrigatorios") or []:
        if fid not in kb.fornecedores:
            p.append(_p("ERRO", "config", f"fornecedor obrigatório '{fid}' sem ficha na KB"))
    if cfg["modo"] == "proponente" and cfg.get("proponente") not in kb.fornecedores:
        p.append(_p("ERRO", "config", f"proponente '{cfg.get('proponente')}' sem ficha na KB"))
    for g in cfg.get("gates") or []:
        if g["regra"] not in REGRAS:
            p.append(_p("ERRO", "config", f"gate {g['id']}: regra desconhecida '{g['regra']}'"))
        if not g.get("clausula"):
            p.append(_p("AVISO", "config", f"gate {g['id']}: transcreva a cláusula literal do edital em 'clausula'"))
    if cfg["fornecedores"].get("lideres_gartner") == "auto" and not kb.edicoes(projeto.data_ref):
        p.append(_p("AVISO", "gartner", "nenhuma edição do Gartner MQ publicada até a data de referência"))
    ed = kb.edicao_vigente(projeto.data_ref)
    if ed and (projeto.data_ref - util.para_data(ed.get("data_publicacao") or f"{ed['ano']}-07-01")).days > 400:
        p.append(_p("AVISO", "gartner", f"edição vigente do Gartner MQ é {ed['ano']} — verifique se há edição mais "
                                        "recente e atualize kb/gartner-mq.yaml"))

    for nivel, msg in kb.validar():
        p.append(_p(nivel, "kb", msg))

    rtm = util.ler_json(projeto.dir_projeto / "rtm.json")
    if not rtm:
        p.append(_p("ERRO", "rtm", "rtm.json ausente — rode 'python kit.py rtm'"))
        return _gravar(projeto, p)
    if rtm["total"] == 0:
        p.append(_p("ERRO", "rtm", "nenhum requisito extraído — revise 'entradas' no rfp.yaml"))
    else:
        nc = rtm["resumo"].get("nao_classificados_relevantes", rtm["resumo"]["nao_classificados"])
        base = rtm["resumo"].get("relevantes_para_pesos") or rtm["total"]
        pct = 100.0 * nc / base
        limite = float(cfg["classificacao"].get("limite_nao_classificado_pct", 5))
        if pct > limite:
            p.append(_p("AVISO", "classificacao",
                        f"{nc} de {base} requisitos que entram nos pesos ({util.br(pct)}%) não classificados "
                        f"(limite {util.br(limite)}%) — tratar 02-analise/pendencias-classificacao.csv "
                        "(prompts/01-classificar-pendencias.md)"))
    for a in rtm.get("avisos") or []:
        p.append(_p("AVISO", "rtm", a))

    pesos = util.ler_json(projeto.dir_projeto / "categorias-pesos.json")
    if pesos and abs(pesos["soma"] - 100) > 0.05:
        p.append(_p("ERRO", "pesos", f"soma dos pesos = {pesos['soma']} (esperado 100)"))

    _, problemas_override = carregar_overrides(projeto)
    for msg in problemas_override:
        p.append(_p("ERRO", "gates", msg))
    gates = util.ler_json(projeto.dir_analise / "gates.json")
    ranking = util.ler_json(projeto.dir_analise / "ranking.json")
    if gates:
        for fid, dados in gates["fornecedores"].items():
            for l in dados["gates"]:
                if l["veredito"] == "INDEFINIDO" and l["eliminatorio"]:
                    p.append(_p("AVISO", "gates", f"{dados['nome']} × {l['gate']}: INDEFINIDO — {l['justificativa']}"))

    categorias = {c["id"] for c in kb.categorias_produto}
    completa = set((ranking or {}).get("avaliacao_completa") or [])
    for a in util.ler_yaml(projeto.dir_analise / "ajustes-notas.yaml", []) or []:
        rot = f"ajuste {a.get('fornecedor')}/{a.get('categoria')}"
        if a.get("categoria") not in categorias:
            p.append(_p("ERRO", "ajustes", f"{rot}: categoria inválida"))
        nota = util.num(a.get("nota"))
        if nota is None or not 0 <= nota <= 1:
            p.append(_p("ERRO", "ajustes", f"{rot}: nota deve ser um número em [0,1]"))
        if not str(a.get("justificativa") or "").strip():
            p.append(_p("ERRO", "ajustes", f"{rot}: justificativa obrigatória"))
        if not a.get("fontes"):
            p.append(_p("ERRO", "ajustes", f"{rot}: ao menos uma fonte oficial é obrigatória"))
        if completa and a.get("fornecedor") not in completa:
            p.append(_p("AVISO", "ajustes", f"{rot}: fornecedor fora da avaliação completa"))

    eixos = util.ler_yaml(projeto.dir_analise / "eixos.yaml", {}) or {}
    if ranking:
        for fid in cfg["fornecedores"].get("obrigatorios") or []:
            if fid in kb.fornecedores and fid not in completa:
                p.append(_p("ERRO", "selecao", f"obrigatório '{fid}' fora da avaliação completa"))
        for l in ranking["ranking"]:
            e = eixos.get(l["fornecedor"]) or {}
            faltam = [k for k in cfg["eixos"] if k != "aderencia" and e.get(k) is None]
            if faltam:
                p.append(_p("AVISO", "eixos", f"{l['nome']}: eixos sem nota ({', '.join(faltam)}) — nota final em "
                                              "aberto (prompts/04-eixos-scorecard.md)"))
            for k, v in e.items():
                if k in cfg["eixos"] and v is not None:
                    valor = util.num(v)
                    if valor is None or not ESCALA_EIXO[0] <= valor <= ESCALA_EIXO[1]:
                        p.append(_p("ERRO", "eixos", f"{l['nome']}: eixo {k}={v} deve ser número entre 0 e 5"))
            if e and not e.get("justificativa"):
                p.append(_p("AVISO", "eixos", f"{l['nome']}: eixos sem justificativa"))
            if not l["notas_completas"]:
                vazias = [c for c, o in l["origem_notas"].items() if o == "ausente"]
                p.append(_p("AVISO", "notas", f"{l['nome']}: sem nota em {', '.join(vazias)} (contada como 0) — "
                                              "completar a KB ou ajustes-notas.yaml"))
        for aviso in ranking.get("avisos") or []:
            p.append(_p("AVISO", "selecao", aviso))

    narrativa = projeto.dir_analise / "narrativa.md"
    if narrativa.exists():
        bruto = narrativa.read_text(encoding="utf-8")
        sem_blocos = re.sub(r"\{#.*?#\}|\{\{.*?\}\}|<!--.*?-->", "", bruto, flags=re.S)
        for titulo in ("Recomendação", "Fatores estratégicos", "Próximos passos"):
            m = re.search(rf"^##\s+{titulo}\s*$(.*?)(?=^##\s|\Z)", sem_blocos, flags=re.S | re.M)
            if not m or not m.group(1).strip():
                p.append(_p("AVISO", "narrativa", f"seção '{titulo}' vazia (prompts/07-narrativa.md)"))
        numeros = re.findall(r"\b\d{1,3}[,.]\d{1,2}\s?%|\b[0-5][,.]\d{2}\b", sem_blocos)
        if numeros:
            p.append(_p("AVISO", "narrativa", f"números digitados na narrativa ({', '.join(sorted(set(numeros))[:5])}) "
                                              "— use placeholders para não divergir do cálculo"))
    else:
        p.append(_p("AVISO", "narrativa", "02-analise/narrativa.md ausente"))

    if cfg["modo"] == "proponente":
        resp = util.ler_json(projeto.dir_analise / "respostas.json")
        if resp is None:
            p.append(_p("AVISO", "respostas", "respostas.json ausente — rode 'python kit.py respostas'"))
        else:
            from .respostas import validar_respostas
            for nivel_msg, msg in validar_respostas(projeto, kb):
                p.append(_p(nivel_msg, "respostas", msg))
            vazias = sum(1 for r in resp if not r.get("resposta") and not r.get("_orfa"))
            if vazias:
                p.append(_p("AVISO", "respostas", f"{vazias} requisitos sem resposta"))
            if any(r.get("evidencias") for r in resp) and not (projeto.dir_analise / "validacao-urls.csv").exists():
                p.append(_p("AVISO", "urls", "URLs das evidências ainda não verificadas — rode 'python kit.py validar-urls'"))

    for r in util.ler_csv(projeto.dir_analise / "validacao-urls.csv"):
        situacao = r.get("situacao") or ("OK" if str(r.get("ok")).lower() in ("true", "1") else "QUEBRADA")
        if situacao == "OK":
            continue
        if situacao == "QUEBRADA":
            p.append(_p("ERRO", "urls", f"URL inacessível ({r.get('status') or r.get('erro')}): {r.get('url')} — "
                                        f"usada por {r.get('usado_por')}"))
        elif situacao == "BLOQUEADA":
            p.append(_p("AVISO", "urls", f"o site recusou a verificação automática ({r.get('status')}): {r.get('url')} "
                                         "— confira no navegador"))
        elif situacao == "NAVEGADOR":
            p.append(_p("AVISO", "urls", f"página montada por JavaScript (só a disponibilidade foi verificada): "
                                         f"{r.get('url')} — confira as citações no navegador"))
        elif situacao == "CITACAO_AUSENTE":
            p.append(_p("ERRO", "urls", f"a página não contém mais a citação literal que sustenta a evidência "
                                        f"({str(r.get('citacoes_ausentes'))[:120]}): {r.get('url')} — a fonte mudou ou a "
                                        "citação não é literal; reinvestigue os itens que a usam (usada por "
                                        f"{r.get('usado_por')})"))
        elif situacao == "REDIRECIONADA":
            p.append(_p("AVISO", "urls", f"URL redirecionada para {r.get('redirecionada_para')}: {r.get('url')} — "
                                         "confirme se a página de destino sustenta a afirmação e atualize a evidência"))
        else:
            p.append(_p("AVISO", "urls", f"página não contém as palavras-chave ({r.get('palavras_faltantes')}): "
                                         f"{r.get('url')} — confira se ainda sustenta a afirmação"))

    from .evidencias import validar_referencias, validar_registro
    for nivel_msg, msg in validar_registro(projeto, kb):
        p.append(_p(nivel_msg, "registro", msg))
    for nivel_msg, msg in validar_referencias(projeto, kb):
        p.append(_p(nivel_msg, "cases", msg))
    from .analises import validar_pontuacao
    for nivel_msg, msg in validar_pontuacao(projeto, kb):
        p.append(_p(nivel_msg, "cases", msg))
    from .esforco_custo import validar as validar_esforco_custo
    for nivel_msg, msg in validar_esforco_custo(projeto, kb):
        p.append(_p(nivel_msg, "esforco-custo", msg))
    for q in util.ler_json(projeto.dir_extracao / "extracao-qa.json", []) or []:
        sem_texto = q.get("paginas_sem_texto_lista") or []
        if sem_texto:
            p.append(_p("AVISO", "extracao", f"{q.get('arquivo')}: {len(sem_texto)} página(s) sem texto "
                                             f"({', '.join(map(str, sem_texto[:10]))}) — PDF escaneado: use 'ocr: true' "
                                             "na entrada do rfp.yaml ou confira o documento"))

    from .duvidas import validar as validar_duvidas
    for nivel_msg, msg in validar_duvidas(projeto):
        p.append(_p(nivel_msg, "duvidas", msg))
    from .revisao import validar as validar_revisao
    for nivel_msg, msg in validar_revisao(projeto, kb):
        p.append(_p(nivel_msg, "revisao", msg))
    from .investigacao import validar as validar_investigacao
    for nivel_msg, msg in validar_investigacao(projeto, kb):
        p.append(_p(nivel_msg, "investigacao", msg))
    from .independente import validar as validar_independente
    for nivel_msg, msg in validar_independente(projeto):
        p.append(_p(nivel_msg, "independente", msg))
    from .confianca import validar as validar_confianca
    for nivel_msg, msg in validar_confianca(projeto, kb):
        p.append(_p(nivel_msg, "confianca", msg))
    from .execucao import validar as validar_execucao
    for nivel_msg, msg in validar_execucao(projeto, kb)[0]:
        p.append(_p(nivel_msg, "execucao", msg))
    return _gravar(projeto, p)


def _gravar(projeto, problemas: list) -> list:
    linhas = ["# Validação da análise", "", f"_{len(problemas)} apontamento(s)._", "",
              "| Nível | Verificação | Detalhe |", "|---|---|---|"]
    for x in problemas:
        linhas.append(f"| {x['nivel']} | {x['codigo']} | {x['mensagem'].replace('|', '/')} |")
    projeto.dir_analise.mkdir(parents=True, exist_ok=True)
    (projeto.dir_analise / "validacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return problemas
