import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lab_kit import scaffold


def tree_hashes(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git/" not in p.as_posix()
    }


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


EXPECTED_SKILLS = [
    "decision-log",
    "explain-results",
    "lab-adopt",
    "research-direction",
    "result-graphs",
]


def test_init_on_empty_project_creates_everything(project):
    scaffold.run(project, mode="init")
    for skill in EXPECTED_SKILLS:
        assert (project / ".claude" / "skills" / skill / "SKILL.md").exists()
    assert (project / ".env.example").exists()
    assert (project / "notebooks" / "_template.py").exists()
    assert (project / "data" / "raw" / ".gitkeep").exists()
    assert (project / "results" / ".gitkeep").exists()
    assert "lab-kit:begin" in (project / "CLAUDE.md").read_text(encoding="utf-8")
    assert "lab-kit:begin" in (project / ".gitignore").read_text(encoding="utf-8")
    assert (project / ".lab-kit" / "manifest.json").exists()


def test_init_is_idempotent(project):
    scaffold.run(project, mode="init")
    before = tree_hashes(project)
    report = scaffold.run(project, mode="init")
    assert tree_hashes(project) == before
    assert report.count("create") == 0
    assert report.count("conflict") == 0
    assert report.count("block-add") == 0


def test_init_keeps_existing_claude_md_and_gitignore(project):
    (project / "CLAUDE.md").write_text("# 自分のルール\n\n- 大事なこと\n", encoding="utf-8")
    (project / ".gitignore").write_text("*.log\nsecret/\n", encoding="utf-8")
    scaffold.run(project, mode="init")

    claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
    assert claude.startswith("# 自分のルール\n\n- 大事なこと\n")
    assert "lab-kit:begin" in claude and "lab-kit:end" in claude

    ignore = (project / ".gitignore").read_text(encoding="utf-8")
    assert ignore.startswith("*.log\nsecret/\n")
    assert ignore.count("lab-kit:begin") == 1


def test_init_does_not_overwrite_conflicting_file(project):
    (project / ".env.example").write_text("MY_OWN=1\n", encoding="utf-8")
    skill = project / ".claude" / "skills" / "decision-log"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("自分で書いた Skill\n", encoding="utf-8")

    report = scaffold.run(project, mode="init")

    assert (project / ".env.example").read_text(encoding="utf-8") == "MY_OWN=1\n"
    assert (project / ".env.example.lab-kit.new").exists()
    assert (skill / "SKILL.md").read_text(encoding="utf-8") == "自分で書いた Skill\n"
    assert (skill / "SKILL.md.lab-kit.new").exists()
    assert report.count("conflict") == 2


def test_init_leaves_other_files_untouched(project):
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (project / "data" / "raw").mkdir(parents=True)
    (project / "data" / "raw" / "big.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    before = tree_hashes(project)

    scaffold.run(project, mode="init")

    after = tree_hashes(project)
    for path, digest in before.items():
        assert after[path] == digest


def test_dry_run_changes_nothing(project):
    before = tree_hashes(project)
    report = scaffold.run(project, mode="init", dry_run=True)
    assert tree_hashes(project) == before
    assert report.count("create") > 0


def test_gitignore_block_semantics(project):
    scaffold.run(project, mode="init")

    def ignored(rel):
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text("x", encoding="utf-8")
        result = subprocess.run(["git", "check-ignore", "-q", rel], cwd=project)
        return result.returncode == 0

    assert ignored("data/raw/input.csv")
    assert ignored("data/interim/emb.npy")
    assert ignored("models/model.pt")
    assert ignored(".env")
    assert not ignored("data/interim/cleaned_metadata.yaml")
    assert not ignored("data/processed/sub/x_metadata.yaml")
    assert not ignored("data/raw/.gitkeep")
    assert not ignored("results/exp1/figures/a.png")
    assert not ignored("results/exp1/table.csv")
    assert not ignored("src/main.py")


def test_agents_links(project):
    scaffold.run(project, mode="init", agents=True)
    link = project / ".agents" / "skills" / "decision-log"
    assert link.is_symlink()
    assert (link / "SKILL.md").exists()


@pytest.fixture
def fake_scaffold(tmp_path, monkeypatch):
    """配布物を差し替えられるよう、scaffold をコピーして使う"""
    copy = tmp_path / "scaffold_copy"
    shutil.copytree(scaffold.SCAFFOLD_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(scaffold, "SCAFFOLD_DIR", copy)
    return copy


def test_update_refreshes_unmodified_and_keeps_modified(project, fake_scaffold):
    scaffold.run(project, mode="init")

    # 利用者が explain-results だけ編集した
    edited = project / ".claude" / "skills" / "explain-results" / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\n自分の追記\n", encoding="utf-8")

    # 配布側が decision-log と explain-results を更新した
    (fake_scaffold / "skills" / "decision-log" / "SKILL.md").write_text(
        "新しい版\n", encoding="utf-8"
    )
    explain_src = fake_scaffold / "skills" / "explain-results" / "SKILL.md"
    explain_src.write_text(
        explain_src.read_text(encoding="utf-8") + "\n配布側の追記\n", encoding="utf-8"
    )

    report = scaffold.run(project, mode="update")

    decision = project / ".claude" / "skills" / "decision-log" / "SKILL.md"
    assert decision.read_text(encoding="utf-8") == "新しい版\n"
    assert "自分の追記" in edited.read_text(encoding="utf-8")
    assert "配布側の追記" not in edited.read_text(encoding="utf-8")
    assert (edited.parent / "SKILL.md.lab-kit.new").exists()
    assert report.count("update") == 1
    assert report.count("conflict") == 1


def test_update_replaces_only_the_managed_block(project, fake_scaffold):
    (project / "CLAUDE.md").write_text("# 前\n", encoding="utf-8")
    scaffold.run(project, mode="init")
    path = project / "CLAUDE.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n# 後ろに自分の節\n", encoding="utf-8")

    (fake_scaffold / "blocks" / "CLAUDE.md.block").write_text("## 新しいルール\n", encoding="utf-8")
    scaffold.run(project, mode="update")

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# 前\n")
    assert "## 新しいルール" in text
    assert "lab-kit の運用ルール" not in text
    assert text.rstrip().endswith("# 後ろに自分の節")
    assert text.count("lab-kit:begin") == 1


def test_unbalanced_marker_is_reported_not_touched(project):
    (project / ".gitignore").write_text("# lab-kit:begin\nfoo\n", encoding="utf-8")
    report = scaffold.run(project, mode="init")
    assert (project / ".gitignore").read_text(encoding="utf-8") == "# lab-kit:begin\nfoo\n"
    assert report.count("warn") == 1


def _settings(project):
    return json.loads((project / ".claude" / "settings.json").read_text(encoding="utf-8"))


def test_init_registers_summary_hook(project):
    scaffold.run(project, mode="init")
    assert (project / ".claude" / "hooks" / "summary_guard.py").exists()
    hooks = _settings(project)["hooks"]
    for event in ("PostToolUse", "Stop", "SessionStart"):
        assert any(scaffold.HOOK_MARK in json.dumps(e) for e in hooks[event])


def test_init_keeps_existing_settings(project):
    own = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
    }
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(json.dumps(own), encoding="utf-8")

    scaffold.run(project, mode="init")
    settings = _settings(project)
    assert settings["permissions"] == own["permissions"]
    assert settings["hooks"]["Stop"][0] == own["hooks"]["Stop"][0]
    assert len(settings["hooks"]["Stop"]) == 2

    before = tree_hashes(project)
    report = scaffold.run(project, mode="init")
    assert tree_hashes(project) == before
    assert report.count("hooks-add") == 0


def test_update_replaces_only_our_hook_entry(project):
    scaffold.run(project, mode="init")
    settings = _settings(project)
    settings["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 5  # 古い版の項目を模す
    settings["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "echo mine"}]})
    (project / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    scaffold.run(project, mode="init")
    assert _settings(project)["hooks"]["Stop"][0]["hooks"][0].get("timeout") == 5

    scaffold.run(project, mode="update")
    stop_entries = _settings(project)["hooks"]["Stop"]
    assert stop_entries[0] == scaffold._hook_entry("Stop")
    assert stop_entries[1]["hooks"][0]["command"] == "echo mine"


def test_broken_settings_is_not_touched(project):
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    report = scaffold.run(project, mode="init")
    assert (project / ".claude" / "settings.json").read_text(encoding="utf-8") == "{not json"
    assert any(a == "warn" and "settings.json" in p for a, p, _ in report.entries)
