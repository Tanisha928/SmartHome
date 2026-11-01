"""Import-linter style AST scan: no sqlalchemy/pymongo/boto3 outside persistence."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN = {"sqlalchemy", "pymongo", "boto3", "botocore"}
ALLOWED_PREFIXES = (
    "app/persistence/",
    "app/notifications/",  # SNS publish exception in PLAN §3
)
# alembic is outside app/


def _iter_py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_no_db_aws_imports_outside_persistence() -> None:
    app_root = Path(__file__).resolve().parents[2] / "app"
    violations: list[str] = []
    for path in _iter_py_files(app_root):
        rel = path.relative_to(app_root.parent).as_posix()
        if any(rel.startswith(p) for p in ALLOWED_PREFIXES):
            continue
        # workers may eventually consume SQS; model_worker stub is exempt until Vritika lands
        if rel in {"app/workers/model_worker.py"}:
            continue
        imported = _imports(path)
        bad = imported & FORBIDDEN
        if bad:
            violations.append(f"{rel}: {sorted(bad)}")
    assert violations == [], "Forbidden imports outside persistence:\n" + "\n".join(violations)
