# Prompt 16 — Verificação independente (segundo agente, outro modelo)

**Objetivo:** reavaliar, **sem ver a conclusão da investigação**, uma amostra das avaliações requisito × fornecedor e
dizer se as evidências citadas sustentam o atendimento. O kit compara com a primeira conclusão; divergência rebaixa a
confiança até uma decisão humana.

**Como (pela skill, no VS Code)**
1. `python kit.py verificar-independente "<pasta>"` escolhe a amostra (100% dos eliminatórios do proponente ou dos 3
   primeiros do ranking, 100% das respostas plenas do proponente e uma parcela aleatória do restante) e gera
   `02-analise/verificacao-independente/lote-NN.json`.
2. Um subagente por lote, **com um modelo diferente do usado na investigação**.
3. `python kit.py verificar-independente "<pasta>" --consolidar`.
4. Divergências: apresente cada uma ao usuário (ferramenta de perguntas) e registre em
   `02-analise/verificacao-independente.json` a `resolucao`: `manter` (com `resolucao_obs` explicando por que a
   primeira conclusão fica) ou `corrigir` (refaça a investigação do item; a verificação volta para a fila).
   A verificação vale enquanto a conclusão verificada (atendimento + evidências) não mudar — mesmo que o item saia da
   amostra (`na_amostra: false`); se a conclusão mudar ou sumir (item reaberto), ela fica `suspensa` (não conta) e
   volta a valer, com a decisão registrada, se a mesma conclusão voltar.

**Para cada item do lote (você vê só o requisito, o entendimento, os parâmetros e as evidências citadas)**

| Campo | O que escrever |
|---|---|
| `atendimento` | sua conclusão independente: `pleno` · `parcial` · `nao` · `na` |
| `confere_evidencia` | `sim` (as citações/páginas sustentam integralmente) · `parcial` · `nao` |
| `obs` | o que falta ou diverge, em uma frase |
| `modelo` | o modelo que fez esta verificação |
| `verificado` | `true` |

**Regras:** abra as páginas citadas (use o navegador do VS Code se necessário) e confira as citações literalmente;
não pesquise para "salvar" a conclusão — o que não estiver nas evidências citadas não conta; seja cético com
marketing, preview e documentação de outra edição/versão do produto.
