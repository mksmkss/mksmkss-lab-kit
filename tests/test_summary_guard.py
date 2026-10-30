import json
import subprocess
import sys
from pathlib import Path

import pytest

from lab_kit import scaffold

HOOK = Path(scaffold.SCAFFOLD_DIR) / "hooks" / "summary_guard.py"


def call(project: Path, event: dict) -> dict:
    """フックを、Claude Code と同じく stdin に JSON を渡して実行する。"""
    event = {"cwd": str(project), **event}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={"CLAUDE_PROJECT_DIR": str(project), "PATH": ""},
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def bash(project, command):
    return call(
        project,
        {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": command}},
    )


def stop(project):
    return call(project, {"hook_event_name": "Stop", "stop_hook_active": False})


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".claude").mkdir()
    return tmp_path


def test_comment_without_summary_update_blocks_stop(project):
    out = bash(project, "gh issue comment 12 --body-file /tmp/c.md")
    assert "#12" in out["hookSpecificOutput"]["additionalContext"]
    assert stop(project)["decision"] == "block"


def test_body_edit_clears_pending(project):
    bash(project, "gh issue comment 12 --body-file /tmp/c.md")
    bash(project, "gh issue view 12 --json body --jq .body > b.md && gh issue edit 12 --body-file b.md")
    assert stop(project) == {}
    assert not (project / ".claude" / "summary-pending.json").exists()


def test_label_only_edit_does_not_clear(project):
    bash(project, "gh issue comment 12 -F c.md")
    bash(project, "gh issue edit 12 --add-label doing --remove-label decided")
    assert stop(project)["decision"] == "block"


def test_other_issue_edit_does_not_clear(project):
    bash(project, "gh issue comment 12 -F c.md")
    bash(project, "gh issue edit 13 --body-file b.md")
    assert stop(project)["decision"] == "block"


def test_new_issue_and_unrelated_commands_are_ignored(project):
    bash(project, "gh issue create --title t --body-file b.md --label idea")
    bash(project, "git commit -m 'gh issue comment 5'")
    bash(project, "gh issue view 12 --comments")
    assert stop(project) == {}


@pytest.mark.parametrize(
    "command",
    [
        "gh issue comment https://github.com/o/r/issues/7 --body x",
        "gh issue comment --body-file c.md 7",
        "gh issue close 7 --comment 'done'",
        "gh api repos/o/r/issues/7/comments -f body=@c.md",
        "cd x && gh issue comment 7 -b hi; echo ok",
    ],
)
def test_comment_forms_are_detected(project, command):
    bash(project, command)
    assert stop(project)["decision"] == "block"


def test_api_patch_body_clears_and_repo_forms_match(project):
    bash(project, "gh issue comment 7 -R o/r -b hi")
    bash(project, "gh api -X PATCH repos/o/r/issues/7 -F body=@b.md")
    assert stop(project) == {}


def test_mcp_tools(project):
    call(
        project,
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__github__add_issue_comment",
            "tool_input": {"owner": "o", "repo": "r", "issue_number": 3, "body": "x"},
        },
    )
    assert stop(project)["decision"] == "block"
    call(
        project,
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__github__issue_write",
            "tool_input": {
                "method": "update", "owner": "o", "repo": "r", "issue_number": 3, "body": "y",
            },
        },
    )
    assert stop(project) == {}


def test_stop_gives_up_after_limit_and_reminds_next_session(project):
    bash(project, "gh issue comment 12 -b hi")
    for _ in range(3):
        assert stop(project)["decision"] == "block"
    last = stop(project)
    assert "decision" not in last and "#12" in last["systemMessage"]

    start = call(project, {"hook_event_name": "SessionStart", "source": "startup"})
    assert "#12" in start["hookSpecificOutput"]["additionalContext"]
    # 記録は残っているので、次のセッションでもまた止める
    assert stop(project)["decision"] == "block"


def test_broken_state_file_is_tolerated(project):
    (project / ".claude" / "summary-pending.json").write_text("{broken", encoding="utf-8")
    assert stop(project) == {}
