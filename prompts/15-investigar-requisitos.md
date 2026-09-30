# Prompt 15 — Investigar cada requisito × fornecedor (execução assistida)

**Objetivo:** para cada requisito que pesa na aderência e cada fornecedor da avaliação completa (inclusive o
proponente), concluir o atendimento com **evidência oficial e citação literal**, dizer se a fonte cobre o parâmetro
pedido e, quando não der para ter confiança alta, **tipificar a lacuna e propor o encaminhamento**. O kit calcula a
confiança de cada avaliação por regras (`rfpkit/confianca.py`) e a aderência passa a sair desses itens.

**Como (pela skill, no VS Code)**
1. `python kit.py investigar "<pasta>"` gera `02-analise/investigacao/<fornecedor>/lote-NN.json`.
2. Um subagente por lote, em paralelo; cada subagente trabalha **um fornecedor** e edita **só o seu arquivo**.
3. `python kit.py investigar "<pasta>" --consolidar` incorpora, cria as dúvidas e mostra a cobertura. Repita até 0
   pendentes. Itens com `reabrir` + `resposta_cliente` voltaram porque o cliente respondeu uma ou mais dúvidas
   (`DUV-…: resposta`, separadas por `|`): reavalie com todas elas.
4. Item com `investigado: true` vale **inteiro** na consolidação: o que você deixar vazio (`evidencias: []`,
   `conflito: false`, `lacuna: ""`) substitui o que havia. Item sem `investigado: true` só acrescenta o que foi
   preenchido. Mantenha o JSON válido — lote ilegível é isolado como `.invalido` e o trabalho não entra.

**Entradas:** o lote (traz `entendimento` e `parametros` da revisão do requisito); a ficha e a biblioteca do
fornecedor na KB (`kb/fornecedores/<id>.yaml`, `kb/evidencias/<id>.yaml`); a documentação **oficial** do fornecedor
(pesquise e abra as páginas; use o navegador do VS Code quando a página for montada por JavaScript ou recusar robôs).

**Para cada item, preencha**

| Campo | O que escrever |
|---|---|
| `atendimento` | `pleno` · `parcial` · `nao` · `na` (não se aplica ao produto — exige `justificativa`) |
| `como` | `nativo` · `configuracao` · `extensao` · `terceiro` · `desenvolvimento` |
| `ga` | **obrigatório** em `pleno`/`parcial`: `true` se o recurso é GA; `false` se preview/beta (sem valor = confiança média; texto como `"preview"` = ERRO, tratado como preview) |
| `evidencias` | ids `EV-…` **da biblioteca deste fornecedor** na KB (preferencial) ou URLs oficiais dele — evidência de outro fornecedor não sustenta (confiança baixa). Se não houver EV adequada, **crie-a** em `kb/evidencias/<id>.yaml` ([kb-evidencias-fornecedor](kb-evidencias-fornecedor.md)) com capacidade genérica e citação literal |
| `citacoes` | trechos **literais** da página que sustentam a conclusão (copie e cole, 15+ caracteres; o kit confere se estão na página — com várias URLs, basta estar em uma). Citação curta demais ("SLA 99,9%") não é conferível e fica média. Para EV da KB, as citações já estão lá |
| `cobre_parametro` | `sim` · `parcial` · `nao` · `na` — a fonte cobre o volume/versão/prazo/limite pedido? |
| `conflito` | `true` se fontes oficiais se contradizem |
| `justificativa` | uma ou duas frases: como atende e o limite |
| `lacuna`, `tipo_lacuna` | o que impede confiança alta e de quem é: `cliente` (o edital não define o parâmetro/escopo), `documentacao` (a documentação oficial não esclarece), `conflito` |
| `duvida_sugerida` | se `cliente`/`conflito`: pergunta neutra ao cliente (regras do [prompt 05](05-armadilhas-duvidas.md)) — ou o id existente em `duvida` |
| `pergunta_fabricante` / `poc` | se `documentacao`: pergunta ao fabricante (interna) e/ou `poc: true` para comprovar na POC |
| `modelo` | o modelo que fez a investigação (ex.: o nome do modelo do subagente) |
| `investigado` | `true` quando o item estiver completo |

**Regras de confiança (o kit aplica)**
- **Alta** só com: requisito claro, citação literal conferida na página oficial nesta execução, recurso GA, a fonte
  cobre o parâmetro pedido e nenhum conflito. Para `nao`, cite a fonte que afirma a limitação — ausência de evidência
  não é evidência de ausência (fica média).
- Resposta **plena** do proponente só com confiança alta; se não der, rebaixe para `parcial`/`nao` ou encaminhe
  (pergunta/POC). Nunca "resolve com terceiro" fora da oferta.
- Não copie conclusões da nota da categoria na KB: investigue o requisito.
- Nada de dados de outros clientes; nada do edital na KB (a KB recebe só evidência pública genérica).
