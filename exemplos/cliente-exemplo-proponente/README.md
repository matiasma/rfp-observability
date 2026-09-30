# Cliente exemplo — modo proponente (fictício)

Mesmo edital fictício de `../cliente-exemplo/`, agora **respondido como Azure Monitor** — demonstra o pacote completo de
submissão. Nenhum dado real de cliente; as respostas usam evidências públicas de `kb/evidencias/azure-monitor.yaml`.

| Arquivo | Papel |
|---|---|
| `Matriz-Requisitos-Exemplo.xlsx` | matriz do edital (gerada por `../cliente-exemplo/gerar_exemplo.py`): dropdown com nome definido cobrindo só parte das linhas, aba de dados quantitativos com outra escala, aba oculta de configuração e logotipo |
| `Anexo-Duvidas-Exemplo.xlsx` | modelo de envio de dúvidas do edital (idem) |
| `_analise-rfp/rfp.yaml` | `modo: proponente`, `proponente: azure-monitor`, `duvidas.modelo` |
| `_analise-rfp/02-analise/respostas.json` | 15 respostas com evidências EV-…, método e POC |
| `_analise-rfp/02-analise/duvidas.yaml` | 3 dúvidas enviáveis, com os campos internos (resposta desejada, impacto, status) |
| `_analise-rfp/02-analise/revisao-requisitos.json` | revisão dos 15 requisitos: 3 ambíguos/incompletos ligados às dúvidas — aparecem com confiança média e encaminhamento em `confianca.md` |
| `_analise-rfp/02-analise/registro-evidencias.yaml` | 3 alegações (2 reaproveitando evidências da KB com `kb: EV-…` e 1 de leitura de item do edital) |
| `_analise-rfp/02-analise/cases-referencia.yaml` | 1 case e 2 arquiteturas da KB (`kb: REF-…`) com a relação com o cliente fictício e a nota de maturidade (0–10) |
| `_analise-rfp/02-analise/esforco-poc.yaml` | esforço de POC ILUSTRATIVO por frente e fornecedor (frentes-portão e risco) |
| `_analise-rfp/02-analise/custo.yaml` | custo ILUSTRATIVO (`ilustrativo: true`) para demonstrar o cálculo e o cruzamento esforço × custo |
| `_analise-rfp/02-analise/narrativa.md` | mensagem principal, diferenciais, arquitetura, ressalvas e próximos passos (com placeholders) |

```powershell
python exemplos/cliente-exemplo/gerar_exemplo.py
python kit.py tudo exemplos/cliente-exemplo-proponente --urls --pdf
```

Em `_analise-rfp/03-entregas/`: planilha **RESPONDIDA**, `matriz-respostas`, anexo de dúvidas **PREENCHIDO**, memorial
técnico e sumário executivo (DOCX/PDF), relatório HTML/MD com a seção de respostas, comparativo e RTM.
Em `_analise-rfp/00-projeto/evidencias/`: dossiês por fornecedor, Gartner, registro de evidências e a biblioteca de
evidências usadas nas respostas; em `02-analise/`: `eliminatorios.md`, `ranking.md` (com battlecards), `esforco-custo.md`,
`duvidas-interna.md`, `cases-referencia-maturidade.md`, `pente-fino-automatico.md`, `validacao-urls.md` e `validacao.md`;
e o índice `03-entregas/README-ENTREGAS.md`.
