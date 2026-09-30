{#
Narrativa do estudo — é o ÚNICO texto livre que entra nos relatórios (HTML e MD).
Gerada pelo analista/LLM a partir de 02-analise/gates.json e ranking.json (ver prompts/07-narrativa.md).
Este bloco entre chaves-cerquilha é comentário do Jinja2 e não aparece no relatório.

REGRA DE OURO: nunca digite números. Use placeholders, calculados na hora de gerar o relatório:
  {{ r['datadog'].aderencia_pct | br }}%      -> aderência ponderada (ex.: 92,9%)
  {{ r['datadog'].nota_final | br(2) }}       -> nota final (0–5)
  {{ r['datadog'].status_gate }}              -> PASSA | RISCO | REPROVA
  {{ melhor_elegivel.nome }} / {{ melhor_merito.nome }}
  {{ t['azure-monitor'].status_gate }}        -> resultado de triagem de qualquer fornecedor da triagem
  {{ edicao.ano }}                            -> edição do Gartner MQ usada
Ids válidos: os de kb/fornecedores (r = avaliação completa; t = triagem).
Mantenha os títulos "## ..." abaixo: eles viram as seções do relatório. Comentários HTML são ignorados.
#}

## Recomendação
<!-- 2–4 frases: fornecedor recomendado, por que passa no gate, aderência/nota final (placeholders), principal ressalva. -->

## Fatores estratégicos
<!-- 3–6 bullets: contexto do cliente que pesa na decisão (nuvem principal, soberania/LGPD, OSS/OTel, custo, legado). -->

## Próximos passos
<!-- 3–5 itens numerados: dúvidas a submeter, POC/POV, fase comercial, due diligence. -->

## Ressalvas
<!-- Opcional: premissas frágeis, gates dependentes de interpretação, fatos a confirmar por escrito. -->
