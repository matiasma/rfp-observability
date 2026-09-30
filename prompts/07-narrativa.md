# Prompt 07 — Narrativa do relatório

**Objetivo:** escrever o único texto livre que entra nos relatórios (HTML e MD), coerente com o cálculo.

**Entradas:** `02-analise/gates.json`, `ranking.json`, `selecao.json`, `00-projeto/premissas.md`, `rfp.yaml → cliente.contexto`, módulos opcionais já produzidos (armadilhas, red team).

**Saída:** `02-analise/narrativa.md` com estas seções (títulos `## `):
- `## Recomendação` — 2–4 frases: quem é recomendado, resultado no gate, aderência/nota final, principal ressalva. No modo proponente: mensagem principal do produto ofertado (vira o sumário executivo do memorial), cobertura das respostas e gaps honestos.
- `## Fatores estratégicos` — 3–6 bullets com o contexto do cliente que pesa na decisão (no modo proponente: diferenciais).
- `## Próximos passos` — 3–5 itens numerados (dúvidas, POC, fase comercial, due diligence).
- `## Ressalvas` — opcional: premissas frágeis, fatos a confirmar, lacunas assumidas.
- `## Arquitetura` — opcional (modo proponente): componentes da solução proposta; vira a seção de arquitetura do memorial técnico.
- `## Cenários` — opcional: cenários de decisão que o cálculo não cobre (ex.: "se residência de dados no Brasil virar
  mandatória…"); aparece depois da tabela automática de cenários de gate.
- `## Revisão crítica` — opcional: o que o red team mudou ou confirmou na conclusão (vai para o relatório executivo e o HTML).

**Placeholders (obrigatórios para números)** — o arquivo é um template Jinja2 renderizado com os dados:
- `{{ r['<id>'].aderencia_pct | br }}%`, `{{ r['<id>'].nota_final | br(2) }}`, `{{ r['<id>'].status_gate }}`, `{{ r['<id>'].gates_reprovados }}`, `{{ r['<id>'].gates_risco }}` — fornecedores da avaliação completa
- `{{ t['<id>'].status_gate }}`, `{{ t['<id>'].aderencia_previa_pct | br }}` — qualquer fornecedor da triagem
- `{{ melhor_elegivel.nome }}` (melhor que não reprova), `{{ melhor_merito.nome }}` (melhor nota final), `{{ edicao.ano }}`
- Leituras da decisão: `{{ nome_de(sens.robusto) }}` (1º robusto na sensibilidade), `{{ nome_de(lentes.lider_aderencia) }}`,
  `{{ lentes.aderencia_pct | br }}`, `{{ nome_de(lentes.lider_nota) }}`
- Modo proponente: `{{ proponente_nome }}`, `{{ cobertura.respondidos }}`, `{{ cobertura.total }}`,
  `{{ cobertura.por_resposta.get('<valor da escala>', 0) }}`, `{{ cobertura.eliminatorios_em_risco | length }}`
- Condicionais permitidas: `{% if melhor_elegivel %}…{% else %}…{% endif %}`

**Regras**
- Nunca digite percentuais/notas (a validação avisa). Nunca contradiga `gates.json` (ex.: chamar de "aprovado" quem está em RISCO).
- Tom executivo, frases curtas, sem marketing. "Não atende" e "reprova" ditos com clareza.
- Depois: `python kit.py tudo "<pasta>"` e confira o HTML (sem `⟨?⟩`).
