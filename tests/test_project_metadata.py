import tomllib
from pathlib import Path


def test_project_depends_on_moomoo_api_distribution():
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    dependencies = metadata["project"]["dependencies"]

    assert any(item.startswith("moomoo-api") for item in dependencies)
