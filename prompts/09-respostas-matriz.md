# Prompt 09 — Respostas requisito a requisito (modo proponente)

**Objetivo:** responder a matriz do edital como proponente (`rfp.yaml → proponente`), com honestidade e evidência
oficial, no formato que o kit grava na planilha do próprio cliente.

**Preparação:** `python kit.py respostas "<pasta>"` cria/sincroniza `02-analise/respostas.json` com um item por
requisito da RTM. Cada item traz `escala` — os valores aceitos **naquela aba**, lidos do dropdown da planilha
(ex.: 4 níveis nos requisitos funcionais, 5 níveis nos dados quantitativos).

**Saída:** preencha em `02-analise/respostas.json`, por item:
```json
{"id": "RF-06", "resposta": "Atende Parcialmente",
 "justificativa": "Dynamic Thresholds reduzem alertas falsos com baseline aprendido; não há deduplicação equivalente a AIOps dedicado.",
 "evidencias": ["EV-AZ-003", "EV-AZ-004"], "metodo": "Configuração", "poc": false, "paginas": ""}
```
- `resposta`: exatamente um valor de `escala` (maiúsculas/acentos são normalizados para a grafia do dropdown).
- `justificativa`: obrigatória quando não for a resposta plena; recomendada sempre (como atende, com nomes de recursos).
- `evidencias`: ids da biblioteca `kb/evidencias/<proponente>.yaml` (preferencial) ou URLs oficiais. Na planilha,
  o kit escreve na coluna de observações: justificativa + `[Método: …]` + `[Comprovação em POC.]` + `Ref.: <urls>`.
- `metodo`: `Nativo` (padrão), `Configuração`, `Desenvolvimento`… — aparece na observação quando não for nativo.
- `poc`: `true` quando a comprovação ficará para a POC.
- `paginas`: referência às páginas da proposta, se a planilha tiver essa coluna.

**Evidências novas:** se nenhuma evidência da biblioteca sustentar a resposta, pesquise a documentação oficial e
acrescente uma entrada em `kb/evidencias/<proponente>.yaml` (prompt `kb-evidencias-fornecedor.md`) — capacidade
descrita de forma **genérica**, nunca com texto do requisito ou nome do cliente. A justificativa específica do
requisito fica só no `respostas.json` do cliente.

**Base obrigatória: a investigação.** Na execução assistida, a resposta de cada item parte da investigação do
proponente ([prompt 15](15-investigar-requisitos.md), `02-analise/investigacao.json`): o nível da resposta tem de ser o
mesmo `atendimento` investigado (o kit acusa ERRO quando divergem) e as evidências são as mesmas. Consulte
`02-analise/confianca.md`: **"Atende plenamente" só com confiança alta**; com confiança média, a resposta plena exige
encaminhamento (dúvida ao cliente, pergunta ao fabricante ou POC), e com confiança baixa ela é ERRO — rebaixe ou
encaminhe.

**Regras**
- Só recursos **GA com SLA**; preview é no máximo "parcial", declarado.
- "Parcial" só com base GA demonstrável; sem caminho oficial suportado = "Não Atende". Nunca "resolve com terceiro"
  sem evidência e sem estar na oferta.
- Consistência: a mesma capacidade recebe a mesma resposta em todos os itens.
- Trabalhe em lotes (por aba/módulo). Depois: `python kit.py respostas "<pasta>"` (grava a planilha **RESPONDIDA**,
  estende o dropdown às linhas respondidas, preserva imagens e confere célula a célula em
  `02-analise/verificacao-planilhas.md`), `python kit.py validar-urls "<pasta>"` e o pente-fino (prompt 10).
- Eliminatório com resposta parcial ou negativa é risco de desclassificação: ele aparece em
  `02-analise/cobertura-respostas.md`; trate na narrativa (Ressalvas), nas dúvidas e no roteiro de defesa (prompt 11).
