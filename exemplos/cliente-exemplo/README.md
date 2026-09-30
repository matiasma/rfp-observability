# Cliente exemplo (fictício)

"Companhia Exemplo S.A." é um cliente **inventado** para demonstrar e testar o kit de ponta a ponta. Nenhum dado real.

| Arquivo | Papel |
|---|---|
| `gerar_exemplo.py` | gera `TR-Exemplo-Observabilidade.docx` (TR com títulos, numeração, lista e tabela) e `Matriz-Requisitos-Exemplo.xlsx` (matriz com coluna de resposta) |
| `_analise-rfp/rfp.yaml` | configuração do estudo (gates, contexto, eixos) |
| `_analise-rfp/02-analise/narrativa.md` | narrativa com placeholders e condicionais Jinja2 |
| `_analise-rfp/02-analise/eixos.yaml` | eixos **ilustrativos** (não são avaliação real) |
| `_analise-rfp/02-analise/registro-evidencias.yaml` | 2 alegações: leitura da cláusula de Gartner (item do edital) e a base do gate INDEFINIDO do Azure Monitor (URL oficial com citação) |
| `_analise-rfp/02-analise/duvidas.yaml` | 2 dúvidas que podem reabrir os gates G1 e G2 (aparecem em `eliminatorios.md`) |
| `_analise-rfp/02-analise/*` (demais) | modelos vazios de ajustes, overrides e classificação manual |

```powershell
python exemplos/cliente-exemplo/gerar_exemplo.py
python kit.py tudo exemplos/cliente-exemplo
```

Saídas em `_analise-rfp/03-entregas/` e dossiês de evidências em `_analise-rfp/00-projeto/evidencias/` (ignorados
pelo git — são regenerados a cada execução).
