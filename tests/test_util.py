from rfpkit import util


def test_num_aceita_virgula_decimal():
    assert util.num("3,5") == 3.5 and util.num(4) == 4.0 and util.num("") is None and util.num("abc") is None


def test_br_formata_pt_br():
    assert util.br(92.94) == "92,9" and util.br(3.856, 2) == "3,86" and util.br(None) == "—"


def test_norm_remove_acentos():
    assert util.norm("  Correlação   ÚNICA ") == "correlacao unica"


def test_nome_arquivo_seguro():
    assert util.nome_arquivo_seguro("Grafana Labs (Grafana Cloud / LGTM)") == "Grafana Labs (Grafana Cloud - LGTM)"
    assert util.nome_arquivo_seguro('a:b*c?"d<e>f|g\\h') == "a-b-c-d-e-f-g-h"


def test_ler_csv_decide_delimitador_pelo_cabecalho(tmp_path):
    """Células com listas separadas por vírgula (ex.: 'usado_por') não podem confundir o delimitador ';'."""
    caminho = tmp_path / "urls.csv"
    usos = ", ".join(f"RF-{i:02d} (EV-AZ-001)" for i in range(40))
    util.gravar_csv(caminho, [{"url": "https://a.b/c", "usado_por": usos, "ok": True}], ["ok", "url", "usado_por"])
    linhas = util.ler_csv(caminho)
    assert linhas == [{"ok": "True", "url": "https://a.b/c", "usado_por": usos}]
    (tmp_path / "manual.csv").write_text("id,categoria\nRF-01,apm\n", encoding="utf-8")
    assert util.ler_csv(tmp_path / "manual.csv") == [{"id": "RF-01", "categoria": "apm"}]
