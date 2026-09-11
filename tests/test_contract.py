from pathlib import Path

import yaml
from openapi_spec_validator import validate

SPEC = Path(__file__).resolve().parent.parent / "contracts/main-backend.openapi.yaml"


def test_backend_contract_is_valid_openapi():
    validate(yaml.safe_load(SPEC.read_text(encoding="utf-8")))


def test_mvp_endpoints_are_not_marked_post_mvp():
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    phases = {
        op["x-bai"]: op["x-phase"]
        for path in spec["paths"].values()
        for op in path.values()
        if isinstance(op, dict) and "x-bai" in op
    }
    assert phases["B-AI-2"] == "mvp"
    assert phases["B-AI-3"] == "mvp"
    assert {phases[k] for k in ("B-AI-1", "B-AI-5", "B-AI-6")} == {"post-mvp"}
