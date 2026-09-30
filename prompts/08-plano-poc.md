# Prompt 08 — Plano de POC/POV (módulo `poc`)

**Objetivo:** planejar a prova de conceito focada no que decide o resultado.

**Entradas:** cláusula de POC/POV do edital (`01-extracao/`), `00-projeto/categorias-pesos.json`, `02-analise/gates.json` (gates em RISCO/INDEFINIDO), `rtm.csv`, `rfp.yaml → cliente.contexto`.

**Saída:** `02-analise/plano-poc.md` (modelo já criado pelo kit): objetivo e critério de aprovação; casos de teste priorizados (maiores pesos + gates em risco + diferenciais), cada um com ids da RTM e evidência esperada; pré-requisitos do cliente; cronograma; riscos.

**Regras:** respeite prazo e formato da cláusula de POC do edital; um caso por grande bloco/seção contratável; evidência demonstrável (tela, consulta, alerta disparado), nunca slide.
