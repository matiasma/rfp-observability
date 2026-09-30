# Prompt 05 — Armadilhas do edital, dúvidas e direcionamento (módulos `armadilhas` / `direcionamento`)

**Objetivo:** mapear cláusulas capciosas, ambíguas ou direcionadas que decidem o resultado e redigir as dúvidas a submeter ao cliente.

**Entradas:** `01-extracao/*.md`, `rfp.yaml` (gates), `02-analise/gates.json`, `02-analise/ranking.json`, `00-projeto/premissas.md`.

**Saídas**
- `02-analise/armadilhas-duvidas.md` (modelo já criado pelo kit): uma seção `A<n>` por armadilha com **onde** (citação curta + item), **por que é armadilha**, **quem afeta** (use os vereditos do gates.json), **como tratar**; e o mapa interno das dúvidas.
- `02-analise/duvidas.yaml` — **fonte do anexo enviável**: um item por dúvida com `id`, `documento`, `referencia`
  (página/aba/item), `tema`, `pergunta` (texto pronto para envio), e os campos internos `objetivo` (por que
  perguntamos), `resposta_desejada`, `impacto`, `gates` (ids que a resposta pode reabrir), `prioridade`, `status`
  e `enviar` (false = retirada, com `motivo_retirada`). Os internos alimentam `02-analise/duvidas-interna.md`. Se o edital tiver modelo próprio de envio (`rfp.yaml → duvidas.modelo`, detectado no `init` pelo nome do
  arquivo), use o formato de id do modelo (ex.: `DUV-001`) e numeração contígua. Depois:
  `python kit.py duvidas "<pasta>"` gera `03-entregas/duvidas-<sigla>.xlsx` e a cópia **PREENCHIDO** do modelo.
- `02-analise/direcionamento.md` (se o módulo estiver ativo): sinais de direcionamento (cláusula → fornecedor favorecido), narrativa provável de cada concorrente e implicações.
- `02-analise/registro-evidencias.yaml`: uma alegação por armadilha/direcionamento que sustenta decisão (ex.: "a
  cláusula 2.1.2 reproduz a documentação do fornecedor X"), com `fonte` (`edital: <arquivo> <item>` e/ou URL oficial
  do fornecedor), `citacoes` literais dos dois lados, `confianca` e `impacto`. Se a comparação usar uma evidência
  pública reaproveitável, cadastre-a em `kb/evidencias/<fornecedor>.yaml` e aponte com `kb: EV-…`.

**O que procurar**
- Gates que só um fabricante atende (número "redondo" de integrações, SLA acima do publicado pelos demais, certificação específica).
- Nome desatualizado de relatório de analista (Gartner "APM and Observability" → "Observability Platforms").
- Termos sem definição ("integração nativa", "tempo real", "granularidade integral").
- Exigências caras ao pé da letra (retenção longa sem downsampling, SO legado como AIX) sem volumetria correspondente.
- Contradições entre documentos (TR × matriz × termo de referência × anexos).

**Regras:** dúvidas neutras e objetivas (não revelar estratégia); priorize as que mudam o resultado do gate; não envie nada ao cliente — é artefato interno.
