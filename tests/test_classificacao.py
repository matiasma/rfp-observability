import pytest

from rfpkit.classificacao import NAO_CLASSIFICADO, Classificador
from rfpkit.kb import KB


@pytest.fixture(scope="module")
def clf():
    return Classificador(KB().taxonomia)


@pytest.mark.parametrize("texto,bloco,esperado", [
    ("A solução deverá monitorar clusters Kubernetes, incluindo pods e nós.", "", "infraestrutura"),
    ("A solução deverá oferecer tracing distribuído entre microsserviços.", "", "apm"),
    ("Mascaramento de PII nos logs antes do armazenamento.", "", "logs"),
    ("Monitorar consultas lentas e planos de execução no SQL Server.", "", "banco-dados"),
    ("Session replay para aplicativos móveis Android e iOS.", "", "experiencia-usuario"),
    ("Monitorar consumo de tokens e alucinações de aplicações LLM.", "", "ia-llm"),
    ("Integração com ServiceNow para abertura automática de chamados.", "", "integracoes-itsm"),
    ("Qualquer texto", "Observabilidade de dados e pipelines", "dados-pipelines"),
])
def test_categoria(clf, texto, bloco, esperado):
    assert clf.categoria(texto, bloco)[0] == esperado


def test_palavra_curta_casa_so_palavra_inteira(clf):
    # "rum" não pode casar "rumor"; "log" não pode casar "logística"
    assert clf.categoria("Rever o rumor sobre a logística do projeto.")[0] == NAO_CLASSIFICADO


def test_mapa_de_blocos_prevalece():
    clf = Classificador(KB().taxonomia, {"Seção de dados": "dados-pipelines"})
    assert clf.categoria("Dashboards de APM", "1.2 Seção de Dados — requisitos")[:3] == ("dados-pipelines", 1.0, "mapa-blocos")


@pytest.mark.parametrize("texto,explicito,esperado", [
    ("A solução deverá suportar SSO.", "", "obrigatorio"),
    ("É desejável que a solução ofereça session replay.", "", "desejavel"),
    ("Requisito eliminatório: SLA de 99,8%.", "", "eliminatorio"),
    ("Monitoramento de filas", "Eliminatório", "eliminatorio"),
    ("A solução deverá suportar SSO.", "Desejável", "desejavel"),
    ("A solução deverá permitir dashboards que poderão ser compartilhados.", "", "obrigatorio"),
    ("A contratada poderá propor ferramentas complementares.", "", "desejavel"),
    ("Monitoramento de filas", " 2. Desejável \n (Should Have)", "desejavel"),
])
def test_obrigatoriedade(clf, texto, explicito, esperado):
    assert clf.obrigatoriedade(texto, explicito) == esperado


@pytest.mark.parametrize("texto,bloco,dica,esperado", [
    ("A contratada deverá realizar treinamento.", "", "", "implantacao"),
    ("O pagamento será mensal.", "", "", "comercial"),
    ("A solução deverá monitorar hosts.", "", "Requisitos Comerciais", "comercial"),
    ("O fabricante deverá apresentar atestado de capacidade técnica.", "", "", "qualificacao"),
    ("A solução deverá monitorar hosts.", "", "", "tecnico"),
    ("A solução deverá monitorar hosts.", "", "processo", "processo"),               # natureza explícita
    ("Relatório mensal com posição no Gartner.", "", "tecnico", "tecnico"),         # explícita vence o texto
])
def test_natureza(clf, texto, bloco, dica, esperado):
    assert clf.natureza(texto, bloco, dica) == esperado
