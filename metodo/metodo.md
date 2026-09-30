# Método de análise de RFP de observabilidade

Este documento explica **por que** o kit funciona do jeito que funciona. As premissas específicas de cada estudo
são geradas em `<pasta-do-cliente>/_analise-rfp/00-projeto/premissas.md` a partir do `rfp.yaml`.

## 1. Duas lentes, nesta ordem
1. **Gate eliminatório (pass/fail).** Critério knock-out do edital (habilitação do fabricante ou requisito
   eliminatório). Reprovar um gate desclassifica — nenhuma nota compensa. Gates são lidos de forma estrita até o
   cliente flexibilizar por escrito; ambiguidades viram dúvidas formais.
2. **Mérito ponderado.** Scorecard multi-eixo; para quem reprova no gate, o mérito é referência (hipótese de
   flexibilização), nunca recomendação.

## 2. Dois modos
- **Neutro:** estudo de seleção vendor-neutro. A recomendação deriva da evidência.
- **Proponente:** a resposta é de um fornecedor (ex.: Azure Monitor). Mede-se a aderência do produto ofertado,
  com honestidade ("Atende parcialmente" só com base GA demonstrável; "Não atende" quando não há caminho oficial),
  e os demais fornecedores viram inteligência competitiva.

## 3. Campo avaliado
Líderes da edição vigente do Gartner MQ for Observability Platforms + **Azure Monitor (sempre)** + fornecedores
de contexto (incumbente, legado). Todos passam pela **triagem de gates**; a **avaliação completa** fica com os
obrigatórios e os melhores da triagem (padrão: até 6) — mais fornecedores sem inflar o trabalho.

## 4. Requisitos → categorias → pesos
- A matriz de requisitos (RTM) é extraída do edital e classificada numa **taxonomia fixa** (`kb/taxonomia.yaml`),
  o que permite reaproveitar as notas dos fornecedores entre editais.
- Cada requisito tem **natureza** (técnico, implantação, SLA, qualificação, comercial, processo) e
  **obrigatoriedade** (eliminatório, obrigatório, desejável; o valor explícito do edital prevalece).
- **Peso da categoria** = soma dos requisitos das naturezas consideradas × multiplicador de obrigatoriedade,
  normalizada para 100. Serviços do integrador e licenciamento ficam fora da aderência do produto (alimentam os
  eixos esforço e custo). `override` fixa pesos quando o edital declara prioridades explícitas.

## 5. Régua e aderência
Régua única: **1,0** nativo-líder · **0,75** forte · **0,5** parcial/por extensão · **0,25** fraco · **0** não atende.
Nota efetiva = nota-base da KB ou ajuste justificado para o edital. **Aderência** = média ponderada pelas
categorias com peso.

## 6. Scorecard
Nota final (0–5) = Σ peso do eixo × valor, com aderência convertida para 0–5. Padrão: aderência 35 · risco 20 ·
esforço 15 · custo 20 · estratégico 10 (configurável). Eixos não calculados exigem justificativa por fornecedor.

## 6.1 Leituras da decisão
- **Duas lentes:** líder em aderência pura ao edital × líder no balanço completo (nota final).
- **Sensibilidade:** cada eixo ganha 20 p.p. (os demais caem proporcionalmente), mais "só aderência" e pesos iguais;
  o **1º robusto** é quem vence mais cenários (desempate: menor posição média), entre todos e entre os elegíveis.
- **Cenários de gate:** leitura estrita, cada gate eliminatório flexibilizado isoladamente e todos flexibilizados
  (só mérito) — mostra quem elimina quem e quem vira o melhor elegível. Flexibilização só com aceite do cliente por escrito.
- **Esforço × custo (opcional):** esforço de POC por frente (1 pessoa, dias úteis; frentes-portão de alto risco) e
  custo de produção a preço de tabela com fonte e data; os eixos `esforco` e `custo` devem ser coerentes com eles.

## 6.2 Confiança e esclarecimento
- **Investigação item a item:** cada requisito que pesa na aderência é investigado para cada fornecedor da avaliação
  completa (atendimento, como, GA, evidência oficial com citação literal, cobertura do parâmetro). A nota da categoria
  passa a sair dos itens (pleno 1,0 · por extensão 0,5 · parcial 0,5/0,25 · não atende 0, pesos por obrigatoriedade);
  a nota-base da KB só cobre o que ainda não foi investigado.
- **Confiança por regras:** alta = requisito claro + citação literal do próprio fornecedor conferida nesta execução
  (cada evidência pelas suas citações) + GA + cobre o parâmetro + sem conflito; média e baixa com os motivos
  registrados (ver README, seção "Confiança das respostas").
- **Portão:** abaixo de alta, cada motivo exige encaminhamento — pergunta ao cliente, pergunta ao fabricante/POC, nova
  verificação ou decisão humana. Eliminatório sem encaminhamento e resposta plena sem confiança alta bloqueiam a entrega.
- **Ciclo:** respostas do cliente e erratas reabrem só os itens afetados (toda resposta ainda não incorporada volta
  para o lote); o relatório de confiança mostra o que mudou. Mudanças de campo avaliado ou de escopo não apagam o que
  foi investigado, e a prévia da triagem usa só a KB (o corte não oscila com a investigação).
- **Verificação independente:** outro modelo reavalia às cegas 100% dos eliminatórios do foco, 100% das respostas
  plenas do proponente e uma amostra do restante; divergências vão para decisão humana e a concordância calibra o método.

## 7. Evidência
- Fatos e notas com **URL oficial + data**; fatos vencem e deixam o gate INDEFINIDO até revalidação.
- **Sem inflar matriz:** nada de "resolve com terceiro" sem evidência; preview não pontua como GA.
- Custo com list price/estimativa indicativa — nunca valor contratual inventado.
- **Alegações que decidem** (leitura de cláusula, gate, direcionamento, resposta negativa) ficam no registro de
  evidências do estudo com fonte, citação literal, confiança e impacto; fatos públicos reaproveitáveis vão para a KB.
- Cada estudo guarda **dossiês de evidências** (`00-projeto/evidencias/`) — retrato da KB na data de referência —
  para que a decisão continue auditável depois que a KB evoluir.
- No modo proponente, o **pente-fino automático** sinaliza respostas sem evidência, com URL genérica ou muito
  reutilizada e justificativa curta; a leitura de que a página sustenta a afirmação é humana.

## 8. Simplificado × completo
- **Núcleo (padrão):** RTM → gates → aderência/scorecard → relatórios, com dois checkpoints humanos (gates e ranking).
- **Módulos opcionais:** armadilhas e dúvidas, direcionamento, red team, plano de POC, respostas (proponente), pente-fino,
  roteiro de defesa, cases de referência (rubrica de maturidade), esforço de POC e custo de produção.
- **Sempre gerados:** análises internas (eliminatórios, ranking com duas lentes/sensibilidade/cenários, dúvidas internas)
  e o índice das entregas (`03-entregas/README-ENTREGAS.md`).

## 9. Ordem de operações
Extração → RTM → classificação/pesos → gates → notas (KB + ajustes) → ranking → registro de evidências e dossiês →
red team → narrativa → entregas.
Regenerar Excel/HTML somente com os artefatos de análise coerentes; a narrativa usa placeholders para nunca
divergir do cálculo.
