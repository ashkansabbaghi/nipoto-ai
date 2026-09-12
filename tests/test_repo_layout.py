from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_claude_md_links_design_and_plan():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AI-SERVICE.fa.md" in text
    assert "MVP-PLAN.fa.md" in text


def test_package_layout():
    for pkg in ("api", "core", "pipeline", "retrieval", "llm", "guardrails", "connectors", "db"):
        assert (ROOT / "app" / pkg / "__init__.py").is_file(), pkg


def test_identity_never_comes_from_a_request_body():
    """AI-3: `user_id`/`role` come from the verified token only.

    Guard against a request model or endpoint growing a caller-supplied identity field.
    """
    offenders = []
    allowed = {ROOT / "app" / "core" / "auth.py", ROOT / "app" / "core" / "actor.py"}
    for path in (ROOT / "app").rglob("*.py"):
        if path in allowed:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for field in ("user_id", "role", "sub"):
                # A pydantic-style declaration of an identity field in an app module.
                if stripped.startswith(f"{field}:") and "Actor" not in stripped:
                    offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {stripped}")
    assert not offenders, "identity must come from Actor, not from request models:\n" + "\n".join(
        offenders
    )


def test_only_connectors_talk_to_the_main_backend():
    """AI-1 / module boundary: no module outside app/connectors builds an httpx client
    for the backend. app/retrieval/embed.py talks to the embeddings sidecar, not the
    backend, so it is allowed its own client."""
    allowed_prefixes = ("app/connectors/", "app/retrieval/embed.py")
    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        rel = str(path.relative_to(ROOT))
        if rel.startswith(allowed_prefixes):
            continue
        text = path.read_text(encoding="utf-8")
        if "import httpx" in text or "from httpx" in text:
            offenders.append(rel)
    assert not offenders, f"only app/connectors/ may import httpx for the backend: {offenders}"
