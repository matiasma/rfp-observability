# Prompt KB — Biblioteca de evidências públicas de um fornecedor

**Quando:** ao responder um edital como proponente e nenhuma evidência de `kb/evidencias/<id>.yaml` sustentar uma
resposta; ao criar a biblioteca de um fornecedor novo (copie `kb/evidencias/_modelo.yaml`).

**O quê:** capacidade → URL oficial → citação literal curta. Só documentação **pública** e recursos **GA**. A capacidade
é descrita de forma **genérica** (ex.: "Monitoramento de Azure Functions com Application Insights"), nunca com o texto
de um requisito ou o nome de um cliente — a biblioteca é compartilhada entre editais.

---

Para o fornecedor **<FORNECEDOR>**, encontre na documentação oficial evidências para estas capacidades:
<lista de capacidades genéricas>.
Para cada uma, devolva um item YAML no formato:
```yaml
- id: <PREFIXO>-<nnn>          # próximo número livre da biblioteca
  capacidade: "<descrição genérica>"
  categorias: [<ids de kb/taxonomia.yaml>]
  url: <URL oficial exata>
  citacao: "<trecho literal curto da página>"
  palavras_chave: [<2-3 termos que aparecem na página>]
  ga: true                     # false se a própria página indicar preview
  status: A_VALIDAR
  verificado_em: null
```
Não invente URL nem citação; se não achar fonte oficial, diga que não achou. A `citacao` precisa ser **literal**
(copiada da página, 15+ caracteres): o kit confere, a cada execução, se o texto ainda está na página
(`citacao_conferida_em`) e marca `mudanca_detectada` quando some. Formatos aceitos: o trecho literal puro, ou um
**rótulo curto terminado em `:`** seguido do trecho entre aspas (`"Sec. 7: 'texto literal'"`, `"Tabela de locais:
'Brazil South | latam-br-gru-edge'"`). Qualquer outro texto fora das aspas conta como parte da citação — comentário
ou paráfrase em volta de um nome entre aspas não passa na conferência. Páginas montadas por JavaScript ou que recusam
robôs: confira no navegador do VS Code e registre `verificado_navegador_em: <data>`.

Para **alegações** (limitação, restrição de termos de uso, aposentadoria de recurso, preview, SLA), acrescente
`alegacao: "<o que a fonte sustenta, em uma frase>"` e `citacoes: ["<trecho literal 1>", "<trecho literal 2>"]` —
são reaproveitadas pelo registro de evidências dos estudos (`kb: EV-…`). Se a página for montada por JavaScript
(o texto não aparece no HTML), marque `verificacao: navegador` e confira as citações no navegador.

---

**Depois:** acrescente os itens ao arquivo, rode `python kit.py kb-validar-urls --fornecedor <id> --atualizar`
(marca VALIDADA/QUEBRADA e grava a data) e `python kit.py kb-validar`.
