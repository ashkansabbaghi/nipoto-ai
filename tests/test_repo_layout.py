from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_claude_md_links_design_and_plan():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AI-SERVICE.fa.md" in text
    assert "MVP-PLAN.fa.md" in text


def test_package_layout():
    for pkg in ("api", "core", "pipeline", "retrieval", "llm", "guardrails", "connectors", "db"):
        assert (ROOT / "app" / pkg / "__init__.py").is_file(), pkg
