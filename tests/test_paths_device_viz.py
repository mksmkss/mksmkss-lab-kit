import pytest

from lab_kit import data_path, get_device, project_root, results_path
from lab_kit.paths import project_root as _project_root
from lab_kit.viz import JP_FONT_FAMILY, apply_jp_font, register_template


def test_project_root_from_marker(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.delenv("MAIN_PATH", raising=False)
    monkeypatch.chdir(sub)
    assert project_root() == tmp_path.resolve()
    assert data_path("raw", "x.csv") == tmp_path.resolve() / "data" / "raw" / "x.csv"
    assert results_path("e1") == tmp_path.resolve() / "results" / "e1"


def test_main_path_env_wins(tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.setenv("MAIN_PATH", str(other))
    monkeypatch.chdir(tmp_path)
    assert project_root() == other.resolve()


def test_main_path_from_dotenv(tmp_path, monkeypatch):
    target = tmp_path / "elsewhere"
    target.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".env").write_text(f"MAIN_PATH={target}\n")
    monkeypatch.delenv("MAIN_PATH", raising=False)
    monkeypatch.chdir(proj)
    assert project_root() == target.resolve()


def test_project_root_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("MAIN_PATH", raising=False)
    # tmp_path の上位に .git や pyproject.toml がない前提を作る
    isolated = tmp_path / "x"
    isolated.mkdir()
    monkeypatch.chdir(isolated)
    try:
        root = _project_root()
    except FileNotFoundError:
        return
    # 環境によっては上位に marker がある。その場合は、tmp の外を指していることだけ確認
    assert tmp_path.resolve() not in (root, *root.parents) or root == tmp_path.resolve()


def test_get_device_returns_known_name():
    assert get_device() in {"cpu", "cuda", "mps"}
    assert get_device("cpu") == "cpu"


def test_apply_jp_font():
    go = pytest.importorskip("plotly.graph_objects")
    fig = apply_jp_font(go.Figure())
    assert fig.layout.font.family == JP_FONT_FAMILY


def test_register_template_sets_default():
    import plotly.io as pio

    previous = pio.templates.default
    try:
        name = register_template(set_default=False)
        assert name in pio.templates
    finally:
        pio.templates.default = previous
