# Prompt 01 — Classificar requisitos pendentes

**Objetivo:** atribuir categoria (e, se preciso, natureza/obrigatoriedade) aos requisitos que o classificador por palavras-chave não resolveu, para que os pesos reflitam o edital.

**Entradas**
- `<pasta>/_analise-rfp/02-analise/pendencias-classificacao.csv` (só itens que entram nos pesos: não classificados ou confiança < 0,4)
- `<KIT>/kb/taxonomia.yaml` (ids e descrições das categorias)
- Se precisar de contexto: `01-extracao/*.md`

**Saída:** acrescente linhas em `<pasta>/_analise-rfp/02-analise/classificacao-manual.csv` (separador `;`, mantenha o cabeçalho):

```
id;categoria;natureza;obrigatoriedade;obs
TEO:3.7.3;aiops;;;detecção de anomalias é AIOps, não alerta
```

**Regras**
- `categoria`: um id de `taxonomia.yaml` (`coleta` … `licenciamento`). Deixe vazio para manter o automático.
- `natureza` (opcional): `tecnico | implantacao | sla | qualificacao | comercial | processo`. Use `qualificacao` para critérios de habilitação do fabricante (vão para os gates, não para os pesos).
- `obrigatoriedade` (opcional): `eliminatorio | obrigatorio | desejavel` — só corrija se o edital for explícito.
- Classifique pelo **que o requisito exige do produto**, não pelas palavras soltas. Serviços do integrador (treinamento, implantação) = `servicos`.
- Se um bloco inteiro está errado, prefira `classificacao.mapa_blocos` no rfp.yaml (`"trecho do título": categoria`).
- Depois: `python kit.py tudo "<pasta>"` e confira que o aviso de classificação sumiu.
