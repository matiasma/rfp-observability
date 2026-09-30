# Prompt 03 — Ajustar notas ao contexto do edital

**Objetivo:** ajustar as notas-base da KB quando o contexto **deste** cliente/edital muda a leitura da capacidade (ex.: stack de dados concentrada numa nuvem, exigência detalhada de um banco específico, legado).

**Entradas**
- `02-analise/ranking.json` (notas efetivas por fornecedor × categoria) e `00-projeto/categorias-pesos.json`
- `<KIT>/kb/fornecedores/<id>.yaml` (nota-base, `obs` e fontes)
- `rfp.yaml → cliente.contexto` e os requisitos da categoria em `00-projeto/rtm.csv`

**Saída:** `02-analise/ajustes-notas.yaml`

```yaml
- fornecedor: azure-monitor
  categoria: dados-pipelines
  nota: 0.4
  justificativa: "80% dos requisitos da categoria são de pipelines em outra nuvem; integração existe mas sem data quality/lineage nativos."
  fontes: ["https://learn.microsoft.com/..."]
```

**Regras**
- Ajuste apenas categorias com peso relevante e só quando o edital **muda** a leitura (não para "corrigir" a KB — isso se faz na KB, com fonte).
- Régua: 1,0 nativo-líder · 0,75 forte · 0,5 parcial/por extensão · 0,25 fraco · 0 não atende. Preview ≠ GA.
- `justificativa` e `fontes` (URLs oficiais) são obrigatórias — a validação acusa ERRO sem elas.
- Mesma régua para todos: se ajustar um fornecedor por um motivo, avalie o mesmo motivo nos demais.
- Depois: `python kit.py tudo "<pasta>"`.
