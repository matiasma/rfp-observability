# Prompt 10 — Pente-fino de evidências (antes de submeter)

**Objetivo:** garantir que cada resposta é verdadeira, sustentada por documentação oficial viva e coerente com as demais.

**Pré-requisitos:** `python kit.py respostas "<pasta>"`, `python kit.py validar-urls "<pasta>"` e `python kit.py validar "<pasta>"`.

**Entradas:** `02-analise/respostas.json`, `02-analise/validacao.md` (seções respostas/urls — o kit já aponta:
evidência inexistente, resposta fora da escala, resposta plena/parcial sem evidência, linguagem de marketing,
preview em resposta plena, URL quebrada, página sem as palavras-chave), `02-analise/pente-fino-automatico.md`
(sinais por item: sem evidência, URL genérica, reuso alto da mesma URL, justificativa curta, marketing, preview,
evidência não validada, resposta plena com evidência não GA), `02-analise/validacao-urls.md`,
`00-projeto/evidencias/biblioteca-<proponente>.md` e `kb/evidencias/<proponente>.yaml`.

**Saída:** `02-analise/pente-fino-evidencias.md` (modelo criado pelo kit com o módulo `pente_fino`) e as correções
aplicadas no `respostas.json` (ou na biblioteca de evidências, se o problema for da evidência).

**Checklist**
1. Zerar todos os ERROS da validação; tratar todos os AVISOS de respostas/urls.
2. Para cada eliminatório: a evidência citada realmente afirma o que a justificativa diz? (abra a página).
3. Itens com `url_generica` ou `reuso_url`: troque pela página que sustenta a afirmação específica (crie a evidência
   na KB com **prompts/kb-evidencias-fornecedor.md** se faltar); itens com `justificativa_curta`: diga o recurso,
   como atende e o limite.
4. Respostas plenas que dependem de configuração/desenvolvimento → marcar `metodo` e, se preciso, rebaixar.
5. Mesma capacidade com respostas diferentes → alinhar.
6. Nada de roadmap não público, preview, ou componentes fora da oferta.
7. Respostas negativas ou parciais relevantes (eliminatórios, itens de peso): registrar a alegação que as sustenta em
   `02-analise/registro-evidencias.yaml` (com citação literal) — é o que será questionado na defesa.
8. Tom: factual, sem superlativos; nomes de recursos oficiais.
9. Rodar de novo `respostas`, `validar-urls` e `validar` até 0 erros.
