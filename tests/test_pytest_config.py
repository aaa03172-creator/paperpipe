import tomllib
from pathlib import Path


def test_pytest_uses_strict_registered_harness_markers() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    config = payload["tool"]["pytest"]["ini_options"]
    assert "--strict-markers" in config["addopts"]

    marker_names = {entry.split(":", 1)[0] for entry in config["markers"]}
    assert {
        "smoke",
        "real_smoke",
        "network",
        "external_inference",
        "slow",
        "goldset",
    }.issubset(marker_names)
