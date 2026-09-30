# Prompt KB — Registrar nova edição do Gartner Magic Quadrant

**Quando:** em toda execução assistida, confira se saiu edição mais nova que a última de `kb/gartner-mq.yaml` (busca rápida por "Magic Quadrant for Observability Platforms <ano>"). Se não saiu, só atualize `revisado_em` para a data de hoje. Se saiu (normalmente em julho), registre-a com o bloco abaixo.

---

Liste os fornecedores de cada quadrante do Gartner *Magic Quadrant for Observability Platforms* **<ANO>**. Hoje: <AAAA-MM-DD>.
Use fontes que listem os fornecedores: gráfico oficial republicado por fornecedores, comunicados de imprensa dos fabricantes, imprensa especializada (Network World, APMdigest etc.). Confira a contagem total de fornecedores quando publicada.
Use os ids de `kb/fornecedores/*.yaml` e de `kb/gartner-mq.yaml` (Microsoft = `azure-monitor`, IBM = `ibm-instana`, Cisco/Splunk = `splunk`); kebab-case para os demais.
Devolva UM bloco ```yaml:

```yaml
- ano: <ANO>
  titulo: "Magic Quadrant for Observability Platforms"
  data_publicacao: AAAA-MM-DD
  confianca: Alta            # Alta = lista completa confirmada; Média = parcial/inferida
  fontes: [<url>, <url>]
  quadrantes:
    lider: [...]
    desafiante: [...]
    visionario: [...]
    nicho: [...]
  obs: "<dúvidas e mudanças vs. ano anterior>"
```

---

**Depois:** insira a edição no topo de `edicoes:` em `kb/gartner-mq.yaml`, atualize `revisado_em`, rode `python kit.py kb-validar` e `python kit.py kb-status` (mostra os Líderes vigentes). Crie fichas (`kit.py kb-novo`) para novos Líderes que ainda não existirem na KB.
