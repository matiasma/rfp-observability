# Prompt 14 — Revisar TODOS os requisitos do edital (execução assistida)

**Objetivo:** cada requisito do edital lido e entendido pelo LLM — não só os que o classificador por palavras-chave
não resolveu — com a classificação confirmada, os parâmetros extraídos e toda lacuna de informação transformada em
pergunta de esclarecimento ao cliente.

**Como (pela skill, no VS Code)**
1. `python kit.py revisar "<pasta>"` gera `02-analise/revisao/lote-NN.json` com os requisitos ainda não revisados.
2. Um subagente por lote, em paralelo, com este prompt. Cada subagente edita **só o seu arquivo de lote**.
3. `python kit.py revisar "<pasta>" --consolidar` incorpora os lotes, cria as dúvidas em `02-analise/duvidas.yaml` e
   mostra a cobertura. Repita até **0 pendentes** (a validação acusa ERRO enquanto houver requisito sem revisão).

**Entradas:** o arquivo do lote; `01-extracao/*.md` (todos os documentos do edital, inclusive anexos e erratas);
`<KIT>/kb/taxonomia.yaml`; `02-analise/duvidas.yaml` (perguntas já existentes); `rfp.yaml → cliente.contexto`.

**Para cada item do lote, preencha**

| Campo | O que escrever |
|---|---|
| `categoria` | id de `kb/taxonomia.yaml` quando `automatico.categoria` estiver errada; vazio mantém o automático. Classifique pelo que o requisito exige do produto (regras do [prompt 01](01-classificar-pendencias.md)); serviços do integrador = `servicos` |
| `natureza`, `obrigatoriedade` | só quando o edital for explícito e diferente do automático |
| `entendimento` | uma frase verificável: o que o requisito exige |
| `parametros` | volumes, versões, prazos, SLAs, quantidades e ambientes citados, literalmente; vazio se não houver |
| `clareza` | `clara` · `ambigua` (termo sem definição que muda a resposta, duas leituras possíveis) · `incompleta` (falta volume, versão, ambiente, escopo ou critério de aceite para avaliar) |
| `lacuna` | obrigatório se a clareza não for `clara`: o que falta, em uma frase |
| `duvida_sugerida` | pergunta ao cliente que fecha a lacuna — neutra, objetiva, sem revelar estratégia nem citar fornecedor, citando o item (regras do [prompt 05](05-armadilhas-duvidas.md)). Se já existir pergunta equivalente em `duvidas.yaml`, informe o id dela em `duvida` em vez de sugerir outra |
| `obs` | curta: contradição com outro documento, duplicidade, dependência de outro item |
| `revisado` | `true` quando o item estiver completo — item concluído vale inteiro na consolidação (campo vazio limpa o anterior) |

**Regras**
- Antes de declarar lacuna, procure a informação em **todos** os documentos do edital (seção, bloco, anexos, erratas,
  respostas a esclarecimentos já publicadas). Lacuna é o que nem o edital resolve.
- Não avalie fornecedores aqui: a capacidade de cada produto é tratada na KB, nas notas e nas respostas.
- Não altere `id`, `requisito`, `fonte`, `localizacao` nem `automatico`; mantenha o JSON válido; escreva em português.
- Nada de outros clientes ou editais no texto.
