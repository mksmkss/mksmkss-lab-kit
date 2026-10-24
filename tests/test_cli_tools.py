import json
import subprocess

import pytest

from lab_kit import doctor, labels, lineage, save_data_with_metadata
from lab_kit.cli import build_parser, main


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_wanted_labels_default_and_kinds():
    names = [n for n, _, _ in labels.wanted_labels(None)]
    assert names == ["idea", "decided", "doing", "done", "meeting"]
    names = [n for n, _, _ in labels.wanted_labels("default")]
    assert names[-4:] == ["experiment", "method", "data", "analysis"]
    custom = labels.wanted_labels("model, eval")
    assert [n for n, _, _ in custom[-2:]] == ["model", "eval"]


def test_labels_creates_only_missing(monkeypatch, capsys):
    calls = []

    def fake_gh(args):
        calls.append(args)
        if args[:2] == ["api", "repos/{owner}/{repo}/labels?per_page=100"]:
            return completed("idea\nDone\n")
        return completed()

    monkeypatch.setattr(labels.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(labels, "run_gh", fake_gh)
    assert labels.run() == 0

    created = [c[5].removeprefix("name=") for c in calls if c[:3] == ["api", "-X", "POST"]]
    assert created == ["decided", "doing", "meeting"]  # idea と done(大文字小文字無視)は既にある
    assert "既にある" in capsys.readouterr().out


def test_labels_dry_run_creates_nothing(monkeypatch):
    calls = []

    def fake_gh(args):
        calls.append(args)
        return completed("")

    monkeypatch.setattr(labels.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(labels, "run_gh", fake_gh)
    assert labels.run(dry_run=True) == 0
    assert all(c[:3] != ["api", "-X", "POST"] for c in calls)


def test_labels_without_gh(monkeypatch, capsys):
    monkeypatch.setattr(labels.shutil, "which", lambda name: None)
    assert labels.run() == 1
    assert "gh" in capsys.readouterr().out


def test_labels_gh_not_logged_in(monkeypatch):
    monkeypatch.setattr(labels.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        labels, "run_gh", lambda args: completed(returncode=1, stderr="not logged in")
    )
    assert labels.run() == 1


def test_doctor_reports_missing_init(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    results = doctor.check(tmp_path)
    by_name = {name: status for status, name, _ in results}
    assert by_name["Python"] == doctor.OK
    assert by_name["gh"] == doctor.WARN
    assert by_name["lab-kit init"] == doctor.WARN
    assert doctor.run(tmp_path) in (0, 1)


def test_doctor_warns_on_public_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "/usr/bin/x")

    def fake_run(cmd):
        if cmd[:3] == ["gh", "auth", "status"]:
            return completed()
        if cmd[:3] == ["gh", "repo", "view"]:
            return completed(json.dumps({"nameWithOwner": "a/b", "visibility": "PUBLIC"}))
        return completed()

    monkeypatch.setattr(doctor, "_run", fake_run)
    github = [r for r in doctor.check(tmp_path) if r[1] == "GitHub"][0]
    assert github[0] == doctor.WARN
    assert "meeting" in github[2]


def test_lineage_main_writes_mermaid(tmp_path):
    import pandas as pd

    df = pd.DataFrame({"a": [1, 2]})
    raw = tmp_path / "data" / "raw.csv"
    save_data_with_metadata(df, raw, created_by="make.py")
    out = tmp_path / "data" / "clean.csv"
    save_data_with_metadata(df, out, created_by="clean.py", source_info=str(raw))

    path = lineage.main(root=tmp_path, verbose=False)
    assert path is not None
    text = open(path, encoding="utf-8").read()
    assert "mermaid" in text
    assert "clean" in text and "raw" in text
    assert "docs" in path


def test_lineage_main_without_metadata(tmp_path):
    assert lineage.main(root=tmp_path, verbose=False) is None


def test_cli_init_and_update_end_to_end(tmp_path, capsys):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    with pytest.raises(SystemExit) as e:
        main(["init", "--dir", str(tmp_path)])
    assert e.value.code == 0
    assert (tmp_path / ".claude" / "skills" / "decision-log" / "SKILL.md").exists()

    with pytest.raises(SystemExit) as e:
        main(["update", "--dir", str(tmp_path), "--dry-run"])
    assert e.value.code == 0
    assert "変更なし" in capsys.readouterr().out


def test_parser_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
