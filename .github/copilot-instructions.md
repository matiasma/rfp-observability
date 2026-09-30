# Instruções para o Copilot neste repositório

Este repositório é o **kit de análise de RFP de observabilidade** — genérico, compartilhado e **sem dados de cliente**.

## Ao analisar um edital
Siga a skill `.github/skills/analise-rfp-observabilidade/SKILL.md` e os prompts de `prompts/`. A análise de um
cliente acontece na pasta do cliente (`<pasta>/_analise-rfp/`), nunca dentro deste repositório.
Toda execução é **assistida** (seção 0 da skill): atualize a KB dos fornecedores do campo e o Gartner, revise todos
os requisitos (prompts/14) e transforme lacunas em perguntas de esclarecimento antes de gerar os entregáveis.

## Ao alterar o kit
- Nunca adicione nomes, trechos de edital ou contexto de clientes (código, KB, testes, exemplos, commits).
  O exemplo em `exemplos/cliente-exemplo/` é fictício e deve continuar assim.
- `kb/` só recebe informação pública de fabricantes, com `fonte` (URL oficial) e `verificado_em`. Em
  `kb/evidencias/` e `kb/cases/`, a capacidade/o case é descrito de forma genérica — a justificativa de cada
  requisito fica no `respostas.json` do cliente, e a relação de um case com o cliente e as alegações específicas do
  edital ficam em `cases-referencia.yaml` e `registro-evidencias.yaml` do estudo. Confirmações obtidas num edital
  nunca entram na KB.
- O código é determinístico; julgamento (gates, notas, eixos, narrativa) vive em arquivos de `02-analise/`
  com justificativa. Não embuta conclusões de um estudo no código ou nos templates.
- Termos de domínio em português (fornecedor, requisito, aderência); Python 3.10+.
- Nova regra de gate: `rfpkit/gates.py` (`REGRAS`) + `kb/gates-biblioteca.yaml` + teste em `tests/test_gates.py`.
- Antes de concluir: `python kit.py kb-validar` e `python -m pytest -q`.
