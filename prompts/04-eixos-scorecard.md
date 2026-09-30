# Prompt 04 — Eixos do scorecard (risco, esforço, custo, estratégico)

**Objetivo:** atribuir notas 0–5 aos eixos não calculados, para os fornecedores da **avaliação completa**.

**Entradas**
- `02-analise/selecao.json` (quem está na avaliação completa) e `02-analise/gates.json`
- `rfp.yaml → cliente.contexto`, volumetria do edital (em `01-extracao/`)
- `<KIT>/kb/fornecedores/<id>.yaml` (destaques, gaps, entrega, região, suporte)

**Saída:** `02-analise/eixos.yaml`

```yaml
datadog:
  risco: 3.4
  esforco: 4.5
  custo: 2.6
  estrategico: 3.6
  justificativa:
    risco: "Gate G3 em RISCO (suporte PT-BR não documentado); sem região de dados no Brasil."
    esforco: "Agente único, integrações prontas; POC de 15 dias viável."
    custo: "List price premium para a volumetria do edital (estimativa indicativa)."
    estrategico: "OTel e ecossistema amplo; aderente à nuvem principal do cliente."
```

**Escala (0–5, maior = melhor para o cliente)**
- **risco:** 5 = baixíssimo (gates PASSA, fornecedor sólido, presença no Brasil, sem lock-in crítico); 0 = crítico.
- **esforco:** 5 = implantação/POC simples e rápida; 0 = montagem pesada (muitos componentes/integrador).
- **custo:** 5 = TCO indicativo mais baixo do campo; 0 = mais caro. Use list price/estimativa pública — **nunca invente valor contratual**; diga a base na justificativa.
- **estrategico:** 5 = máximo alinhamento ao contexto do cliente (nuvem, OSS/OTel, soberania/LGPD, roadmap, suporte local).

**Regras:** justificativa curta e factual por eixo; notas relativas entre os fornecedores do campo; não use eixos para "compensar" gate reprovado.
Se o estudo tiver `esforco-poc.yaml`/`custo.yaml` (**prompts/13-esforco-custo.md**), derive `esforco` e `custo` deles
(menos dias / menor custo mensal → nota maior) e cite os números na justificativa; o kit avisa quando divergem. Depois
confira `02-analise/ranking.md` (seção Sensibilidade): se o 1º mudar com pequenas variações de peso, diga isso na narrativa.
