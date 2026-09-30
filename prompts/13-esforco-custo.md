# Prompt 13 — Esforço de POC e estimativa de custo (módulos `esforco` e `custo`)

**Objetivo:** quantificar o esforço de POC por fornecedor e estimar o custo recorrente de produção a preço de tabela,
para a leitura "esforço × custo" e para dar base aos eixos `esforco` e `custo` do scorecard.

**Entradas:** seção de POC/prova de conceito do edital em `01-extracao/` (frentes e critérios de aceite), volumetria do
edital (hosts, GB/dia, sessões, usuários), `02-analise/ranking.json` (avaliação completa), fichas da KB e páginas de
preço **públicas e oficiais** de cada fornecedor.

**Saídas**
- `02-analise/esforco-poc.yaml` (modelo criado pelo kit): uma `frente` por bloco da POC do edital, com `dias`
  [mín, máx] por fornecedor (1 pessoa, dias úteis), `portao: true` nas frentes cujo critério de aceite é de alto
  risco, `obs` explicando a diferença, e `risco` (baixo/medio/alto + motivo) de reprovar na POC.
- `02-analise/custo.yaml`: `cenario` de referência (derivado da volumetria do edital; se o edital não trouxer, declare
  as premissas), e por fornecedor o `modelo_cobranca` e os `componentes` com `quantidade` × `preco_unitario` (ou `valor`
  mensal pronto), cada um com `fonte` (URL oficial da página de preço ou calculadora/API de preços) e `verificado_em`.
  Use faixas [mín, máx] quando o preço depende de plano ou compromisso; registre em `ressalva` o que o custo NÃO cobre
  (ex.: capacidade que o produto não tem).

**Regras**
- Preço de tabela público, sem desconto e sem cotação privada; nunca invente preço. Sem fonte → não inclua o componente
  e diga o que falta. Cópias arquivadas (web.archive.org) só quando a página oficial não mostra o preço sem login.
- Mesma volumetria para todos os fornecedores; mesma unidade de esforço (1 pessoa, dias úteis).
- Estimativa indicativa: não vai para o cliente no modo proponente (fase técnica) e não substitui a proposta comercial.
- Depois ajuste os eixos `esforco` e `custo` em `eixos.yaml` (menos esforço/menor custo → nota maior); o kit avisa em
  `validacao.md` quando os eixos contradizem as estimativas. Rode `python kit.py tudo "<pasta>" --urls` (as URLs de
  preço também são verificadas).
