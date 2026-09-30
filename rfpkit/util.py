import csv
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

import yaml


def norm(texto) -> str:
    """Minúsculas, sem acentos e com espaços colapsados — base de toda comparação por palavra-chave."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def slug(texto) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(texto)).strip("-")


def norm_literal(texto) -> str:
    """Normalização para comparar uma citação com o texto de uma página: minúsculas, sem acentos e só letras e dígitos
    (pontuação, aspas tipográficas e quebras de linha não contam)."""
    return re.sub(r"[^a-z0-9]+", " ", norm(texto)).strip()


_ASPAS = re.compile(r"[\"“”«]([^\"“”«»]{12,})[\"“”»]|(?<![A-Za-z])'([^']{12,})'(?![A-Za-z])")
_PARES = {'"': '"', "'": "'", "“": "”", "«": "»"}
_FIM_ROTULO = (":", "—", "–", "-")


def trechos_citacao(citacao, minimo: int = 15) -> list:
    """Trechos literais de uma citação que devem aparecer na página. Citação inteira entre aspas: vale o miolo. Rótulo
    curto terminado em ':' ou '—' seguido de trechos entre aspas (ex.: "Seção 7: 'texto'", "Tabela de locais: 'Brazil
    South'"): valem só os trechos entre aspas. Qualquer outro texto fora das aspas conta como parte da citação — uma
    paráfrase que só põe um nome entre aspas não passa. As reticências separam trechos. Trechos com menos de `minimo`
    caracteres (normalizados) são ignorados."""
    s = str(citacao or "").strip()
    achados = list(_ASPAS.finditer(s))
    bases = [s]
    if achados:
        rotulo = s[:achados[0].start()].strip()
        resto = [s[a.end():b.start()] for a, b in zip(achados, achados[1:])] + [s[achados[-1].end():]]
        if ((not rotulo or (len(rotulo) <= 80 and rotulo.endswith(_FIM_ROTULO)))
                and all(re.fullmatch(r"[\s.,;:…]*", r) for r in resto)):
            bases = [m.group(1) or m.group(2) for m in achados]
    elif len(s) > 2 and s[0] in _PARES and s.endswith(_PARES[s[0]]):
        bases = [s[1:-1]]
    saida = []
    for base in bases:
        for frag in re.split(r"\.\.\.|…", base):
            f = norm_literal(frag)
            if len(f) >= minimo:
                saida.append(f)
    return saida


def nome_arquivo_seguro(texto) -> str:
    """Remove caracteres inválidos em nomes de arquivo no Windows (ex.: "Grafana Cloud / LGTM")."""
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|]+', "-", str(texto or ""))).strip(" .-") or "arquivo"


def compilar_palavras(palavras) -> list:
    """Palavra curta (<=4 letras) casa só a palavra inteira; as demais casam por prefixo de palavra."""
    padroes = []
    for p in palavras or []:
        p = norm(p)
        if not p:
            continue
        fim = r"(?![a-z0-9])" if len(p) <= 4 else ""
        padroes.append(re.compile(r"(?<![a-z0-9])" + re.escape(p) + fim))
    return padroes


def contar(padroes, texto_normalizado: str) -> int:
    return sum(1 for p in padroes if p.search(texto_normalizado))


def ler_yaml(caminho, padrao=None):
    caminho = Path(caminho)
    if not caminho.exists():
        return padrao
    with caminho.open(encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    return padrao if dados is None else dados


def gravar_yaml(caminho, dados):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with Path(caminho).open("w", encoding="utf-8") as f:
        yaml.safe_dump(dados, f, allow_unicode=True, sort_keys=False, width=120)


def ler_lote(caminho) -> tuple:
    """(itens, erro) de um lote preenchido por subagente: lista de objetos JSON; erro descreve o problema."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as e:
        return None, f"JSON inválido ({type(e).__name__}: {str(e)[:80]})"
    if not isinstance(dados, list):
        return None, "o lote deve ser uma lista de itens (como foi gerado pelo kit)"
    return [d for d in dados if isinstance(d, dict)], ""


def isolar_lote(caminho) -> Path:
    """Renomeia um lote ilegível para <lote>.invalido (ou <lote>.N.invalido — nunca sobrescreve um isolado anterior)."""
    destino, n = Path(str(caminho) + ".invalido"), 2
    while destino.exists():
        destino, n = Path(f"{caminho}.{n}.invalido"), n + 1
    Path(caminho).rename(destino)
    return destino


def ler_json(caminho, padrao=None):
    caminho = Path(caminho)
    if not caminho.exists():
        return padrao
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, dados):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with Path(caminho).open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=str)


def gravar_csv(caminho, linhas, colunas):
    """CSV com ';' e BOM — abre direto no Excel pt-BR."""
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with Path(caminho).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for linha in linhas:
            w.writerow({k: ("" if linha.get(k) is None else linha.get(k)) for k in colunas})


def ler_csv(caminho) -> list:
    """Lê CSV com ';' (gravado pelo kit/Excel pt-BR) ou ','. O delimitador é decidido pelo CABEÇALHO: contar no
    corpo erra quando as células têm listas separadas por vírgula."""
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        cabecalho = f.readline()
        f.seek(0)
        delim = ";" if cabecalho.count(";") >= cabecalho.count(",") else ","
        linhas = []
        for linha in csv.DictReader(f, delimiter=delim):
            linhas.append({(k or "").strip(): (delim.join(v) if isinstance(v, list) else (v or "")).strip()
                           for k, v in linha.items()})
        return linhas


def para_data(valor):
    if valor in (None, ""):
        return None
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    return dt.date.fromisoformat(str(valor).strip()[:10])


def num(valor):
    """Número de YAML/CSV aceitando vírgula decimal ("3,5"); None se vazio ou inválido."""
    if valor is None or valor == "" or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).strip().replace(",", "."))
    except ValueError:
        return None


def br(valor, casas: int = 1) -> str:
    """Número no formato pt-BR (vírgula decimal). None vira travessão."""
    if valor is None or valor == "":
        return "—"
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)
