# Prompt 12 — Cases e arquiteturas de referência (módulo `cases`)

**Objetivo:** selecionar casos públicos e arquiteturas de referência oficiais do proponente que se pareçam com o
cenário do cliente (setor, escala, picos, tecnologias), para o Anexo B do memorial e para a argumentação.

**Entradas:** `rfp.yaml → cliente.contexto` e setor; categorias de maior peso (`00-projeto/categorias-pesos.json`);
biblioteca pública `kb/cases/<proponente>.yaml` (cases e arquiteturas já verificados).

**Saída:** `02-analise/cases-referencia.yaml` (modelo criado pelo kit com o módulo `cases`), 3–6 itens.
Primeiro reaproveite a KB — só a `relacao` com este cliente é escrita aqui:
```yaml
- kb: REF-AZ-002
  relacao: "Mesmo setor e mesmo padrão de pico sazonal do cliente."
  pontuacao: {solucao: 3.5, setor: 2.5, escala: 1.5, capacidades: 1}
```
Pontue cada case na **rubrica de maturidade (0–10)**: `solucao` 0–4 (o produto do proponente é a solução principal —
verifique pelo conteúdo, não pelo título), `setor` 0–3 (setor/cenário do cliente), `escala` 0–1,5 (escala e picos),
`capacidades` 0–1,5 (capacidades pedidas no edital). O kit ordena os cases por nota no memorial e em
`02-analise/cases-referencia-maturidade.md`.
Se nada na KB servir, pesquise e **cadastre primeiro na KB** (é público e reaproveitável), no formato de
`kb/cases/_modelo.yaml`:
```yaml
- id: REF-AZ-0nn
  tipo: case                     # case | arquitetura
  organizacao: "Nome publicado no case"
  setor: "Varejo"
  pais: "Brasil"
  cenario: "Observabilidade de e-commerce com APM e RUM"
  resultados: ["Resultado conforme publicado (sem extrapolar)"]
  solucao: "Produtos usados"
  url: "https://<página oficial do case>"
  fonte: "Customer story (data)"
  publicado_em: 2025-01-01
  palavras_chave: ["application insights"]
  status: A_VALIDAR
  verificado_em: null
```

**Regras:** só casos **publicados** pelo fabricante ou pelo próprio cliente do case (customer stories, notícias
oficiais, blog oficial) e arquiteturas oficiais (Architecture Center, Well-Architected); nunca casos internos, sob
NDA ou de outros editais; resultados copiados do texto publicado; prefira casos recentes e do mesmo setor/país.
Página original fora do ar → cópia do Internet Archive, registrada em `observacao`. Depois:
`python kit.py kb-validar-urls --fornecedor <id> --atualizar` (KB) e `python kit.py validar-urls "<pasta>"` (estudo).
