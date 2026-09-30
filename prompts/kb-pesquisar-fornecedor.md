# Prompt KB — Pesquisar/atualizar a ficha de um fornecedor

**Quando:** fornecedor novo (`kit.py kb-novo <id>`), fato vencido/sem data (`kit.py kb-status`) ou um gate
INDEFINIDO no `validacao.md` de um edital que dependa de fato sem evidência pública na KB.
**O quê:** só evidência **pública** oficial. Resposta do fabricante obtida para um edital específico não entra
aqui — vai para `02-analise/gates-override.yaml` do estudo daquele cliente.
**Como:** um subagente de pesquisa por fornecedor, em paralelo. Cole o conteúdo abaixo, trocando `<FORNECEDOR>` e `<id>`.

---

Pesquise o fornecedor de observabilidade **<FORNECEDOR>** para a base de conhecimento (KB) do kit de análise de RFP. Data de hoje: <AAAA-MM-DD>.

Use SOMENTE fontes oficiais/públicas do fabricante (documentação, páginas legais/SLA, trust center, blog/press oficial, GitHub do fabricante). Todo fato deve citar a URL oficial exata verificada; se não conseguir verificar, `valor: null` (nunca chute).

Devolva UM documento YAML válido num bloco ```yaml, exatamente no esquema de `kb/fornecedores/_modelo.yaml` (mesmas chaves e enumerações), com `id: <id>`, `atualizado_em` e `verificado_em` = data de hoje. Verifique em especial:
- integrações nativas (número oficial; `qualificador: "mais de"` se a fonte disser "more than N");
- SLA de disponibilidade publicado do SaaS (%); região de dados no Brasil (SIM | NAO | NAO_CONFIRMADO);
- suporte local em português (SIM | NAO | NAO_DOCUMENTADO); agente open source/auditável (licença + GitHub);
- OpenTelemetry nativo; retenção máxima de métricas (meses) e se é em granularidade integral;
- SOs com agente (linux, windows, macos, aix, solaris, hpux, zos, arm); opção self-managed;
- RUM mobile nativo; session replay GA; certificações (ISO27001, SOC2, …).

Notas-base (`notas_base`): as 15 categorias de produto de `kb/taxonomia.yaml`, régua 1.0 nativo-líder · 0.75 forte · 0.5 parcial/por extensão · 0.25 fraco · 0 não atende (múltiplos de 0.05), `obs` curta em português e 1–3 URLs oficiais. Preview não conta como GA.
`destaques` e `gaps`: 3–6 frases curtas e honestas, em português. `confianca`: Alta | Média | Baixa.
NÃO inclua posição no Gartner MQ (fica em `kb/gartner-mq.yaml`) nem qualquer informação de cliente.
Depois do bloco YAML, liste em até 5 linhas o que não foi possível verificar.

---

**Depois:** grave o YAML em `kb/fornecedores/<id>.yaml`, rode `python kit.py kb-validar` (0 erros) e `python -m pytest tests/test_kb.py`.
