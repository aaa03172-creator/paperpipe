import importlib
import sys


def test_skills_package_does_not_eagerly_import_runner():
    sys.modules.pop("src.skills", None)
    sys.modules.pop("src.skills.runner", None)

    skills_pkg = importlib.import_module("src.skills")

    assert skills_pkg is not None
    assert "src.skills.runner" not in sys.modules
