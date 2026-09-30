---
name: analise-rfp-observabilidade
description: "Analisa editais/RFPs/TRs de observabilidade de qualquer cliente (docx, xlsx, pdf) com o kit-rfp-observabilidade — extrai e classifica requisitos, aplica gates eliminatórios, ranqueia fornecedores (Líderes do Gartner Magic Quadrant + Azure Monitor sempre) e gera relatórios (xlsx, html, md, docx/pdf). No modo proponente, responde a matriz do edital item a item com evidências oficiais e gera o pacote de submissão (planilha oficial respondida, anexo de dúvidas preenchido, memorial técnico e sumário executivo). Use quando pedirem para analisar ou responder um RFP/TR/edital de observabilidade, montar matriz de requisitos (RTM), comparar Datadog/Dynatrace/Grafana/New Relic/Elastic/Azure Monitor etc. ou atualizar a base de fornecedores. Executado sempre no VS Code: a cada execução atualiza a base de fornecedores e revisa todos os requisitos com LLM."
argument-hint: "[pasta do cliente] [neutro | proponente <fornecedor>]"
---

# Análise de RFP de observabilidade (kit-rfp-observabilidade)

## 0. Execução assistida — obrigatória em TODA execução
O kit é executado **sempre no VS Code, por esta skill**. O código Python faz o determinístico; o LLM faz, a cada
execução, o que depende de pesquisa e leitura: (1) **atualizar a KB** dos fornecedores do campo e conferir o Gartner
MQ; (2) **revisar todos os requisitos** do edital; (3) **transformar toda lacuna em pergunta de esclarecimento**. Com
`execucao.assistida: true` (padrão), o kit confere essas etapas e a validação dá ERRO se alguma não aconteceu nesta
execução — os entregáveis saem marcados PRELIMINAR. Nunca pule etapas nem use `--nao-assistida` num estudo real; se
algo não puder ser feito (sem rede, sem acesso a uma fonte), diga ao usuário e deixe a entrega PRELIMINAR.

Workspace: o `init` cria `<pasta-do-cliente>/<SIGLA>-analise-rfp.code-workspace` (pasta do cliente + kit) — abra-o no
VS Code para ter os documentos e esta skill juntos. Invocação: `/analise-rfp-observabilidade "<pasta>"`.

## 1. Localizar o kit
- `KIT` = variável de ambiente `RFP_KIT_HOME`. Se não existir: raiz do repositório que contém esta skill
  (três níveis acima deste arquivo: `.github/skills/analise-rfp-observabilidade/SKILL.md`).
- Comandos: `python "<KIT>/kit.py" <comando> "<pasta-do-cliente>"`. Dependências (uma vez): `pip install -r "<KIT>/requirements.txt"`.
- Os prompts de cada fase estão em `<KIT>/prompts/`. Leia o prompt da fase ANTES de executá-la.

## 2. Regras inegociáveis
1. **Gate antes do mérito.** Critério eliminatório é pass/fail; nenhuma nota compensa um gate reprovado. Gates são estritos até o cliente flexibilizar **por escrito**.
2. **Azure Monitor é sempre avaliado** (fica em `fornecedores.obrigatorios` no rfp.yaml), mesmo que reprove gate. Nunca o remova.
3. **Campo avaliado = Líderes da edição vigente do Gartner MQ** (automático via `kb/gartner-mq.yaml`) + obrigatórios + contexto do cliente.
4. **Evidência oficial ou nada.** Fatos e notas só com fonte pública oficial do fabricante (URL + data). Sem fonte → `null`. Preview não conta como GA. Não inflar matriz.
5. **Sem números digitados na narrativa** — use placeholders (`{{ r['id'].aderencia_pct | br }}`), para o texto nunca divergir do cálculo.
6. **Dados de cliente nunca entram em `<KIT>/kb/`** (repositório compartilhado). Tudo do cliente fica em `<pasta-do-cliente>/_analise-rfp/`.
7. **Checkpoints com o usuário** (use a ferramenta de perguntas): (a) gates do rfp.yaml; (b) triagem/ranking antes da narrativa.
8. **Confiança antes de afirmar.** Nenhuma resposta, nota ou veredito sem fonte oficial verificada nesta execução; se o
   edital ou a documentação não bastam para confiança alta, a saída é uma **pergunta de esclarecimento** (ou item de POC),
   nunca uma suposição.

## 3. Fluxo de cada execução
| # | Fase | Como | Saída |
|---|---|---|---|
| 0 | Preparar | `kit.py init "<pasta>" --cliente "<Nome>" --sigla <SIGLA> [--modo proponente --proponente azure-monitor]` (só na primeira vez) | `_analise-rfp/rfp.yaml`, pastas e o `.code-workspace` |
| 1 | Extrair | `kit.py extrair "<pasta>"`; ler `01-extracao/extracao-qa.json` (páginas sem texto → `ocr: true`) | `01-extracao/*.md` |
| 2 | Configurar | Ler `01-extracao/` e preencher no rfp.yaml: `cliente.contexto`, `gates` (**prompts/02-extrair-gates.md**) e, se preciso, mapeamento de colunas de xlsx. **Checkpoint (a).** | rfp.yaml |
| 2a | Campo avaliado | `kit.py rtm` e `kit.py ranking` para saber quem está na triagem (`02-analise/selecao.json`) | `selecao.json` |
| 2b | **Atualizar a KB** | Para **cada fornecedor da triagem** (e o proponente): um subagente por fornecedor, em paralelo, com **prompts/kb-pesquisar-fornecedor.md** — priorize os fatos usados pelos gates deste edital e as notas das categorias de maior peso; `atualizado_em` = hoje. Depois `kit.py kb-validar` e `kit.py kb-validar-urls --fornecedor <id> --atualizar` para cada um. Gartner: **prompts/kb-atualizar-gartner.md** (edição nova? senão só `revisado_em` = hoje) | `kb/fornecedores/*.yaml`, `kb/evidencias/`, `kb/gartner-mq.yaml` |
| 2c | **Revisar todos os requisitos** | `kit.py revisar "<pasta>"` → um subagente por lote (`02-analise/revisao/lote-NN.json`) com **prompts/14-revisar-requisitos.md** → `kit.py revisar "<pasta>" --consolidar`; repetir até 0 pendentes. Lacunas viram dúvidas em `duvidas.yaml` | `02-analise/revisao-requisitos.json`, `duvidas.yaml` |
| 2d | **Investigar requisito × fornecedor** | `kit.py investigar "<pasta>"` → um subagente por lote (`02-analise/investigacao/<fornecedor>/lote-NN.json`, um fornecedor por lote) com **prompts/15-investigar-requisitos.md** → `kit.py investigar "<pasta>" --consolidar`; repetir até 0 pendentes. Evidência nova vai para `kb/evidencias/<id>.yaml` com citação literal | `02-analise/investigacao.json`, dúvidas novas |
| 2e | **Verificação independente** | `kit.py verificar-independente "<pasta>"` → subagentes com **OUTRO modelo** (`model` diferente) e **prompts/16-verificacao-independente.md** → `--consolidar`. **Checkpoint (c):** apresentar cada divergência ao usuário e registrar `resolucao` (manter + justificativa, ou corrigir e reinvestigar) | `02-analise/verificacao-independente.json` |
| 2f | **Conferir no navegador** | Para evidências `NAVEGADOR`/`BLOQUEADA` em `validacao-urls.md`: abrir a página com o navegador do VS Code, confirmar as citações literais e gravar `verificado_navegador_em` na evidência da KB | `kb/evidencias/*.yaml` |
| 3 | Rodar | `kit.py tudo "<pasta>"` (verifica URLs e citações, calcula a confiança e grava `02-analise/execucao.json` e `confianca.md`) | RTM, pesos, gates, ranking, relatórios, `02-analise/validacao.md` |
| 4 | Pendências | Tratar `validacao.md` nesta ordem: classificação (**01**), fatos INDEFINIDO/vencidos/sem ficha na KB (**kb-pesquisar-fornecedor**), ajustes de nota por contexto (**03**), eixos (**04**). Rodar `tudo` de novo após cada rodada. | `02-analise/*.csv|yaml`, `kb/fornecedores/*.yaml` |
| 5 | Decisão | Mostrar triagem, ranking, sensibilidade e cenários de gate (`02-analise/ranking.md`, `eliminatorios.md`) ao usuário. **Checkpoint (b).** | — |
| 6 | Evidências | Registrar em `02-analise/registro-evidencias.yaml` toda alegação que sustenta decisão (leitura de cláusula, gate INDEFINIDO/RISCO, direcionamento, resposta negativa): fonte oficial ou `edital: <arquivo> <item>`, citação literal, confiança, impacto — ou `kb: EV-…`. O `tudo` gera os dossiês. | `00-projeto/evidencias/` (índice, Gartner, dossiê por fornecedor, registro) |
| 7 | Narrativa | **prompts/07-narrativa.md** → `02-analise/narrativa.md`; `tudo` | relatórios finais |
| 8 | Fechar | `tudo` com **0 ERRO**; para a versão enviada ao cliente use `relatorio.incluir_pendencias: false` | `03-entregas/` |

Módulos opcionais (só se estiverem em `modulos` no rfp.yaml ou se o usuário pedir):
`armadilhas`/`direcionamento` (**05**), `red_team` (**06**), `poc` (**08**), `pente_fino` (**10**), `defesa` (**11**),
`cases` (**12**), `esforco`/`custo` (**13** — esforço de POC por frente e custo a preço de tabela, com fonte).

O `tudo` também gera as **análises internas** em `02-analise/` (não enviar ao cliente): `eliminatorios.md`,
`ranking.md` (duas lentes, sensibilidade, cenários de gate, battlecards no modo proponente), `duvidas-interna.md`,
`cases-referencia-maturidade.md` e `esforco-custo.md` — e o índice `03-entregas/README-ENTREGAS.md`.

### Modo proponente — pacote de submissão completo
| # | Etapa | Como | Saída em `03-entregas/` |
|---|---|---|---|
| P1 | Respostas | `kit.py respostas` (cria/sincroniza `02-analise/respostas.json` com a escala de cada aba) → preencher com **prompts/09-respostas-matriz.md**, citando evidências `EV-…` de `kb/evidencias/` → `kit.py respostas` | Planilha oficial **RESPONDIDA** (resposta + observação com justificativa, método, POC e `Ref.: URLs`; dropdown estendido; imagens preservadas; conferência em `verificacao-planilhas.md`) e `matriz-respostas-<sigla>.xlsx` |
| P2 | Evidências | `kit.py validar-urls` (HTTP 200 + palavras-chave) → ler `02-analise/pente-fino-automatico.md` (sem evidência, URL genérica, reuso alto de URL, justificativa curta, marketing, preview) → **prompts/10-pente-fino-evidencias.md** | `02-analise/validacao-urls.md`, `pente-fino-automatico.md`, `00-projeto/evidencias/biblioteca-<proponente>.md` |
| P3 | Dúvidas | **prompts/05** → `02-analise/duvidas.yaml` → `kit.py duvidas` | `duvidas-<sigla>.xlsx` e modelo do edital **PREENCHIDO** |
| P4 | Defesa e cases | **prompts/11** e **prompts/12** (cases e arquiteturas de `kb/cases/` com `kb: REF-…` + `relacao` com este cliente) | `roteiro-defesa-parciais.md`, `cases-referencia.yaml` (Anexo B) |
| P5 | Documentos | narrativa com `## Arquitetura` (**prompts/07**) → `kit.py tudo "<pasta>" --urls --pdf` | Memorial técnico e sumário executivo em DOCX e PDF, HTML/MD com a seção de respostas |

### Confiança e ciclo de esclarecimento
- A confiança de cada avaliação é calculada pelo kit (`02-analise/confianca.md`): **alta** = requisito claro +
  citação oficial literal (15+ caracteres) **do próprio fornecedor** conferida nesta execução + GA + a fonte cobre o
  parâmetro pedido (`na` exige justificativa). Abaixo de alta, cada item
  precisa de encaminhamento: **pergunta ao cliente** (lacuna do edital — vai para o anexo de dúvidas), **pergunta ao
  fabricante ou POC** (lacuna da documentação) ou **nova verificação**. Eliminatório sem encaminhamento e resposta
  plena do proponente sem confiança alta são ERRO.
- Quando o cliente responder: em `duvidas.yaml` marque `status: RESPONDIDA`, `resposta_cliente` e `respondida_em`;
  rode `kit.py tudo` — os requisitos ligados à dúvida voltam para revisão e investigação com a resposta como contexto
  (campos `reabrir`/`resposta_cliente` nos lotes; resposta que chega depois reabre de novo). Erratas: acrescente o
  documento em `entradas`; requisitos com texto novo voltam para a fila sozinhos. `confianca.md` mostra o que mudou
  desde a execução anterior.
- Lote ilegível é isolado como `lote-NN.json.invalido` (ou `.N.invalido`, sem sobrescrever) e aparece como
  `!! lote ilegível` — corrija o JSON, renomeie de volta para `lote-NN.json` e rode de novo. Nada investigado se perde quando o campo avaliado ou o escopo mudam
  (`fora_do_campo`, `investigacao-arquivo.json`).

## 4. Atualização da base de conhecimento (KB) — detalhes da fase 2b
- `kit.py kb-status` lista fatos vencidos/sem data e evidências a validar (`--ausentes` inclui fatos sem evidência pública); `kit.py kb-validar` valida o esquema; `kit.py kb-validar-urls --fornecedor <id> --atualizar` verifica e grava o status das URLs; `kit.py kb-novo <id>` cria ficha.
- Pesquise **um fornecedor por subagente, em paralelo**, com **prompts/kb-pesquisar-fornecedor.md**; grave o YAML retornado em `kb/fornecedores/<id>.yaml` e rode `kb-validar`.
- Evidências por capacidade (modo proponente): **prompts/kb-evidencias-fornecedor.md** → `kb/evidencias/<id>.yaml` (capacidade genérica + URL oficial + citação; alegações de limitação com `alegacao` + `citacoes` literais; `verificacao: navegador` para páginas montadas por JavaScript).
- Cases e arquiteturas de referência publicados: `kb/cases/<id>.yaml` (modelo em `kb/cases/_modelo.yaml`); a relação com um cliente fica só no estudo.
- Nova edição do Gartner MQ (todo julho): **prompts/kb-atualizar-gartner.md** → `kb/gartner-mq.yaml`.
- Só informação pública de fabricante. Nunca copie trechos do edital ou contexto do cliente para a KB.
- **Confirmações não viram aprendizado:** o que precisa ser confirmado com o fabricante depende dos requisitos de cada edital. Gate INDEFINIDO/RISCO → pesquise **fonte pública** (se achar, atualize a KB); se a resposta vier do fabricante para este edital, registre só no estudo do cliente (`02-analise/gates-override.yaml` + `registro-evidencias.yaml` + dúvidas), nunca na KB. Não gere listas de "fatos a confirmar" fora do contexto de um edital.

## 5. Ao terminar, reporte ao usuário
Status da execução assistida (`02-analise/execucao.json`: completa ou pendências), caminhos dos entregáveis em
`03-entregas/` e dos dossiês em `00-projeto/evidencias/`, resultado da triagem (quem passa/reprova e por quê), top do
ranking, pendências abertas (dúvidas a submeter, fatos a confirmar por escrito, sinais do pente-fino) e quaisquer
suposições feitas. Lembre o usuário de versionar as atualizações da KB (`kb/`) no repositório do kit — nunca os
arquivos do cliente.
