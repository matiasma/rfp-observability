"""Gera os documentos do edital FICTÍCIO usado como exemplo e teste do kit.

Uso: python exemplos/cliente-exemplo/gerar_exemplo.py [pasta-destino]
Cria: TR-Exemplo-Observabilidade.docx e Matriz-Requisitos-Exemplo.xlsx (nenhum dado real de cliente).
"""
import sys
from pathlib import Path

from docx import Document
from openpyxl import Workbook

TR = [
    ("h1", "1. OBJETO"),
    ("p", "Contratação de solução de observabilidade em modelo SaaS, pelo período de 36 meses, para os ambientes "
          "on-premises e em nuvem da Companhia Exemplo."),
    ("h1", "2. CRITÉRIOS DE QUALIFICAÇÃO TÉCNICA"),
    ("p", "2.1.1 O fabricante deverá estar posicionado como Líder no Quadrante Mágico do Gartner de Observability "
          "Platforms nos últimos 3 anos. Requisito eliminatório."),
    ("p", "2.1.2 A solução deverá possuir catálogo com mais de 500 integrações nativas, documentadas e suportadas "
          "pelo fabricante. Requisito eliminatório."),
    ("p", "2.1.3 O fabricante deverá oferecer suporte técnico local no Brasil, com atendimento em língua portuguesa. "
          "Requisito eliminatório."),
    ("p", "2.1.4 A solução SaaS deverá possuir SLA de disponibilidade publicado de no mínimo 99,5%. "
          "Requisito eliminatório."),
    ("h1", "3. ESPECIFICAÇÃO TÉCNICA"),
    ("h2", "3.1 Coleta de dados, agentes e integrações"),
    ("p", "3.1.1 A solução deverá coletar métricas, logs e traces por meio de agente único por host."),
    ("p", "3.1.2 A solução deverá ser compatível com OpenTelemetry para ingestão de traces, métricas e logs, sem "
          "exigir agente proprietário."),
    ("p", "3.1.3 O agente deverá suportar os seguintes sistemas operacionais:"),
    ("li", "Linux (RHEL, Ubuntu e Oracle Linux);"),
    ("li", "Windows Server 2016 ou superior;"),
    ("li", "IBM AIX 7.2 ou superior."),
    ("p", "3.1.4 A solução deverá reter métricas por no mínimo 13 meses."),
    ("h2", "3.2 Monitoramento de infraestrutura e Kubernetes"),
    ("p", "3.2.1 A solução deverá monitorar hosts físicos e virtuais VMware, com métricas de CPU, memória, disco e rede."),
    ("p", "3.2.2 A solução deverá monitorar clusters Kubernetes (AKS, EKS e GKE), incluindo pods, nós e eventos."),
    ("p", "3.2.3 A solução deverá monitorar dispositivos de rede via SNMP."),
    ("h2", "3.3 APM e tracing distribuído"),
    ("p", "3.3.1 A solução deverá prover APM com auto-instrumentação para Java, .NET, Node.js e Python."),
    ("p", "3.3.2 A solução deverá oferecer tracing distribuído fim a fim entre microsserviços."),
    ("p", "3.3.3 A solução deverá identificar exceções e erros em nível de código."),
    ("h2", "3.4 Gestão de logs"),
    ("p", "3.4.1 A solução deverá centralizar logs de aplicações e sistemas operacionais, com parsing e busca "
          "textual."),
    ("p", "3.4.2 A solução deverá permitir mascaramento de dados pessoais (PII) nos logs antes do armazenamento."),
    ("p", "3.4.3 A solução deverá permitir arquivamento e reidratação de logs."),
    ("h2", "3.5 Experiência do usuário"),
    ("p", "3.5.1 A solução deverá oferecer RUM para aplicações web, com Core Web Vitals."),
    ("p", "3.5.2 A solução deverá oferecer RUM para aplicativos móveis Android e iOS."),
    ("p", "3.5.3 É desejável que a solução ofereça session replay."),
    ("p", "3.5.4 A solução deverá executar testes sintéticos de APIs e de jornadas de navegador."),
    ("h2", "3.6 Banco de dados"),
    ("p", "3.6.1 A solução deverá monitorar SQL Server, Oracle e PostgreSQL, identificando consultas lentas e "
          "planos de execução."),
    ("h2", "3.7 Alertas, dashboards e SLOs"),
    ("p", "3.7.1 A solução deverá permitir a criação de dashboards e alertas com notificação por e-mail e "
          "Microsoft Teams."),
    ("p", "3.7.2 A solução deverá permitir definir SLOs com error budget e burn rate."),
    ("p", "3.7.3 A solução deverá detectar anomalias e sugerir causa raiz por meio de inteligência artificial."),
    ("h2", "3.8 Observabilidade de IA"),
    ("p", "3.8.1 A solução deverá monitorar aplicações baseadas em LLM, incluindo consumo de tokens, latência e "
          "custo por requisição."),
    ("h2", "3.9 Segurança, governança e LGPD"),
    ("p", "3.9.1 A solução deverá suportar SSO via SAML e controle de acesso baseado em perfis (RBAC)."),
    ("p", "3.9.2 A solução deverá manter trilha de auditoria das ações dos usuários."),
    ("p", "3.9.3 O fabricante deverá declarar conformidade com a LGPD."),
    ("h2", "3.10 Integração com ITSM"),
    ("p", "3.10.1 A solução deverá integrar-se ao ServiceNow para abertura automática de incidentes."),
    ("h1", "4. IMPLANTAÇÃO E SERVIÇOS"),
    ("p", "4.1.1 A contratada deverá realizar a implantação da solução em até 60 dias."),
    ("p", "4.1.2 A contratada deverá realizar treinamento para até 20 participantes."),
    ("p", "4.1.3 A contratada deverá prestar operação assistida por 90 dias após a implantação."),
    ("h1", "5. NÍVEIS DE SERVIÇO"),
    ("p", "5.1.1 Incidentes de severidade 1 deverão ser atendidos em até 1 hora, sob pena de glosa."),
    ("h1", "6. CONDIÇÕES COMERCIAIS"),
    ("p", "6.1.1 O pagamento deverá ser mensal, mediante apresentação de nota fiscal."),
    ("p", "6.1.2 O licenciamento deverá considerar a volumetria de 200 hosts e 500 GB/dia de logs."),
]

TABELA = [
    ["ID", "Requisito complementar", "Tipo"],
    ["RC-01", "Painéis executivos com visão de disponibilidade por serviço de negócio.", "Desejável"],
    ["RC-02", "Profiling contínuo de aplicações Java em produção.", "Desejável"],
    ["RC-03", "Monitoramento de pipelines de dados em Apache Airflow e Kafka.", "Desejável"],
]

MATRIZ = [
    ("RF-01", "APM", "Mapa de dependências entre serviços gerado automaticamente.", "Eliminatório"),
    ("RF-02", "APM", "Correlação automática entre traces, logs e métricas da mesma transação.", "Eliminatório"),
    ("RF-03", "RUM", "Captura de erros JavaScript e tempo de carregamento de páginas.", "Obrigatório"),
    ("RF-04", "RUM", "Monitoramento de crashes de aplicativos móveis.", "Obrigatório"),
    ("RF-05", "Logs", "Live tail de logs em tempo real.", "Desejável"),
    ("RF-06", "AIOps", "Redução de ruído e deduplicação de alertas.", "Obrigatório"),
    ("RF-07", "AIOps", "Assistente em linguagem natural para investigação de incidentes.", "Desejável"),
    ("RF-08", "Infraestrutura", "Monitoramento de funções serverless.", "Desejável"),
    ("RF-09", "Segurança", "Criptografia de dados em repouso e em trânsito.", "Eliminatório"),
    ("RF-10", "Integrações", "Envio de eventos para webhooks e API REST documentada.", "Obrigatório"),
    ("RF-11", "Plataforma", "Retenção configurável de dados por tipo de telemetria.", "Obrigatório"),
    ("RF-12", "Dados", "Monitoramento de qualidade e atualidade (freshness) de tabelas analíticas.", "Desejável"),
]

DADOS_QUANTITATIVOS = [
    ("DQ-1", "Infraestrutura", "Hosts monitorados simultaneamente", "200"),
    ("DQ-2", "Logs", "Ingestão diária de logs", "500 GB/dia"),
    ("DQ-3", "Métricas", "Retenção de métricas", "13 meses"),
]

ESCALA_4N = ["Atende Plenamente", "Atende Parcialmente", "Se propõe a desenvolver", "Não Atende"]
ESCALA_5N = ["Atendido Nativamente", "Atendido por Extensão", "Atendido Parcialmente", "Não Atendido", "Não Fornecido"]


def _logo():
    """Logotipo fictício (PNG em memória) para testar a preservação de imagens na planilha respondida."""
    import io

    from PIL import Image as PILImage, ImageDraw
    from openpyxl.drawing.image import Image

    img = PILImage.new("RGB", (160, 48), (31, 78, 120))
    ImageDraw.Draw(img).text((12, 16), "EXEMPLO S.A.", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf)


def _nome_definido(wb, nome, destino):
    from openpyxl.workbook.defined_name import DefinedName
    dn = DefinedName(nome, attr_text=destino)
    try:
        wb.defined_names[nome] = dn
    except TypeError:
        wb.defined_names.append(dn)


def gerar_matriz(caminho: Path):
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Requisitos Funcionais"
    ws["A1"] = "Matriz de Requisitos — Observabilidade (exemplo fictício)"
    ws.append([])
    ws.append(["ID", "Módulo", "Requisito", "Tipo", "Resposta do Fornecedor", "Justificativa"])
    for linha in MATRIZ:
        ws.append(list(linha) + ["", ""])
    ws.add_image(_logo(), "H1")

    cfg = wb.create_sheet("Config")
    cfg["A1"] = "ATRIBUIÇÃO DE ADERÊNCIA"
    for i, v in enumerate(ESCALA_4N, start=2):
        cfg.cell(row=i, column=1, value=v)
    cfg.sheet_state = "hidden"
    _nome_definido(wb, "listaAderencia", "Config!$A$2:$A$5")
    dv = DataValidation(type="list", formula1="listaAderencia", allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("E4:E10")  # dropdown propositalmente curto: o kit deve estendê-lo às linhas respondidas

    ws2 = wb.create_sheet("Dados Quantitativos", 1)
    ws2.append(["Referência", "Tipo", "Métrica", "Quantidade", "Avaliação", "Observações"])
    for linha in DADOS_QUANTITATIVOS:
        ws2.append(list(linha) + ["", ""])
    dv2 = DataValidation(type="list", formula1='"' + ",".join(ESCALA_5N) + '"', allow_blank=True)
    ws2.add_data_validation(dv2)
    dv2.add("E2:E4")
    wb.save(str(caminho))


def gerar_modelo_duvidas(caminho: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Instruções"
    ws["A1"] = "Preencha a aba Dúvidas com uma pergunta por linha."
    ws2 = wb.create_sheet("Dúvidas")
    ws2["B1"] = "Dúvidas do PARTICIPANTE"
    ws2.append(["Identificador", "Nome do anexo", "Página/Aba", "Classificação", "Dúvida/Pergunta",
                "Resposta do cliente", "Status"])
    for i in range(1, 11):
        texto = "Preencha a coluna com a dúvida" if i == 1 else ""
        ws2.append([f"DUV-{i:03d}", "", "", "", texto, "", "PENDENTE"])
    wb.save(str(caminho))


def gerar(destino: Path):
    destino.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.core_properties.author = "kit-rfp-observabilidade"
    doc.add_heading("TERMO DE REFERÊNCIA — SOLUÇÃO DE OBSERVABILIDADE (EXEMPLO FICTÍCIO)", level=0)
    for tipo, texto in TR:
        if tipo == "h1":
            doc.add_heading(texto, level=1)
        elif tipo == "h2":
            doc.add_heading(texto, level=2)
        elif tipo == "li":
            doc.add_paragraph(texto, style="List Bullet")
        else:
            doc.add_paragraph(texto)
    doc.add_heading("7. REQUISITOS COMPLEMENTARES", level=1)
    tabela = doc.add_table(rows=len(TABELA), cols=3)
    for i, linha in enumerate(TABELA):
        for j, valor in enumerate(linha):
            tabela.cell(i, j).text = valor
    doc.save(str(destino / "TR-Exemplo-Observabilidade.docx"))
    gerar_matriz(destino / "Matriz-Requisitos-Exemplo.xlsx")
    gerar_modelo_duvidas(destino / "Anexo-Duvidas-Exemplo.xlsx")
    return destino


if __name__ == "__main__":
    if len(sys.argv) > 1:
        alvos = [Path(sys.argv[1])]
    else:
        base = Path(__file__).resolve().parent
        alvos = [base, base.parent / "cliente-exemplo-proponente"]
    for alvo in alvos:
        print(f"Documentos de exemplo gerados em {gerar(alvo)}")
