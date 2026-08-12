import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _imported_top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_no_source_file_imports_the_old_backend_app_package():
    """The pre-Commit-8 implementation's root package was literally
    named `app` (nested one level under the now-removed backend
    directory), entirely distinct from this repo's `yt_live_dungeon`
    package. Nothing under src/ may import a top-level `app` module --
    if this ever starts failing, something is reaching back into the
    deleted implementation (or a reintroduced copy of it), not a false
    positive from an unrelated third-party package also happening to
    be named `app`."""
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in SRC_ROOT.rglob("*.py")
        if "app" in _imported_top_level_names(path)
        # yt_live_dungeon/app.py itself is the FastAPI entrypoint module,
        # never imported as bare `app` from within the package
        and path.name != "app.py"
    ]
    assert offenders == []
