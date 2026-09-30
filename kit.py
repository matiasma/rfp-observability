"""CLI do kit de análise de RFP de observabilidade.

Uso: python kit.py <comando> [pasta-do-cliente] [opções]   (python kit.py -h para a lista de comandos)
"""
import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from rfpkit import __version__, util
from rfpkit.config import KB_DIR, KIT_HOME, TEMPLATES_DIR, ErroConfig, Projeto
from rfpkit.kb import KB

ARQS_ANALISE = ("narrativa.md", "ajustes-notas.yaml", "eixos.yaml", "gates-override.yaml", "classificacao-manual.csv",
                "duvidas.yaml", "registro-evidencias.yaml")
MODULOS = {"armadilhas": "armadilhas-duvidas.md", "direcionamento": "direcionamento.md",
           "red_team": "red-team.md", "poc": "plano-poc.md", "defesa": "roteiro-defesa-parciais.md",
           "pente_fino": "pente-fino-evidencias.md", "cases": "cases-referencia.yaml",
           "esforco": "esforco-poc.yaml", "custo": "custo.yaml"}
EXTENSOES = (".docx", ".xlsx", ".xlsm", ".pdf")


def cmd_init(a):
    pasta = Path(a.pasta).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    proj = Projeto(pasta)
    proj.criar_pastas()
    if proj.arquivo_config.exists() and not a.forcar:
        print(f"rfp.yaml já existe em {proj.raiz} (use --forcar para recriar). Nada alterado.")
    else:
        documentos = [p for p in sorted(pasta.iterdir())
                      if p.is_file() and p.suffix.lower() in EXTENSOES and not p.name.startswith("~$")]
        modelo_duvidas = next((p.name for p in documentos
                               if p.suffix.lower() in (".xlsx", ".xlsm") and "duvida" in util.norm(p.name)), None)
        entradas = [{"arquivo": p.name, "tipo": "xlsx" if p.suffix.lower() == ".xlsm" else p.suffix.lower()[1:]}
                    for p in documentos if p.name != modelo_duvidas]
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), trim_blocks=True, lstrip_blocks=True)
        texto = env.get_template("rfp.yaml.j2").render(
            cliente_nome=a.cliente or pasta.name, sigla=(a.sigla or util.slug(pasta.name)).upper(),
            setor=a.setor or "", data_referencia=a.data or dt.date.today().isoformat(), modo=a.modo,
            proponente=a.proponente or "null", entradas=entradas,
            modelo_duvidas=f'"{modelo_duvidas}"' if modelo_duvidas else "null",
            assistida=not getattr(a, "nao_assistida", False))
        proj.arquivo_config.write_text(texto, encoding="utf-8")
        print(f"Criado: {proj.arquivo_config}  ({len(entradas)} documento(s) do edital"
              + (f"; modelo de dúvidas: {modelo_duvidas}" if modelo_duvidas else "") + ")")
    for nome in ARQS_ANALISE:
        destino = proj.dir_analise / nome
        if not destino.exists():
            shutil.copyfile(TEMPLATES_DIR / "analise" / nome, destino)
    workspace = _criar_workspace(proj)
    print(f"Estrutura pronta em {proj.raiz}\nPróximo passo: abra no VS Code o workspace {workspace.name} (pasta do "
          "cliente + kit) e peça no chat do Copilot: /analise-rfp-observabilidade "
          f"\"{pasta}\" — a skill conduz a execução assistida.")


def _criar_workspace(proj):
    """Workspace do VS Code com a pasta do cliente e a do kit: a skill (.github/skills) e as instruções do kit ficam
    disponíveis para o Copilot enquanto ele trabalha nos documentos do cliente."""
    import json
    destino = proj.pasta_cliente / f"{proj.sigla.upper()}-analise-rfp.code-workspace"
    if not destino.exists():
        dados = {"folders": [{"name": f"cliente — {proj.pasta_cliente.name}", "path": "."},
                             {"name": "kit-rfp-observabilidade", "path": str(KIT_HOME)}],
                 "settings": {"files.exclude": {"**/__pycache__": True, "**/.pytest_cache": True}},
                 "extensions": {"recommendations": ["github.copilot-chat", "ms-python.python"]}}
        destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destino


def _preparar_modulos(proj):
    for nome in ARQS_ANALISE:   # estudos criados por versões anteriores do kit recebem os arquivos novos (vazios)
        destino = proj.dir_analise / nome
        if not destino.exists():
            shutil.copyfile(TEMPLATES_DIR / "analise" / nome, destino)
    for modulo in proj.cfg.get("modulos") or []:
        nome = MODULOS.get(modulo)
        if nome and not (proj.dir_analise / nome).exists():
            texto = (TEMPLATES_DIR / "analise" / nome).read_text(encoding="utf-8")
            (proj.dir_analise / nome).write_text(texto.replace("{{CLIENTE}}", proj.cfg["cliente"]["nome"]),
                                                 encoding="utf-8")


def cmd_extrair(a, proj=None):
    from rfpkit.extracao import extrair
    proj = proj or Projeto(a.pasta)
    for r in extrair(proj):
        print(f"  {'ERRO' if 'erro' in r else 'ok  '} {r['arquivo']}: {r.get('erro') or {k: v for k, v in r.items() if k not in ('arquivo', 'saida')}}")


def cmd_rtm(a, proj=None, kb=None):
    from rfpkit.rtm import construir_rtm
    proj = proj or Projeto(a.pasta)
    rtm = construir_rtm(proj, kb)
    res = rtm["resumo"]
    base = res["relevantes_para_pesos"]
    pct = 100 * res["nao_classificados_relevantes"] / base if base else 0
    print(f"  {rtm['total']} requisitos ({base} entram nos pesos) · não classificados entre esses: "
          f"{res['nao_classificados_relevantes']} ({util.br(pct)}%)")
    print(f"  por obrigatoriedade: {res['por_obrigatoriedade']}")
    print(f"  por natureza: {res['por_natureza']}")
    for aviso in rtm["avisos"]:
        print(f"  AVISO: {aviso}")
    return rtm


def cmd_pesos(a, proj=None, kb=None):
    from rfpkit.pesos import calcular_pesos
    proj = proj or Projeto(a.pasta)
    pesos = calcular_pesos(proj, kb)
    top = sorted(pesos["categorias"], key=lambda c: -c["peso"])
    print("  " + " · ".join(f"{c['id']} {util.br(c['peso'])}" for c in top if c["peso"] > 0))
    return pesos


def cmd_ranking(a, proj=None, kb=None):
    from rfpkit.ranking import calcular
    proj = proj or Projeto(a.pasta)
    res = calcular(proj, kb)
    print(f"  Gartner MQ vigente: {res['edicao_gartner']} · triagem: {len(res['triagem'])} · "
          f"avaliação completa: {len(res['avaliacao_completa'])}")
    print(f"  {'Fornecedor':32} {'Origem':20} {'Gate':8} {'Ader.prévia':>11}  Completa")
    for t in res["triagem"]:
        print(f"  {t['nome'][:32]:32} {t['origem'][:20]:20} {t['status_gate']:8} "
              f"{util.br(t['aderencia_previa_pct']):>10}%  {'sim' if t['avaliacao_completa'] else '-'}")
    print(f"\n  {'#':>2} {'Fornecedor':32} {'Ader.%':>7} {'Final':>6}  Gate")
    for l in res["ranking"]:
        print(f"  {l['posicao']:>2} {l['nome'][:32]:32} {util.br(l['aderencia_pct']):>7} "
              f"{util.br(l['nota_final'], 2):>6}  {l['status_gate']}")
    for aviso in res["avisos"]:
        print(f"  AVISO: {aviso}")
    return res


def cmd_premissas(a, proj=None, kb=None):
    from rfpkit.relatorios import gerar_premissas
    proj = proj or Projeto(a.pasta)
    print(f"  {gerar_premissas(proj, kb)}")


def cmd_validar(a, proj=None, kb=None, silencioso=False):
    from rfpkit.validacao import validar
    proj = proj or Projeto(a.pasta)
    probs = validar(proj, kb)
    erros = [p for p in probs if p["nivel"] == "ERRO"]
    if not silencioso:
        for p in probs:
            print(f"  {p['nivel']:5} [{p['codigo']}] {p['mensagem']}")
        print(f"  {len(erros)} erro(s), {len(probs) - len(erros)} aviso(s) — detalhes em {proj.dir_analise / 'validacao.md'}")
    return probs


def cmd_relatorios(a, proj=None, kb=None, pendencias=None):
    from rfpkit.relatorios import gerar
    proj = proj or Projeto(a.pasta)
    if pendencias is None:
        pendencias = cmd_validar(a, proj, kb, silencioso=True)
    if getattr(a, "pdf", False):
        proj.cfg["relatorio"]["pdf"] = True
    for s in gerar(proj, kb, pendencias):
        print(f"  {s}")


def cmd_respostas(a, proj=None, kb=None):
    from rfpkit import respostas
    proj = proj or Projeto(a.pasta)
    info = respostas.preparar(proj)
    print(f"  {info['caminho']}: {info['respondidos']} respondido(s), {info['novos']} requisito(s) novo(s) sem "
          f"resposta{', ' + str(info['orfas']) + ' resposta(s) órfã(s)' if info['orfas'] else ''}")
    if not info["respondidos"]:
        print("  Preencha as respostas (prompts/09-respostas-matriz.md) e rode de novo.")
        return
    for s in respostas.exportar(proj, kb):
        print(f"  {s}")
    cob = respostas.cobertura(proj)
    print(f"  cobertura: {cob['respondidos']}/{cob['total']} · por resposta: {cob['por_resposta']}"
          f" · eliminatórios em risco: {len(cob['eliminatorios_em_risco'])}")


def _problemas_lotes(info: dict):
    for p in info.get("problemas") or []:
        print(f"  !! lote ilegível: {p}")


def cmd_revisar(a, proj=None, kb=None):
    """Revisão de todos os requisitos por LLM: prepara os lotes para os subagentes ou consolida os preenchidos."""
    from rfpkit import revisao
    proj = proj or Projeto(a.pasta)
    if getattr(a, "consolidar", False):
        r = revisao.consolidar(proj, getattr(a, "tamanho", 40) or 40)
        _problemas_lotes(r)
        print(f"  {r['aplicados']} item(ns) consolidado(s){' (' + str(r['ignorados']) + ' ignorado(s): requisito mudou)' if r['ignorados'] else ''}"
              f"; {r['duvidas_criadas']} dúvida(s) criada(s) em 02-analise/duvidas.yaml")
        print(f"  revisados: {r['revisados']}/{r['total']} · com lacuna: {r['com_lacuna']} · "
              f"lacunas sem dúvida: {len(r['lacunas_sem_duvida'])}")
        if r["pendentes"]:
            print("  Ainda há pendentes: rode 'python kit.py revisar' para gerar os lotes que faltam.")
        return
    info = revisao.preparar(proj, getattr(a, "tamanho", 40) or 40)
    _problemas_lotes(info)
    print(f"  {revisao.arquivo(proj)}: {info['revisados']}/{info['total']} revisado(s), {info['pendentes']} pendente(s)"
          + (f"; {info['aplicados']} incorporado(s) dos lotes" if info["aplicados"] else "")
          + (f"; {info['duvidas_criadas']} dúvida(s) criada(s)" if info["duvidas_criadas"] else ""))
    for lote in info["lotes"]:
        print(f"  lote: {lote}")
    if info["lotes"]:
        print("  Preencha cada lote com um subagente (prompts/14-revisar-requisitos.md) e rode: "
              f"python kit.py revisar \"{proj.pasta_cliente}\" --consolidar")


def cmd_investigar(a, proj=None, kb=None):
    """Investigação requisito × fornecedor pelo LLM: lotes por fornecedor para os subagentes / consolidação."""
    from rfpkit import investigacao
    proj = proj or Projeto(a.pasta)
    info = investigacao.preparar(proj, getattr(a, "tamanho", 30) or 30)
    _problemas_lotes(info)
    cob = info["por_fornecedor"]
    print(f"  {info['requisitos']} requisito(s) que pesam na aderência × {len(info['fornecedores'])} fornecedor(es): "
          + " · ".join(f"{f} {c['investigados']}/{c['total']}" for f, c in cob.items())
          + (f"; {info['aplicados']} campo(s) incorporado(s) dos lotes" if info["aplicados"] else "")
          + (f"; {info['reabertas']} reaberta(s) por resposta do cliente" if info["reabertas"] else "")
          + (f"; {info['duvidas_criadas']} dúvida(s) criada(s)" if info["duvidas_criadas"] else "")
          + (f"; {info['arquivadas']} requisito(s) fora do escopo guardado(s) em investigacao-arquivo.json"
             if info["arquivadas"] else ""))
    for lote in info["lotes"][:20]:
        print(f"  lote: {lote}")
    if len(info["lotes"]) > 20:
        print(f"  … e mais {len(info['lotes']) - 20} lote(s) em {investigacao.dir_lotes(proj)}")
    if info["lotes"]:
        print("  Um subagente por lote (prompts/15-investigar-requisitos.md) e depois: "
              f"python kit.py investigar \"{proj.pasta_cliente}\" --consolidar")


def cmd_verificar_independente(a, proj=None, kb=None):
    """Verificação independente (segundo agente, outro modelo) de uma amostra das avaliações."""
    from rfpkit import independente
    proj, kb = proj or Projeto(a.pasta), kb or KB()
    info = independente.preparar(proj, kb, getattr(a, "tamanho", 30) or 30)
    _problemas_lotes(info)
    print(f"  amostra: {info['amostra']} · verificadas: {info['verificados']} · divergentes: {info['divergentes']} "
          f"(sem decisão: {info['divergencias_abertas']}) · concordância: "
          f"{util.br(info['concordancia_pct']) + '%' if info['concordancia_pct'] is not None else '—'}")
    for lote in info["lotes"]:
        print(f"  lote: {lote}")
    if info["lotes"]:
        print("  Um subagente de OUTRO modelo por lote (prompts/16-verificacao-independente.md) e depois: "
              f"python kit.py verificar-independente \"{proj.pasta_cliente}\" --consolidar")


def cmd_confianca(a, proj=None, kb=None):
    from rfpkit import confianca
    proj, kb = proj or Projeto(a.pasta), kb or KB()
    dados = confianca.calcular(proj, kb)
    for s in confianca.gravar(proj, kb, dados):
        print(f"  {s}")
    for fid, c in dados["resumo"].items():
        print(f"  {kb.nome(fid):32} alta {c['alta']:>4} · média {c['media']:>4} · baixa {c['baixa']:>4} · "
              f"eliminatórios com alta {c['elim_alta']}/{c['elim_total']} · com pendência {c['pendencias']}")


def cmd_duvidas(a, proj=None, kb=None):
    from rfpkit import duvidas
    proj = proj or Projeto(a.pasta)
    for s in duvidas.exportar(proj):
        print(f"  {s}")


def cmd_validar_urls(a, proj=None, kb=None):
    from rfpkit import urls
    proj, kb = proj or Projeto(a.pasta), kb or KB()
    alvos = urls.alvos_do_estudo(proj, kb)
    if not alvos:
        print("  Nenhuma URL citada nas respostas, cases ou registro de evidências deste estudo.")
        return
    resultados = urls.verificar_varias(alvos)
    urls.gravar_relatorio(resultados, proj.dir_analise / "validacao-urls.csv", proj.dir_analise / "validacao-urls.md",
                          f"Validação das URLs de evidência — {proj.cfg['cliente']['nome']}",
                          proj.dir_analise / "validacao-urls.json")
    falhas = [r for r in resultados if not r["ok"]]
    print(f"  {len(resultados)} URL(s) verificadas; {len(falhas)} a conferir — {proj.dir_analise / 'validacao-urls.md'}")
    for r in falhas:
        print(f"  !! {r['situacao']:13} {r['status'] or r['erro']} {r['url']}"
              + (f" -> {r['redirecionada_para']}" if r["redirecionada_para"] else ""))


def cmd_documentos(a, proj=None, kb=None):
    from rfpkit import documentos
    from rfpkit.relatorios import carregar_contexto
    proj, kb = proj or Projeto(a.pasta), kb or KB()
    for s in documentos.gerar(proj, kb, carregar_contexto(proj, kb), pdf=a.pdf):
        print(f"  {s}")


def cmd_evidencias(a, proj=None, kb=None):
    from rfpkit import evidencias
    proj, kb = proj or Projeto(a.pasta), kb or KB()
    saidas = evidencias.gerar(proj, kb)
    print(f"  {len(saidas)} arquivo(s) em {proj.dir_projeto / 'evidencias'} (índice: indice.md)")


def _dossies_sem_bloquear(a, proj, kb):
    """No 'tudo', os dossiês (artefato derivado) não podem impedir a validação e os entregáveis."""
    try:
        cmd_evidencias(a, proj, kb)
    except Exception as e:
        print(f"  AVISO: dossiês de evidências não gerados ({type(e).__name__}: {e}) — trate as pendências de "
              f"validacao.md e rode: python kit.py evidencias \"{proj.pasta_cliente}\"")


def cmd_analises(a, proj=None, kb=None):
    from rfpkit import analises
    proj, kb = proj or Projeto(a.pasta), kb or KB()
    for s in analises.gerar(proj, kb):
        print(f"  {s}")


def _analises_sem_bloquear(a, proj, kb):
    try:
        cmd_analises(a, proj, kb)
    except Exception as e:
        print(f"  AVISO: análises internas não geradas ({type(e).__name__}: {e}) — trate as pendências de "
              f"validacao.md e rode: python kit.py analises \"{proj.pasta_cliente}\"")


def cmd_tudo(a):
    proj, kb = Projeto(a.pasta), KB()
    proj.cfg                      # sem rfp.yaml: ErroConfig com a instrução de rodar 'init'
    proj.criar_pastas()
    _preparar_modulos(proj)
    from rfpkit import execucao
    assistida = execucao.config(proj)["assistida"]
    etapas = [("Extração", lambda: cmd_extrair(a, proj)), ("Matriz de requisitos", lambda: cmd_rtm(a, proj, kb))]
    if assistida:
        etapas.append(("Revisão dos requisitos por LLM (sincronização e lotes)", lambda: cmd_revisar(a, proj, kb)))
    etapas += [("Pesos", lambda: cmd_pesos(a, proj, kb)), ("Triagem, gates e ranking", lambda: cmd_ranking(a, proj, kb)),
               ("Premissas", lambda: cmd_premissas(a, proj, kb))]
    if assistida:
        etapas.append(("Investigação requisito × fornecedor (sincronização e lotes)",
                       lambda: cmd_investigar(a, proj, kb)))
    if proj.cfg["modo"] == "proponente":
        etapas.append(("Respostas (modo proponente)", lambda: cmd_respostas(a, proj, kb)))
    from rfpkit.duvidas import carregar as carregar_duvidas, enviavel
    if any(enviavel(d) for d in carregar_duvidas(proj)):
        etapas.append(("Dúvidas ao cliente", lambda: cmd_duvidas(a, proj, kb)))
    if getattr(a, "urls", False) or assistida:   # execução assistida: URLs verificadas em toda execução
        etapas.append(("Validação das URLs de evidência", lambda: cmd_validar_urls(a, proj, kb)))
    if assistida:
        etapas.append(("Verificação independente (amostra e lotes)", lambda: cmd_verificar_independente(a, proj, kb)))
    etapas.append(("Dossiês de evidências", lambda: _dossies_sem_bloquear(a, proj, kb)))
    etapas.append(("Análises internas (eliminatórios, ranking, dúvidas, cases, esforço/custo)",
                   lambda: _analises_sem_bloquear(a, proj, kb)))
    if assistida and execucao.ambiente() == "terminal":
        print("AVISO: execução fora do VS Code/Copilot — atualização da KB, revisão dos requisitos por LLM e pesquisa "
              "de evidências só acontecem pela skill no VS Code; os entregáveis sairão PRELIMINAR.")
    for titulo, fn in etapas:
        print(f"\n== {titulo}")
        fn()
    print("\n== Validação")
    probs = cmd_validar(a, proj, kb)
    print("\n== Entregáveis")
    cmd_relatorios(a, proj, kb, probs)
    return 1 if any(p["nivel"] == "ERRO" for p in probs) else 0


def cmd_kb_status(a):
    kb = KB()
    data = util.para_data(a.data) if a.data else dt.date.today()
    linhas = [l for l in kb.status(data, incluir_ausentes=a.ausentes or a.todos) if a.todos or l["status"] != "OK"]
    if a.csv:
        util.gravar_csv(a.csv, linhas, ["fornecedor", "fato", "status", "verificado_em", "vence_em"])
        print(f"  {a.csv}")
    atual = None
    for l in linhas:
        if l["fornecedor"] != atual:
            atual = l["fornecedor"]
            print(f"\n{kb.nome(atual)} ({atual})")
        print(f"  {l['status']:8} {l['fato']:34} verificado: {l['verificado_em'] or '—'}  vence: {l['vence_em'] or '—'}")
    ed = kb.edicao_vigente(data)
    print(f"\nGartner MQ vigente em {data}: {ed['ano'] if ed else '—'} · Líderes: {', '.join(kb.lideres_vigentes(data))}")
    pend = [l for l in linhas if l["status"] not in ("OK", "AUSENTE") or l["fato"].startswith("nota:")]
    print(f"{len(pend)} item(ns) a revalidar na KB (fatos vencidos/sem data, notas ausentes, evidências a validar)."
          + ("" if a.ausentes or a.todos else " Fatos sem evidência pública só aparecem com --ausentes."))


def cmd_kb_validar_urls(a):
    from rfpkit import urls
    kb = KB()
    alvos = urls.alvos_da_kb(kb, a.fornecedor)
    resultados = urls.verificar_varias(alvos)
    if a.csv:
        urls.gravar_relatorio(resultados, a.csv)
        print(f"  {a.csv}")
    falhas = [r for r in resultados if not r["ok"]]
    for r in falhas:
        print(f"  !! {r['situacao']:13} {r['status'] or r['erro']} {r['url']}"
              + (f" -> {r['redirecionada_para']}" if r["redirecionada_para"] else "")
              + (f" (faltam: {r['palavras_faltantes']})" if r["palavras_faltantes"] else "") + f" — {r['usado_por']}")
    bloqueadas = sum(1 for r in falhas if r["situacao"] in urls.INCONCLUSIVAS)
    print(f"  {len(resultados)} URL(s) verificadas; {len(falhas) - bloqueadas} a corrigir; "
          f"{bloqueadas} a conferir no navegador (site recusa robôs ou página montada por JavaScript).")
    if a.atualizar:
        print(f"  {urls.atualizar_bibliotecas(kb, resultados)} item(ns) atualizado(s) em kb/evidencias e kb/cases.")
    return 1 if len(falhas) > bloqueadas else 0


def cmd_kb_validar(a):
    probs = KB().validar()
    for nivel, msg in probs:
        print(f"  {nivel:5} {msg}")
    erros = sum(1 for n, _ in probs if n == "ERRO")
    print(f"  {erros} erro(s), {len(probs) - erros} aviso(s)")
    return 1 if erros else 0


def cmd_kb_novo(a):
    destino = KB_DIR / "fornecedores" / f"{a.id}.yaml"
    if destino.exists():
        print(f"Já existe: {destino}")
        return 1
    texto = (KB_DIR / "fornecedores" / "_modelo.yaml").read_text(encoding="utf-8")
    texto = texto.replace("id: exemplo-fornecedor", f"id: {a.id}", 1)
    texto = texto.replace("nome: Exemplo Fornecedor", f"nome: {a.nome or a.id}", 1)
    destino.write_text(texto, encoding="utf-8")
    print(f"Criado: {destino}\nPesquise e preencha com prompts/kb-pesquisar-fornecedor.md; valide com: python kit.py kb-validar")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        if sys.stdout.isatty():
            sys.stdout.reconfigure(errors="replace")
        else:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="kit.py", description=f"Kit de análise de RFP de observabilidade v{__version__}")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("init", help="cria _analise-rfp/ e o rfp.yaml na pasta do cliente")
    p.add_argument("pasta")
    p.add_argument("--cliente")
    p.add_argument("--sigla")
    p.add_argument("--setor")
    p.add_argument("--modo", choices=["neutro", "proponente"], default="neutro")
    p.add_argument("--proponente", help="id da KB (ex.: azure-monitor) quando --modo proponente")
    p.add_argument("--data", help="data de referência AAAA-MM-DD (padrão: hoje)")
    p.add_argument("--forcar", action="store_true", help="recria o rfp.yaml")
    p.add_argument("--nao-assistida", action="store_true",
                   help="modo diagnóstico sem as etapas de LLM (testes/exemplos) — não gera entregáveis finais")
    p.set_defaults(fn=cmd_init)

    for nome, fn, ajuda in (
        ("extrair", cmd_extrair, "documentos do edital -> 01-extracao/*.md"),
        ("rtm", cmd_rtm, "matriz de requisitos canônica (00-projeto/rtm.json/csv)"),
        ("pesos", cmd_pesos, "pesos das categorias (00-projeto/categorias-pesos.json)"),
        ("ranking", cmd_ranking, "triagem, gates, aderência e scorecard (02-analise/)"),
        ("premissas", cmd_premissas, "00-projeto/premissas.md a partir do rfp.yaml"),
        ("validar", cmd_validar, "verificações de qualidade (02-analise/validacao.md)"),
        ("relatorios", cmd_relatorios, "xlsx + html + md + docx em 03-entregas/"),
        ("respostas", cmd_respostas, "modo proponente: sincroniza respostas.json e preenche a matriz oficial"),
        ("revisar", cmd_revisar, "revisão de todos os requisitos por LLM: lotes para os subagentes / --consolidar"),
        ("investigar", cmd_investigar, "investigação requisito × fornecedor por LLM: lotes por fornecedor / --consolidar"),
        ("verificar-independente", cmd_verificar_independente,
         "verificação independente (outro modelo) de uma amostra das avaliações / --consolidar"),
        ("confianca", cmd_confianca, "confiança de cada avaliação (02-analise/confianca.json/md)"),
        ("duvidas", cmd_duvidas, "anexo de dúvidas (02-analise/duvidas.yaml -> xlsx e modelo do cliente)"),
        ("validar-urls", cmd_validar_urls, "verifica as URLs citadas nas respostas, cases e registro de evidências"),
        ("evidencias", cmd_evidencias, "dossiês de evidências do estudo em 00-projeto/evidencias/"),
        ("analises", cmd_analises, "análises internas em 02-analise/ (eliminatórios, ranking, dúvidas, cases, "
                                   "esforço/custo)"),
        ("documentos", cmd_documentos, "memorial técnico e sumário executivo em Word (e PDF com --pdf)"),
        ("tudo", cmd_tudo, "pipeline completo"),
    ):
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("pasta", help="pasta do cliente (onde estão os documentos do edital)")
        if nome in ("relatorios", "documentos", "tudo"):
            p.add_argument("--pdf", action="store_true", help="converte os documentos Word para PDF")
        if nome == "tudo":
            p.add_argument("--urls", action="store_true", help="inclui a validação das URLs de evidência (rede); "
                                                                 "automática na execução assistida")
        if nome in ("revisar", "investigar", "verificar-independente"):
            p.add_argument("--consolidar", action="store_true", help="incorpora os lotes preenchidos (e cria as dúvidas)")
            p.add_argument("--tamanho", type=int, default=40 if nome == "revisar" else 30,
                           help="itens por lote (padrão 40 na revisão, 30 nos demais)")
        p.set_defaults(fn=fn)

    p = sub.add_parser("kb-status", help="fatos da KB vencidos/sem data e evidências a validar")
    p.add_argument("--data", help="data de referência (padrão: hoje)")
    p.add_argument("--ausentes", action="store_true", help="inclui fatos sem evidência pública (valor null)")
    p.add_argument("--todos", action="store_true", help="inclui também fatos OK")
    p.add_argument("--csv", help="grava a lista em CSV")
    p.set_defaults(fn=cmd_kb_status)
    p = sub.add_parser("kb-validar", help="valida o esquema da KB")
    p.set_defaults(fn=cmd_kb_validar)
    p = sub.add_parser("kb-validar-urls", help="verifica as URLs da KB (evidências e fontes dos fatos)")
    p.add_argument("--fornecedor", help="id do fornecedor (padrão: todos)")
    p.add_argument("--atualizar", action="store_true", help="grava status/verificado_em em kb/evidencias e kb/cases")
    p.add_argument("--csv", help="grava o resultado em CSV")
    p.set_defaults(fn=cmd_kb_validar_urls)
    p = sub.add_parser("kb-novo", help="cria ficha de fornecedor a partir do modelo")
    p.add_argument("id")
    p.add_argument("--nome")
    p.set_defaults(fn=cmd_kb_novo)

    a = ap.parse_args(argv)
    try:
        codigo = a.fn(a)
    except ErroConfig as e:
        print(f"ERRO de configuração: {e}")
        return 2
    except RuntimeError as e:
        print(f"ERRO: {e}")
        return 1
    if a.comando == "validar":
        return 1 if any(p["nivel"] == "ERRO" for p in codigo or []) else 0
    return codigo if isinstance(codigo, int) else 0


if __name__ == "__main__":
    sys.exit(main())
