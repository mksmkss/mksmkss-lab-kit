import json
import subprocess

from lab_kit import convert


def make_ipynb(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["x = 1"],
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook), encoding="utf-8")


def done(returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


def fake_marimo(calls, check_rc=0, convert_rc=0):
    def _run(args):
        calls.append(args)
        if args[0] == "convert":
            if convert_rc == 0:
                open(args[3], "w", encoding="utf-8").write("import marimo\n")
            return done(convert_rc, "boom" if convert_rc else "")
        return done(check_rc)

    return _run


def test_find_notebooks_excludes_junk(tmp_path):
    make_ipynb(tmp_path / "a.ipynb")
    make_ipynb(tmp_path / "sub" / "b.ipynb")
    make_ipynb(tmp_path / ".venv" / "lib" / "c.ipynb")
    make_ipynb(tmp_path / "sub" / ".ipynb_checkpoints" / "b-checkpoint.ipynb")
    found = [p.relative_to(tmp_path).as_posix() for p in convert.find_notebooks(tmp_path)]
    assert found == ["a.ipynb", "sub/b.ipynb"]


def test_find_notebooks_with_paths(tmp_path):
    make_ipynb(tmp_path / "a.ipynb")
    make_ipynb(tmp_path / "sub" / "b.ipynb")
    found = convert.find_notebooks(tmp_path, [tmp_path / "sub"])
    assert [p.name for p in found] == ["b.ipynb"]


def test_converts_and_keeps_ipynb(tmp_path, monkeypatch):
    make_ipynb(tmp_path / "a.ipynb")
    calls = []
    monkeypatch.setattr(convert, "marimo_command", lambda: ["marimo"])
    monkeypatch.setattr(convert, "run_marimo", fake_marimo(calls))
    assert convert.run(tmp_path) == 0
    assert (tmp_path / "a.py").exists()
    assert (tmp_path / "a.ipynb").exists()
    assert [c[0] for c in calls] == ["convert", "check"]


def test_skips_existing_py_and_never_overwrites(tmp_path, monkeypatch):
    make_ipynb(tmp_path / "a.ipynb")
    (tmp_path / "a.py").write_text("自分のコード\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(convert, "marimo_command", lambda: ["marimo"])
    monkeypatch.setattr(convert, "run_marimo", fake_marimo(calls))
    convert.run(tmp_path)
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "自分のコード\n"
    assert calls == []


def test_dry_run_does_nothing(tmp_path, monkeypatch):
    make_ipynb(tmp_path / "a.ipynb")
    calls = []
    monkeypatch.setattr(convert, "run_marimo", fake_marimo(calls))
    assert convert.run(tmp_path, dry_run=True) == 0
    assert calls == [] and not (tmp_path / "a.py").exists()


def test_failure_returns_1(tmp_path, monkeypatch, capsys):
    make_ipynb(tmp_path / "a.ipynb")
    monkeypatch.setattr(convert, "marimo_command", lambda: ["marimo"])
    monkeypatch.setattr(convert, "run_marimo", fake_marimo([], convert_rc=1))
    assert convert.run(tmp_path) == 1
    assert "失敗" in capsys.readouterr().out


def test_check_issues_are_reported(tmp_path, monkeypatch, capsys):
    make_ipynb(tmp_path / "a.ipynb")
    monkeypatch.setattr(convert, "marimo_command", lambda: ["marimo"])
    monkeypatch.setattr(convert, "run_marimo", fake_marimo([], check_rc=1))
    assert convert.run(tmp_path) == 0
    assert "直す必要" in capsys.readouterr().out


def test_no_marimo_available(tmp_path, monkeypatch):
    make_ipynb(tmp_path / "a.ipynb")
    monkeypatch.setattr(convert, "marimo_command", lambda: None)
    assert convert.run(tmp_path) == 1


def test_no_notebooks(tmp_path):
    assert convert.run(tmp_path) == 0


def test_doctor_checks_official_marimo_skills(tmp_path):
    from lab_kit import doctor

    status = {n: s for s, n, _ in doctor.check(tmp_path)}
    assert status["marimo 公式 Skill"] == doctor.WARN
    for name in ("marimo-notebook", "jupyter-to-marimo"):
        d = tmp_path / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("x", encoding="utf-8")
    status = {n: s for s, n, _ in doctor.check(tmp_path)}
    assert status["marimo 公式 Skill"] == doctor.OK
