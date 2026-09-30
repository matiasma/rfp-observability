"""Base de conhecimento (KB): taxonomia, fichas de fornecedores e histórico do Gartner MQ."""
import datetime as dt
from pathlib import Path

from . import util
from .config import KB_DIR

FATOS = (
    "integracoes_nativas", "sla_disponibilidade_pct", "regiao_dados_brasil", "suporte_ptbr",
    "agente_open_source", "opentelemetry", "retencao_metricas_meses", "retencao_metricas_integral",
    "so_suportados", "self_managed", "rum_mobile", "session_replay", "certificacoes",
)
ENUMS = {
    "regiao_dados_brasil": {"SIM", "NAO", "NAO_CONFIRMADO"},
    "suporte_ptbr": {"SIM", "NAO", "NAO_DOCUMENTADO"},
    "agente_open_source": {"SIM", "NAO", "PARCIAL"},
    "opentelemetry": {"SIM", "NAO", "PARCIAL"},
    "retencao_metricas_integral": {"SIM", "NAO", "PARCIAL"},
    "self_managed": {"SIM", "NAO", "PARCIAL"},
    "rum_mobile": {"SIM", "NAO", "PARCIAL"},
    "session_replay": {"SIM", "NAO", "PARCIAL", "PREVIEW"},
}
NUMERICOS = ("integracoes_nativas", "sla_disponibilidade_pct", "retencao_metricas_meses")
SO_VOCAB = {"linux", "windows", "macos", "aix", "solaris", "hpux", "zos", "arm"}
QUADRANTES = ("lider", "desafiante", "visionario", "nicho")
NOME_QUADRANTE = {"lider": "Líder", "desafiante": "Desafiante", "visionario": "Visionário", "nicho": "Nicho",
                  None: "Fora"}


class KB:
    def __init__(self, pasta=KB_DIR):
        self.pasta = Path(pasta)
        self.taxonomia = util.ler_yaml(self.pasta / "taxonomia.yaml", {})
        self.gartner = util.ler_yaml(self.pasta / "gartner-mq.yaml", {"edicoes": []})
        self.fornecedores = {}
        for arq in sorted((self.pasta / "fornecedores").glob("*.yaml")):
            if arq.name.startswith("_"):
                continue
            dados = util.ler_yaml(arq, {}) or {}
            dados.setdefault("id", arq.stem)
            dados["_arquivo"] = str(arq)
            self.fornecedores[dados["id"]] = dados
        self.bibliotecas, self.evidencia_por_id = {}, {}
        for arq in sorted((self.pasta / "evidencias").glob("*.yaml")):
            if arq.name.startswith("_"):
                continue
            dados = util.ler_yaml(arq, {}) or {}
            dados["_arquivo"] = str(arq)
            fid = dados.get("fornecedor") or arq.stem
            self.bibliotecas[fid] = dados
            for ev in dados.get("evidencias") or []:
                self.evidencia_por_id.setdefault(ev.get("id"), {**ev, "fornecedor": fid})
        self.cases, self.referencia_por_id = {}, {}
        for arq in sorted((self.pasta / "cases").glob("*.yaml")):
            if arq.name.startswith("_"):
                continue
            dados = util.ler_yaml(arq, {}) or {}
            dados["_arquivo"] = str(arq)
            fid = dados.get("fornecedor") or arq.stem
            self.cases[fid] = dados
            for ref in dados.get("referencias") or []:
                self.referencia_por_id.setdefault(ref.get("id"), {**ref, "fornecedor": fid})

    def referencia(self, rid):
        return self.referencia_por_id.get(str(rid or "").strip())

    def evidencia(self, eid):
        return self.evidencia_por_id.get(str(eid or "").strip())

    def status_evidencia(self, ev: dict, data_ref: dt.date) -> str:
        """VALIDADA | VENCIDA | A_VALIDAR | QUEBRADA (VENCIDA = validada há mais que o ttl do fornecedor)."""
        status = ev.get("status") or "A_VALIDAR"
        if status != "VALIDADA":
            return status
        verificado = util.para_data(ev.get("verificado_em"))
        ttl = int((self.fornecedores.get(ev.get("fornecedor")) or {}).get("ttl_dias") or 180)
        return "VENCIDA" if not verificado or verificado + dt.timedelta(days=ttl) < data_ref else "VALIDADA"

    # ---------- taxonomia ----------
    @property
    def categorias(self) -> list:
        return self.taxonomia.get("categorias", [])

    def categoria(self, cid) -> dict:
        return next((c for c in self.categorias if c["id"] == cid), {"id": cid, "nome": cid, "escopo": "produto"})

    @property
    def categorias_produto(self) -> list:
        return [c for c in self.categorias if c.get("escopo") == "produto"]

    # ---------- fornecedores ----------
    def nome(self, fid) -> str:
        return (self.fornecedores.get(fid) or {}).get("nome") or fid

    def fato(self, fid, nome, data_ref: dt.date) -> dict:
        """Retorna o fato com status OK | AUSENTE | VENCIDO | SEM_FICHA."""
        forn = self.fornecedores.get(fid)
        if not forn:
            return {"fato": nome, "valor": None, "status": "SEM_FICHA", "fonte": None, "verificado_em": None}
        bruto = (forn.get("fatos") or {}).get(nome) or {}
        valor = bruto.get("valor")
        verificado = util.para_data(bruto.get("verificado_em"))
        ttl = int(bruto.get("ttl_dias") or forn.get("ttl_dias") or 180)
        vence = verificado + dt.timedelta(days=ttl) if verificado else None
        if valor is None:
            status = "AUSENTE"
        elif verificado is None:
            status = "SEM_DATA"
        elif vence < data_ref:
            status = "VENCIDO"
        else:
            status = "OK"
        return {"fato": nome, "valor": valor, "status": status, "fonte": bruto.get("fonte"),
                "verificado_em": verificado, "vence_em": vence, "qualificador": bruto.get("qualificador"),
                "texto": bruto.get("texto"), "obs": bruto.get("obs")}

    def nota_base(self, fid, cid):
        entrada = ((self.fornecedores.get(fid) or {}).get("notas_base") or {}).get(cid) or {}
        return entrada.get("nota")

    # ---------- Gartner ----------
    def edicoes(self, data_ref: dt.date) -> list:
        """Edições publicadas até a data de referência, da mais recente para a mais antiga."""
        saida = []
        for e in self.gartner.get("edicoes", []):
            publicada = util.para_data(e.get("data_publicacao")) or dt.date(int(e["ano"]), 7, 1)
            if publicada <= data_ref:
                saida.append(e)
        return sorted(saida, key=lambda e: int(e["ano"]), reverse=True)

    @staticmethod
    def posicao(edicao: dict, fid: str):
        for q in QUADRANTES:
            if fid in ((edicao.get("quadrantes") or {}).get(q) or []):
                return q
        return None

    def historico(self, fid, data_ref: dt.date) -> list:
        return [{"ano": int(e["ano"]), "posicao": self.posicao(e, fid), "titulo": e.get("titulo")}
                for e in self.edicoes(data_ref)]

    def lideres_vigentes(self, data_ref: dt.date) -> list:
        eds = self.edicoes(data_ref)
        return list((eds[0].get("quadrantes") or {}).get("lider") or []) if eds else []

    def edicao_vigente(self, data_ref: dt.date):
        eds = self.edicoes(data_ref)
        return eds[0] if eds else None

    # ---------- manutenção ----------
    def status(self, data_ref: dt.date, incluir_ausentes: bool = False) -> list:
        """Frescor da KB: fatos vencidos/sem data e notas ausentes. Fatos sem valor (AUSENTE) só entram com
        incluir_ausentes — eles só importam quando um edital tem gate que depende deles, e aí o próprio estudo
        acusa o gate INDEFINIDO."""
        linhas = []
        for fid in sorted(self.fornecedores):
            for nome in FATOS:
                f = self.fato(fid, nome, data_ref)
                if f["status"] == "AUSENTE" and not incluir_ausentes:
                    continue
                linhas.append({"fornecedor": fid, "fato": nome, "status": f["status"],
                               "verificado_em": f["verificado_em"], "vence_em": f.get("vence_em")})
            for c in self.categorias_produto:
                if self.nota_base(fid, c["id"]) is None:
                    linhas.append({"fornecedor": fid, "fato": f"nota:{c['id']}", "status": "AUSENTE",
                                   "verificado_em": None, "vence_em": None})
        for fid, bib in sorted(self.bibliotecas.items()):
            for ev in bib.get("evidencias") or []:
                st = self.status_evidencia({**ev, "fornecedor": fid}, data_ref)
                if st != "VALIDADA":
                    linhas.append({"fornecedor": fid, "fato": f"evidencia:{ev.get('id')}", "status": st,
                                   "verificado_em": util.para_data(ev.get("verificado_em")), "vence_em": None})
        for fid, bib in sorted(self.cases.items()):
            for ref in bib.get("referencias") or []:
                st = self.status_evidencia({**ref, "fornecedor": fid}, data_ref)
                if st != "VALIDADA":
                    linhas.append({"fornecedor": fid, "fato": f"referencia:{ref.get('id')}", "status": st,
                                   "verificado_em": util.para_data(ref.get("verificado_em")), "vence_em": None})
        return linhas

    def validar(self) -> list:
        """Problemas de esquema da KB: lista de (nível, mensagem)."""
        prob = []
        ids_cat = {c["id"] for c in self.categorias}
        ids_prod = {c["id"] for c in self.categorias_produto}
        if len(ids_cat) != len(self.categorias):
            prob.append(("ERRO", "taxonomia.yaml: ids de categoria repetidos"))
        try:
            util.para_data(self.gartner.get("revisado_em"))
        except (ValueError, TypeError):
            prob.append(("ERRO", "gartner-mq.yaml: revisado_em inválido — use AAAA-MM-DD"))
        for fid, forn in self.fornecedores.items():
            arq = Path(forn["_arquivo"]).name
            try:
                util.para_data(forn.get("atualizado_em"))
            except (ValueError, TypeError):
                prob.append(("ERRO", f"{arq}: atualizado_em inválido — use AAAA-MM-DD"))
            if Path(forn["_arquivo"]).stem != fid:
                prob.append(("ERRO", f"{arq}: id '{fid}' difere do nome do arquivo"))
            for chave in ("nome", "fatos", "notas_base"):
                if not forn.get(chave):
                    prob.append(("ERRO", f"{arq}: chave obrigatória ausente: {chave}"))
            fatos = forn.get("fatos") or {}
            for nome in FATOS:
                if nome not in fatos:
                    prob.append(("ERRO", f"{arq}: fato ausente: {nome}"))
            for nome, f in fatos.items():
                if nome not in FATOS:
                    prob.append(("AVISO", f"{arq}: fato desconhecido: {nome}"))
                    continue
                f = f or {}
                v = f.get("valor")
                if v is None:
                    continue
                if not f.get("fonte") and v not in ("NAO_DOCUMENTADO", "NAO_CONFIRMADO"):
                    prob.append(("ERRO", f"{arq}: fato {nome} com valor informado e sem fonte"))
                if not f.get("verificado_em"):
                    prob.append(("ERRO", f"{arq}: fato {nome} sem verificado_em"))
                if nome in ENUMS and v not in ENUMS[nome]:
                    prob.append(("ERRO", f"{arq}: {nome}={v!r} fora de {sorted(ENUMS[nome])}"))
                if nome in NUMERICOS and not isinstance(v, (int, float)):
                    prob.append(("ERRO", f"{arq}: {nome} deve ser numérico"))
                if nome == "so_suportados":
                    fora = set(v) - SO_VOCAB if isinstance(v, list) else {"<não é lista>"}
                    if fora:
                        prob.append(("ERRO", f"{arq}: so_suportados com valores fora do vocabulário: {sorted(fora)}"))
                if nome == "certificacoes" and not isinstance(v, list):
                    prob.append(("ERRO", f"{arq}: certificacoes deve ser lista"))
            notas = forn.get("notas_base") or {}
            for cid in ids_prod - set(notas):
                prob.append(("ERRO", f"{arq}: notas_base sem a categoria {cid}"))
            for cid, n in notas.items():
                if cid not in ids_prod:
                    prob.append(("ERRO", f"{arq}: notas_base com categoria desconhecida {cid}"))
                    continue
                nota = (n or {}).get("nota")
                if nota is not None and not (0 <= float(nota) <= 1):
                    prob.append(("ERRO", f"{arq}: nota de {cid} fora de [0,1]"))
        anos = [e.get("ano") for e in self.gartner.get("edicoes", [])]
        if len(anos) != len(set(anos)):
            prob.append(("ERRO", "gartner-mq.yaml: edição repetida"))
        vistos_ev = {}
        for fid, bib in self.bibliotecas.items():
            arq = Path(bib["_arquivo"]).name
            if fid not in self.fornecedores:
                prob.append(("ERRO", f"evidencias/{arq}: fornecedor '{fid}' sem ficha em kb/fornecedores"))
            for ev in bib.get("evidencias") or []:
                eid = ev.get("id")
                if not eid or not ev.get("url") or not ev.get("capacidade"):
                    prob.append(("ERRO", f"evidencias/{arq}: evidência sem id, url ou capacidade: {eid}"))
                if eid in vistos_ev:
                    prob.append(("ERRO", f"evidencias/{arq}: id {eid} repetido (também em {vistos_ev[eid]})"))
                vistos_ev[eid] = arq
                if ev.get("status", "A_VALIDAR") not in ("VALIDADA", "A_VALIDAR", "QUEBRADA"):
                    prob.append(("ERRO", f"evidencias/{arq}: {eid} com status inválido {ev.get('status')!r}"))
                if ev.get("status") == "VALIDADA" and not ev.get("verificado_em"):
                    prob.append(("ERRO", f"evidencias/{arq}: {eid} VALIDADA sem verificado_em"))
                if not isinstance(ev.get("ga", True), bool):
                    prob.append(("ERRO", f"evidencias/{arq}: {eid} com 'ga' não booleano"))
                for cid in ev.get("categorias") or []:
                    if cid not in ids_prod:
                        prob.append(("ERRO", f"evidencias/{arq}: {eid} com categoria desconhecida {cid}"))
                if ev.get("citacoes") is not None and not isinstance(ev.get("citacoes"), list):
                    prob.append(("ERRO", f"evidencias/{arq}: {eid} com 'citacoes' que não é lista"))
                if not ev.get("citacao") and not ev.get("citacoes"):
                    prob.append(("AVISO", f"evidencias/{arq}: {eid} sem citação literal — a confiança das respostas que "
                                          "a usam não passa de média"))
        vistos_ref = {}
        for fid, bib in self.cases.items():
            arq = Path(bib["_arquivo"]).name
            if fid not in self.fornecedores:
                prob.append(("ERRO", f"cases/{arq}: fornecedor '{fid}' sem ficha em kb/fornecedores"))
            for ref in bib.get("referencias") or []:
                rid = ref.get("id")
                if not rid or not ref.get("url") or ref.get("tipo") not in ("case", "arquitetura"):
                    prob.append(("ERRO", f"cases/{arq}: referência sem id/url ou com tipo inválido: {rid}"))
                if rid in vistos_ref:
                    prob.append(("ERRO", f"cases/{arq}: id {rid} repetido"))
                vistos_ref[rid] = arq
                if ref.get("status") == "VALIDADA" and not ref.get("verificado_em"):
                    prob.append(("ERRO", f"cases/{arq}: {rid} VALIDADA sem verificado_em"))
        for e in self.gartner.get("edicoes", []):
            vistos = {}
            for q, ids in (e.get("quadrantes") or {}).items():
                if q not in QUADRANTES:
                    prob.append(("ERRO", f"gartner-mq.yaml {e.get('ano')}: quadrante inválido {q}"))
                for i in ids or []:
                    if i in vistos:
                        prob.append(("ERRO", f"gartner-mq.yaml {e.get('ano')}: {i} em dois quadrantes"))
                    vistos[i] = q
        return prob
