"""Classificação de requisitos na taxonomia canônica: categoria, natureza e obrigatoriedade."""
from . import util

NAO_CLASSIFICADO = "nao-classificado"
ORDEM_NATUREZA = ("qualificacao", "comercial", "sla", "implantacao", "processo")
NATUREZAS = ORDEM_NATUREZA + ("tecnico",)


class Classificador:
    PESO_FRACA = 0.5

    def __init__(self, taxonomia: dict, mapa_blocos: dict | None = None):
        self.categorias = [
            (c["id"], util.compilar_palavras(c.get("palavras_chave")), util.compilar_palavras(c.get("palavras_fracas")))
            for c in taxonomia.get("categorias", [])
        ]
        self.naturezas = {k: util.compilar_palavras(v) for k, v in (taxonomia.get("naturezas") or {}).items()}
        self.naturezas_titulo = {k: util.compilar_palavras(v)
                                 for k, v in (taxonomia.get("naturezas_titulo") or {}).items()}
        self.obrig = {k: util.compilar_palavras(v) for k, v in (taxonomia.get("obrigatoriedade") or {}).items()}
        self.mapa_blocos = {util.norm(k): v for k, v in (mapa_blocos or {}).items()}

    def _pontos(self, fortes, fracas, texto_norm: str) -> float:
        return util.contar(fortes, texto_norm) + self.PESO_FRACA * util.contar(fracas, texto_norm)

    @staticmethod
    def _primeira_posicao(padroes, texto_norm: str):
        posicoes = [m.start() for p in padroes for m in [p.search(texto_norm)] if m]
        return min(posicoes) if posicoes else None

    def categoria(self, texto: str, bloco: str = "", secao: str = ""):
        """(categoria, confiança 0..1, origem). Título do bloco pesa 2x (+1 para o primeiro termo forte do título,
        que costuma nomear o assunto: "Correlação entre métricas, logs e traces"); texto 1x; seção 0,5x."""
        nb = util.norm(bloco)
        for chave, cid in self.mapa_blocos.items():
            if chave and chave in nb:
                return cid, 1.0, "mapa-blocos"
        nt, ns = util.norm(texto), util.norm(secao)
        primeiro = None
        if nb:
            candidatos = [(pos, i) for i, (_, fortes, _) in enumerate(self.categorias)
                          if (pos := self._primeira_posicao(fortes, nb)) is not None]
            primeiro = min(candidatos)[1] if candidatos else None
        pontos = []
        for i, (cid, fortes, fracas) in enumerate(self.categorias):
            p = (2 * self._pontos(fortes, fracas, nb) + self._pontos(fortes, fracas, nt)
                 + 0.5 * self._pontos(fortes, fracas, ns) + (1 if i == primeiro else 0))
            pontos.append((p, i, cid))
        pontos.sort(key=lambda x: (-x[0], x[1]))
        melhor, _, cid = pontos[0] if pontos else (0, 0, NAO_CLASSIFICADO)
        if melhor <= 0:
            return NAO_CLASSIFICADO, 0.0, "sem-evidencia"
        total = sum(p for p, _, _ in pontos if p > 0)
        return cid, round(melhor / total, 2), "palavras-chave"

    def natureza(self, texto: str, bloco: str = "", dica: str = "") -> str:
        """Natureza informada no rfp.yaml (ex.: natureza: processo) é aplicada literalmente; senão o título da
        seção/aba (dica) prevalece, depois o bloco, depois o texto do requisito."""
        nd = util.norm(dica)
        if nd in NATUREZAS:
            return nd
        if nd:
            for nat in ORDEM_NATUREZA:
                if util.contar(self.naturezas_titulo.get(nat, []), nd) or util.contar(self.naturezas.get(nat, []), nd):
                    return nat
        for fonte in (util.norm(bloco), util.norm(texto)):
            for nat in ORDEM_NATUREZA:
                if fonte and util.contar(self.naturezas.get(nat, []), fonte):
                    return nat
        return "tecnico"

    def obrigatoriedade(self, texto: str, explicito: str = "") -> str:
        nivel = self.nivel_explicito(explicito)
        if nivel:
            return nivel
        nt = util.norm(texto)
        if util.contar(self.obrig.get("eliminatorio", []), nt):
            return "eliminatorio"
        # "desejável/poderá" só rebaixa quando vem ANTES do verbo de obrigação
        # ("deverá permitir dashboards que poderão ser compartilhados" continua obrigatório)
        pos_desej = self._primeira_posicao(self.obrig.get("desejavel", []), nt[:120])
        pos_verbo = self._primeira_posicao(self.obrig.get("obrigatorio", []), nt)
        if pos_desej is not None and (pos_verbo is None or pos_desej < pos_verbo):
            return "desejavel"
        return "obrigatorio"

    def nivel_explicito(self, valor: str):
        """Nível de obrigatoriedade de um valor explícito do edital (ex.: coluna "Tipo"); None se não reconhecer."""
        nv = util.norm(valor)
        if not nv or len(nv) > 80:
            return None
        for nivel in ("eliminatorio", "desejavel", "obrigatorio"):
            if util.contar(self.obrig.get(nivel, []), nv):
                return nivel
        return None

    def tem_verbo_obrigacao(self, texto: str) -> bool:
        return bool(util.contar(self.obrig.get("obrigatorio", []), util.norm(texto)))
