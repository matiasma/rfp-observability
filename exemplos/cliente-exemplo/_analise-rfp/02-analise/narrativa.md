{# Exemplo FICTÍCIO: a narrativa usa placeholders e condicionais Jinja2 para nunca divergir do cálculo. #}

## Recomendação
{% if melhor_elegivel %}
**{{ melhor_elegivel.nome }}** é o fornecedor mais bem ranqueado entre os que não reprovam nos gates eliminatórios
(resultado **{{ melhor_elegivel.status_gate }}**; aderência {{ melhor_elegivel.aderencia_pct | br }}%, nota final
{{ melhor_elegivel.nota_final | br(2) }} de 5){% if melhor_elegivel.gates_risco != '-' %}. Os gates em risco
({{ melhor_elegivel.gates_risco }}) precisam de confirmação por escrito antes da decisão{% endif %}.
{% else %}
Nenhum fornecedor passa em todos os gates eliminatórios sob leitura estrita; o melhor por mérito é
**{{ melhor_merito.nome }}** (aderência {{ melhor_merito.aderencia_pct | br }}%). Antes de decidir, submeter dúvidas
para estabilizar a leitura dos gates.
{% endif %}
O Azure Monitor, avaliado por diretriz, tem aderência de {{ r['azure-monitor'].aderencia_pct | br }}% e resultado
**{{ r['azure-monitor'].status_gate }}** na triagem{% if r['azure-monitor'].gates_reprovados != '-' %} (reprova em {{ r['azure-monitor'].gates_reprovados }}){% endif %}.

## Fatores estratégicos
- Parque com IBM AIX: a cobertura de sistemas operacionais (G5) separa os fornecedores, embora não seja eliminatória.
- App móvel próprio: RUM mobile nativo pesa na categoria de experiência do usuário.
- LGPD: mascaramento de PII em logs e trilha de auditoria são obrigatórios.
- Integração com ServiceNow e Microsoft Teams é obrigatória no fluxo de incidentes.

## Próximos passos
1. Submeter dúvida sobre o critério Gartner (G1): o Quadrante foi renomeado para Observability Platforms em 2024.
2. Confirmar por escrito os fatos em RISCO ou INDEFINIDO na triagem (ver Metodologia e fontes).
3. Preparar a POC com APM e correlação, RUM mobile e ingestão OpenTelemetry.
4. Fase comercial: modelar o TCO de 36 meses com a volumetria do edital.

## Ressalvas
- Exemplo fictício: os eixos de risco, esforço, custo e estratégico são ilustrativos.
