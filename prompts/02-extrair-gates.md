# Prompt 02 — Extrair os gates (critérios eliminatórios) do edital

**Objetivo:** transformar as cláusulas eliminatórias/de habilitação do edital em gates avaliáveis no `rfp.yaml`.

**Entradas**
- `<pasta>/_analise-rfp/01-extracao/*.md` (procure: "eliminatório", "desclassifica", "habilitação", "qualificação técnica", "Gartner", "Quadrante", "integrações", "SLA", "disponibilidade", "suporte", "português", "open source", "OpenTelemetry", "retenção", "AIX", "território nacional", "certificação")
- `00-projeto/rtm.csv` (coluna `obrigatoriedade = eliminatorio` e `natureza = qualificacao`)
- `<KIT>/kb/gates-biblioteca.yaml` (regras disponíveis e parâmetros)

**Saída:** a seção `gates:` do `rfp.yaml`, um item por cláusula:

```yaml
gates:
  - id: G1
    regra: gartner_lider
    params: {anos: 3, consecutivos: true}
    clausula: "<transcrição literal e curta da cláusula, com item do edital>"
    eliminatorio: true
```

**Regras**
- **Transcreva** a cláusula (não parafraseie) — ela aparece no relatório.
- `eliminatorio: true` só para knock-out explícito (ou critério de habilitação do fabricante). Requisitos técnicos críticos que não desclassificam → `eliminatorio: false` (aparecem como contexto).
- Mapeie para a regra mais específica; sem regra adequada → `regra: manual` + veredito por fornecedor em `02-analise/gates-override.yaml` (com justificativa).
- "Mais de N" → `estrito: true`; "no mínimo N" → `estrito: false`.
- Cláusula ambígua (ex.: cita o nome antigo do Gartner MQ, "integração nativa" sem definição, residência de dados implícita) → registre como dúvida (prompt 05) e mantenha leitura estrita.
- Não crie gate para o que o edital não exige (ex.: residência no Brasil quando só pede suporte em português).

**Checkpoint:** mostre ao usuário a tabela `id | cláusula | regra | eliminatório` e peça confirmação antes de seguir.
