{# Exemplo FICTÍCIO no modo proponente: números e contagens vêm de placeholders (cobertura, r, t). #}

## Recomendação
O **{{ proponente_nome }}** responde aos {{ cobertura.respondidos }} itens da matriz com evidência na documentação
oficial da Microsoft: {{ cobertura.por_resposta.get('Atende Plenamente', 0) }} itens funcionais atendidos plenamente,
{{ cobertura.por_resposta.get('Atende Parcialmente', 0) }} parcialmente e {{ cobertura.por_resposta.get('Não Atende', 0) }}
não atendido, além dos dados quantitativos. Na triagem de gates do edital, o resultado é
**{{ t['azure-monitor'].status_gate }}**. A única lacuna assumida é o monitoramento de crashes de aplicativos móveis,
respondido com honestidade como "Não Atende".

## Fatores estratégicos
- OpenTelemetry nativo, serviço gerenciado para Prometheus e Managed Grafana: padrões abertos, sem agente proprietário obrigatório para aplicações.
- Segurança e privacidade: criptografia em trânsito e em repouso com chaves do cliente, Private Link e controle de acesso pelo Microsoft Entra ID.
- Região de dados no Brasil e SLA publicado de disponibilidade para Azure Monitor, Application Insights e Log Analytics.
- Integração nativa com ITSM e action groups para webhooks, Logic Apps e Functions.

## Arquitetura
- **Coleta:** Azure Monitor Agent nos hosts, Azure Monitor OpenTelemetry Distro nas aplicações e SDK JavaScript no front-end web.
- **Armazenamento e análise:** Log Analytics (KQL), Application Insights e serviço gerenciado para Prometheus.
- **Visualização e resposta:** Workbooks e Managed Grafana; alertas com Dynamic Thresholds e action groups para ITSM e automação.

## Ressalvas
- RF-04 (crashes de aplicativos móveis): Não Atende — não há SDK nativo nem caminho oficial suportado.
- RF-05, RF-06 e RF-12: atendimento parcial, com o limite de cada item descrito no memorial técnico.

## Próximos passos
1. Enviar o anexo de dúvidas (RUM mobile, retenção e live tail).
2. POC: correlação distribuída (RF-02), alertas com baseline (RF-06) e monitoramento de atualidade de tabelas (RF-12).
3. Fase comercial: estimar o TCO com commitment tier compatível com a volumetria informada.
