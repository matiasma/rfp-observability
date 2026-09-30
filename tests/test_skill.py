import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent


def test_frontmatter_da_skill_e_yaml_valido():
    texto = (RAIZ / ".github" / "skills" / "analise-rfp-observabilidade" / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    assert frontmatter, "SKILL.md sem frontmatter"
    dados = yaml.safe_load(frontmatter.group(1))
    assert dados["name"] == "analise-rfp-observabilidade"
    assert 50 < len(dados["description"]) <= 1024


def test_prompts_referenciados_na_skill_existem():
    texto = (RAIZ / ".github" / "skills" / "analise-rfp-observabilidade" / "SKILL.md").read_text(encoding="utf-8")
    prompts = {p.stem for p in (RAIZ / "prompts").glob("*.md")}
    for ref in re.findall(r"prompts/([\w-]+)\.md", texto):
        assert ref in prompts, ref
