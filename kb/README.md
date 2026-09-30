# Base de conhecimento (KB)

A KB é o ativo reaproveitável do kit: **só informação pública de fabricantes**, com fonte e data. Nada de cliente.

| Arquivo | Conteúdo | Atualização |
|---|---|---|
| `taxonomia.yaml` | 17 categorias (15 de produto + `servicos` + `licenciamento`), palavras-chave, naturezas e obrigatoriedade | quando a classificação errar de forma recorrente |
| `fornecedores/<id>.yaml` | fatos para gates + notas-base por categoria + destaques/gaps | fatos vencem em `ttl_dias` (padrão 180) |
| `fornecedores/_modelo.yaml` | esquema comentado de uma ficha (ignorado pelo kit) | — |
| `evidencias/<id>.yaml` | biblioteca de evidências públicas por capacidade (id EV-…, URL oficial, citação, GA, status; opcionalmente `alegacao` + `citacoes` literais) usada nas respostas do modo proponente e no registro de evidências dos estudos | `kb-validar-urls --atualizar`; cresce a cada edital respondido |
| `cases/<id>.yaml` | cases de clientes e arquiteturas de referência **publicados** pelo fabricante (id REF-…, `tipo: case/arquitetura`, resultados conforme publicados, URL, status) — Anexo B do memorial | `kb-validar-urls --atualizar` |
| `gartner-mq.yaml` | quadrantes por edição (2022–2026) | todo ano, na nova edição (julho) |
| `gates-biblioteca.yaml` | documentação das regras de gate disponíveis | ao criar regra em `rfpkit/gates.py` |

## Fatos (`fatos:`)

Cada fato tem `valor`, `fonte` (URL oficial), `verificado_em` (AAAA-MM-DD) e, opcionalmente, `obs`, `texto`,
`qualificador` e `ttl_dias`. O kit calcula o status:

| Status | Quando | Efeito no gate |
|---|---|---|
| OK | valor + data dentro da validade | avaliado normalmente |
| AUSENTE | `valor: null` | INDEFINIDO — pesquisar |
| SEM_DATA | valor sem `verificado_em` | INDEFINIDO — revalidar |
| VENCIDO | `verificado_em + ttl_dias` < data de referência do estudo | INDEFINIDO — revalidar |

Enumerações: `SIM | NAO | PARCIAL` (e `NAO_CONFIRMADO`, `NAO_DOCUMENTADO`, `PREVIEW` onde indicado no modelo).
"Não documentado" registra a **ausência de evidência pública** (não é evidência de ausência) e vira **RISCO**
nos gates. A KB não guarda pendências de confirmação: se um edital tiver gate que dependa desse fato, a
confirmação é tratada **no estudo daquele cliente** (ver "O que não entra na KB").

## Evidências por capacidade (`evidencias/`)

Cada item liga uma **capacidade genérica** do fornecedor a uma URL oficial, com citação curta, `ga` e `status`
(`VALIDADA` quando a URL responde 200 e contém as `palavras_chave`). As respostas de um edital citam os ids (`EV-AZ-003`);
o kit resolve as URLs para a coluna de observações da planilha e para o anexo do memorial. A justificativa de cada
requisito continua no estudo do cliente — a biblioteca só guarda a evidência pública, reaproveitável.

```powershell
python kit.py kb-validar-urls --fornecedor azure-monitor --atualizar   # verifica e grava status/verificado_em
```

**Citação literal é obrigatória:** o kit confere, a cada verificação, se a `citacao`/`citacoes` ainda está na página (`citacao_conferida_em`); quando some, a evidência vira `A_VALIDAR` com `mudanca_detectada` e as respostas que a usam caem de confiança. Evidência sem citação — ou com citação curta demais para conferir (menos de 15 caracteres) — não passa de confiança média. Formatos: trecho literal puro ou `"Rótulo curto: 'trecho literal'"`; texto fora das aspas que não seja um rótulo terminado em `:` conta como parte da citação (paráfrase não passa). Cada evidência é julgada pelas suas próprias citações, e só sustenta avaliações do fornecedor da sua biblioteca.

**Alegações** (limitações, restrições de termos de uso, aposentadorias de recurso, SLA) usam `alegacao` + `citacoes`
(lista de trechos literais): são reaproveitadas pelo registro de evidências de qualquer estudo com `kb: EV-…`.
Alegações datadas (preview, aposentadoria, datas de retirada) mudam com frequência — revalide o conteúdo, não só a URL.

Páginas montadas por JavaScript (ex.: termos de uso em aplicações SPA) não expõem o texto ao verificador: marque a
evidência com `verificacao: navegador`. A checagem automática passa a confirmar só a disponibilidade (situação
`NAVEGADOR`, sem rebaixar o status) e a conferência das citações é feita no navegador do VS Code, registrando `verificado_navegador_em`.

## Cases e arquiteturas de referência (`cases/`)

Só material publicado (customer stories, notícias oficiais, Azure Architecture Center/Well-Architected, equivalentes
de outros fabricantes), com os resultados **como publicados**. A relação do case com um cliente (setor, porte, picos)
é do estudo: `02-analise/cases-referencia.yaml` aponta `kb: REF-…` e escreve a `relacao`. Página original fora do ar →
use a cópia do Internet Archive e registre isso em `observacao`.

## O que não entra na KB
- Confirmações obtidas do fabricante durante um edital (e-mail, resposta a dúvida, carta, proposta): dependem do
  requisito daquele cliente e podem ser confidenciais. Registre-as em `<pasta-do-cliente>/_analise-rfp/02-analise/gates-override.yaml`
  (veredito + justificativa + fonte), no `registro-evidencias.yaml` do estudo e nas dúvidas do edital.
- Listas de "fatos a confirmar" derivadas de gates de um cliente: o que precisa ser confirmado depende de cada edital
  e aparece como gate **INDEFINIDO/RISCO** no `validacao.md` do próprio estudo.
- Trechos de edital, nomes de clientes ou contexto de cliente.

## Notas-base (`notas_base:`)

Uma por categoria de produto, na régua única: **1,0** nativo-líder · **0,75** forte · **0,5** parcial/por extensão ·
**0,25** fraco · **0** não atende (múltiplos de 0,05 permitidos). São *priors* genéricos: o estudo de cada edital
pode ajustá-las em `02-analise/ajustes-notas.yaml`, sempre com justificativa e fonte. Se o ajuste for uma
correção geral (não ligada ao edital), corrija a KB.

## Rotina de manutenção

```powershell
python kit.py kb-status              # frescor: fatos vencidos/sem data e Líderes vigentes
python kit.py kb-status --ausentes   # inclui fatos sem evidência pública (só pesquise se algum edital precisar)
python kit.py kb-status --csv kb-pendencias.csv
python kit.py kb-validar             # esquema (0 erros antes de commitar)
python kit.py kb-novo elastic --nome "Elastic"
```

- Revalide fatos **vencidos** periodicamente; fatos **ausentes** só valem pesquisa quando um edital tiver gate que dependa deles (e só entram na KB se houver fonte pública).
- Pesquisa de fatos: `prompts/kb-pesquisar-fornecedor.md` (um subagente por fornecedor, em paralelo).
- Nova edição do Gartner: `prompts/kb-atualizar-gartner.md`.
- Commit com mensagem que diga o que mudou e a data da verificação (ex.: `kb: datadog SLA/retenção revalidados 2027-01`).

## Regras

1. Fonte oficial do fabricante (docs, termos/SLA, trust center, blog/press oficial, GitHub oficial). Analistas e
   imprensa só para o Gartner MQ.
2. Sem fonte → `valor: null`. Nunca estimar.
3. Preview não é GA (`PARCIAL`/`PREVIEW` + `obs`).
4. Nenhum trecho de edital, nome de cliente, contexto de cliente ou confirmação obtida num edital — a KB é compartilhada e só reflete evidência pública.
