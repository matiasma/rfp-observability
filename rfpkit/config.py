import copy
import datetime as dt
from pathlib import Path

from . import util

KIT_HOME = Path(__file__).resolve().parent.parent
KB_DIR = KIT_HOME / "kb"
TEMPLATES_DIR = KIT_HOME / "templates"
PASTA_ANALISE = "_analise-rfp"

MODOS = ("neutro", "proponente")
EIXOS_PADRAO = {"aderencia": 35, "risco": 20, "esforco": 15, "custo": 20, "estrategico": 10}

DEFAULTS = {
    "cliente": {"nome": "Cliente", "sigla": "CLIENTE", "setor": "", "contexto": []},
    "idioma": "pt-BR",
    "data_referencia": None,
    "modo": "neutro",
    "proponente": None,
    "entradas": [],
    "fornecedores": {
        "obrigatorios": ["azure-monitor"],
        "lideres_gartner": "auto",
        "contexto": [],
        "excluir": [],
        "max_avaliacao_completa": 6,
    },
    "gates": [],
    "classificacao": {"limite_nao_classificado_pct": 5.0, "mapa_blocos": {}},
    "pesos": {
        "multiplicadores": {"eliminatorio": 2.0, "obrigatorio": 1.0, "desejavel": 0.5},
        "naturezas": ["tecnico", "implantacao", "sla"],
        "categorias_excluidas": ["servicos", "licenciamento"],
        "override": {},
    },
    "eixos": dict(EIXOS_PADRAO),
    "modulos": ["nucleo"],
    "premissas_adicionais": [],
    "relatorio": {"incluir_pendencias": True, "confidencial": True, "pdf": False},
    "duvidas": {"modelo": None},
    "respostas": {
        "escala": ["Atende plenamente", "Atende parcialmente", "Não atende", "Não se aplica"],
        "observacao": {"metodo": True, "poc": True, "referencias": True, "prefixo_referencias": "Ref.:"},
        "pente_fino": {"justificativa_min": 90, "reuso_url": 5},
    },
    "execucao": {"assistida": True, "kb_max_dias": 1},
}


def _mesclar(base: dict, extra: dict) -> dict:
    saida = copy.deepcopy(base)
    for chave, valor in (extra or {}).items():
        if isinstance(valor, dict) and isinstance(saida.get(chave), dict):
            saida[chave] = _mesclar(saida[chave], valor)
        else:
            saida[chave] = valor
    return saida


class ErroConfig(Exception):
    pass


class Projeto:
    """Pasta do cliente (documentos do edital) + pasta de análise (_analise-rfp) com o rfp.yaml."""

    def __init__(self, pasta_cliente, pasta_analise: str = PASTA_ANALISE):
        self.pasta_cliente = Path(pasta_cliente).resolve()
        self.raiz = self.pasta_cliente / pasta_analise
        self.arquivo_config = self.raiz / "rfp.yaml"
        self._cfg = None

    @property
    def dir_projeto(self) -> Path:
        return self.raiz / "00-projeto"

    @property
    def dir_extracao(self) -> Path:
        return self.raiz / "01-extracao"

    @property
    def dir_analise(self) -> Path:
        return self.raiz / "02-analise"

    @property
    def dir_entregas(self) -> Path:
        return self.raiz / "03-entregas"

    def criar_pastas(self):
        for d in (self.dir_projeto, self.dir_extracao, self.dir_analise, self.dir_entregas,
                  self.dir_projeto / "evidencias"):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def cfg(self) -> dict:
        if self._cfg is None:
            if not self.arquivo_config.exists():
                raise ErroConfig(
                    f"rfp.yaml não encontrado em {self.raiz}. Rode primeiro: python kit.py init \"{self.pasta_cliente}\"")
            self._cfg = carregar_config(self.arquivo_config)
        return self._cfg

    @property
    def data_ref(self) -> dt.date:
        return util.para_data(self.cfg.get("data_referencia")) or dt.date.today()

    @property
    def sigla(self) -> str:
        return util.slug(self.cfg["cliente"].get("sigla") or self.cfg["cliente"].get("nome")) or "cliente"

    def entregavel(self, prefixo: str, extensao: str) -> Path:
        return self.dir_entregas / f"{prefixo}-{self.sigla}.{extensao}"


def carregar_config(caminho) -> dict:
    bruto = util.ler_yaml(caminho, {}) or {}
    cfg = _mesclar(DEFAULTS, bruto)
    erros = validar_config(cfg)
    if erros:
        raise ErroConfig("rfp.yaml inválido:\n  - " + "\n  - ".join(erros))
    return cfg


def validar_config(cfg: dict) -> list:
    erros = []
    if cfg.get("modo") not in MODOS:
        erros.append(f"modo deve ser um de {MODOS} (atual: {cfg.get('modo')!r})")
    if cfg.get("modo") == "proponente" and not cfg.get("proponente"):
        erros.append("modo=proponente exige 'proponente' (id do fornecedor na KB, ex.: azure-monitor)")
    eixos = cfg.get("eixos") or {}
    if "aderencia" not in eixos:
        erros.append("eixos deve conter 'aderencia'")
    soma = sum(float(v) for v in eixos.values())
    if abs(soma - 100) > 0.01:
        erros.append(f"a soma dos pesos em 'eixos' deve ser 100 (atual: {soma})")
    ids = [g.get("id") for g in cfg.get("gates") or []]
    if len(ids) != len(set(ids)):
        erros.append("ids de gates repetidos")
    for g in cfg.get("gates") or []:
        if not g.get("id") or not g.get("regra"):
            erros.append(f"gate sem 'id' ou 'regra': {g}")
    if cfg.get("data_referencia"):
        try:
            util.para_data(cfg["data_referencia"])
        except ValueError:
            erros.append("data_referencia deve estar no formato AAAA-MM-DD")
    for e in cfg.get("entradas") or []:
        if not e.get("arquivo"):
            erros.append(f"entrada sem 'arquivo': {e}")
    return erros
