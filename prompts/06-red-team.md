# Prompt 06 — Red team (módulo `red_team`)

**Objetivo:** atacar a própria conclusão antes que o cliente ou um concorrente o faça, e declarar a confiança das notas.

**Entradas:** `02-analise/gates.json`, `ranking.json`, `narrativa.md`, `ajustes-notas.yaml`, `eixos.yaml`, fichas da KB dos fornecedores avaliados, `00-projeto/evidencias/` (dossiês com fatos, fontes e datas de cada fornecedor) e `02-analise/registro-evidencias.yaml`.

**Saída:** `02-analise/red-team.md` (modelo já criado pelo kit), com:
1. **Confiança por fornecedor** (Alta/Média/Baixa) e base de evidência (KB `confianca`, fatos vencidos, notas ajustadas).
2. **3–5 ataques** à conclusão, cada um com resposta honesta (procedente / parcialmente / improcedente) e evidência — cite o id do registro (`EV-00nn`) ou a fonte do dossiê.
3. **Riscos da recomendação** com severidade e mitigação.
4. **Vieses controlados:** marketing, incumbente, nuvem do cliente, proponente (no modo proponente, seja duro com o próprio produto).
5. **Conclusão:** a recomendação sobrevive? Em que condição ela muda (ex.: gate flexibilizado)?

**Regras:** se um ataque for procedente, corrija o artefato de origem (KB, ajustes, eixos, gates-override, registro de evidências) e rode `kit.py tudo` — não "explique" o problema só no texto. Alegação de confiança baixa que decide o resultado vira dúvida ao cliente.
