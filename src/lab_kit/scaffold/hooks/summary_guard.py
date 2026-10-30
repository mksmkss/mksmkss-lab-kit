#!/usr/bin/env python3
"""
issue のまとめ(本文)を、コメントのたびに必ず更新させる Claude Code のフック。

lab-kit が `.claude/hooks/summary_guard.py` に置き、`.claude/settings.json` に登録する。
標準ライブラリだけで動く(プロジェクトの環境に依存しない)。

- PostToolUse: issue にコメントしたら「まとめ未更新」に記録する。本文を書き換えたら外す。
- Stop: まとめ未更新の issue が残っていれば、ターンを終えさせず、更新を指示する。
- SessionStart: 前のセッションで残った「まとめ未更新」を知らせる。

記録は `.claude/summary-pending.json`(git には入れない)。
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

STATE_NAME = "summary-pending.json"
# Stop で続けて止める回数の上限。gh が使えないなどで直せないとき、無限に止め続けないため。
MAX_BLOCKS = 3

# gh の、値を取るオプション(番号と取り違えないため)
GH_VALUE_FLAGS = {
    "-b", "--body", "-F", "--body-file", "-R", "--repo", "-t", "--title",
    "-l", "--add-label", "--remove-label", "-a", "--add-assignee", "--remove-assignee",
    "-m", "--milestone", "-p", "--add-project", "--remove-project", "-c", "--comment",
    "-r", "--reason", "--jq", "-q", "--template", "-X", "--method", "-f", "--raw-field",
    "-H", "--header", "--input",
}
ISSUE_REF = re.compile(r"^(?:https://github\.com/([^/]+/[^/]+)/issues/)?#?(\d+)$")
API_ISSUE = re.compile(r"^/?repos/([^/]+/[^/]+)/issues/(\d+)(/comments)?/?$")
DISCUSSION_ID = re.compile(r"\bD_[A-Za-z0-9_-]+")


# ---------- 状態 ----------

def _state_path(cwd: str) -> Path:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or cwd or "."
    return Path(root) / ".claude" / STATE_NAME


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pending": {}, "blocks": 0}
    data.setdefault("pending", {})
    data.setdefault("blocks", 0)
    return data


def _save(path: Path, data: dict):
    if not data["pending"]:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _key(repo, number) -> str:
    return f"{repo}#{number}" if repo else f"#{number}"


# ---------- コマンドの解釈 ----------

def _split_commands(command: str):
    """`a && b; c | d` を、コマンドごとのトークン列に分ける。"""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    current = []
    for tok in tokens:
        if tok and set(tok) <= set(";&|()"):
            if current:
                yield current
            current = []
        else:
            current.append(tok)
    if current:
        yield current


def _option(tokens, *names):
    for i, tok in enumerate(tokens):
        for name in names:
            if tok == name and i + 1 < len(tokens):
                return tokens[i + 1]
            if name.startswith("--") and tok.startswith(name + "="):
                return tok.split("=", 1)[1]
    return None


def _has_option(tokens, *names) -> bool:
    return any(tok in names or any(tok.startswith(n + "=") for n in names) for tok in tokens)


def _positionals(tokens):
    out, skip = [], False
    for tok in tokens:
        if skip:
            skip = False
            continue
        if tok.startswith("-"):
            if tok in GH_VALUE_FLAGS:
                skip = True
            continue
        out.append(tok)
    return out


def _issue_target(args, repo_opt):
    for tok in _positionals(args):
        m = ISSUE_REF.match(tok)
        if m:
            return _key(m.group(1) or repo_opt, m.group(2))
    return None


def _api_fields(tokens) -> list:
    names = []
    for i, tok in enumerate(tokens):
        if tok in ("-f", "-F", "--field", "--raw-field") and i + 1 < len(tokens):
            names.append(tokens[i + 1].split("=", 1)[0])
    return names


def parse_bash(command: str):
    """
    Bash のコマンドから、(コメントした対象, 本文を書き換えた対象) を取り出す。
    対象は "owner/repo#N" か "#N"(リポジトリ省略)か "discussion:D_xxx"。
    """
    commented, edited = [], []
    for tokens in _split_commands(command):
        if "gh" not in tokens:
            continue
        tokens = tokens[tokens.index("gh") + 1:]
        if len(tokens) < 2:
            continue
        group, action, rest = tokens[0], tokens[1], tokens[2:]
        repo_opt = _option(rest, "-R", "--repo")

        if group == "issue":
            target = _issue_target(rest, repo_opt)
            if not target:
                continue
            if action == "comment":
                if _has_option(rest, "--edit-last", "--delete-last"):
                    continue
                commented.append(target)
            elif action == "close" and _has_option(rest, "-c", "--comment"):
                commented.append(target)
            elif action == "edit" and _has_option(rest, "-b", "--body", "-F", "--body-file"):
                edited.append(target)

        elif group == "api":
            rest = tokens[1:]  # api は、オプションがパスの前に来ることがある
            joined = " ".join(rest)
            if "addDiscussionComment" in joined or "updateDiscussion" in joined:
                ids = DISCUSSION_ID.findall(joined) or ["?"]
                bucket = commented if "addDiscussionComment" in joined else edited
                bucket.extend(f"discussion:{i}" for i in ids)
                continue
            endpoint = next((t for t in _positionals(rest) if API_ISSUE.match(t)), None)
            if not endpoint:
                continue
            m = API_ISSUE.match(endpoint)
            target = _key(m.group(1), m.group(2))
            method = (_option(rest, "-X", "--method") or "").upper()
            fields = _api_fields(rest)
            if m.group(3):
                if method == "POST" or (not method and (fields or _has_option(rest, "--input"))):
                    commented.append(target)
            elif method == "PATCH" and ("body" in fields or _has_option(rest, "--input")):
                edited.append(target)
    return commented, edited


def parse_mcp(tool_name: str, tool_input: dict):
    """GitHub の MCP ツールでの、コメント・本文の書き換え。"""
    number = tool_input.get("issue_number") or tool_input.get("issueNumber")
    if number is None:
        return [], []
    owner, repo = tool_input.get("owner"), tool_input.get("repo")
    target = _key(f"{owner}/{repo}" if owner and repo else None, number)
    name = tool_name.rsplit("__", 1)[-1]
    if name == "add_issue_comment":
        return [target], []
    if name in ("issue_write", "update_issue") and tool_input.get("body") is not None:
        return [], [target]
    return [], []


def _same(a: str, b: str) -> bool:
    """"#12" と "owner/repo#12" を同じものとみなす(リポジトリ省略時)。"""
    if a == b:
        return True
    if a.startswith("discussion:") or b.startswith("discussion:"):
        return a == "discussion:?" or b == "discussion:?"
    na, nb = a.rsplit("#", 1)[-1], b.rsplit("#", 1)[-1]
    return na == nb and (a.startswith("#") or b.startswith("#"))


# ---------- フック ----------

def _describe(pending: dict) -> str:
    return "、".join(f"{k}(コメント {v} 件)" for k, v in pending.items())


def _rule() -> str:
    return (
        "`decision-log` Skill の「まとめの型」に従い、本文の先頭の「現時点のまとめ」を、"
        "いま足したコメントの内容まで反映して書き直してください(最新の本文を取得してから直す。"
        "更新前のまとめは <details> に残す。「最終更新」の日付と、反映したコメントへのリンクを書く)。"
        "書き換えは `gh issue edit <N> --body-file <file>` で行うと、この確認が外れます。"
    )


def on_post_tool_use(event: dict):
    path = _state_path(event.get("cwd", ""))
    state = _load(path)
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool == "Bash":
        commented, edited = parse_bash(tool_input.get("command", ""))
    elif tool.startswith("mcp__"):
        commented, edited = parse_mcp(tool, tool_input)
    else:
        return

    for target in edited:
        for key in [k for k in state["pending"] if _same(k, target)]:
            del state["pending"][key]
    for target in commented:
        key = next((k for k in state["pending"] if _same(k, target)), target)
        state["pending"][key] = state["pending"].get(key, 0) + 1
    if commented or edited:
        state["blocks"] = 0
    _save(path, state)

    if commented and state["pending"]:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"まとめが未更新です: {_describe(state['pending'])}。"
                    "このターンを終える前に、本文のまとめを更新してください。" + _rule()
                ),
            }
        }, ensure_ascii=False))


def on_stop(event: dict):
    path = _state_path(event.get("cwd", ""))
    state = _load(path)
    if not state["pending"]:
        return
    if state["blocks"] >= MAX_BLOCKS:
        # 直せない状態で止め続けない。記録は残し、次のセッションの開始時にまた知らせる。
        print(json.dumps({
            "systemMessage": (
                f"[lab-kit] まとめが未更新のまま終わります: {_describe(state['pending'])}。"
                "次のセッションの開始時に、もう一度知らせます。"
            )
        }, ensure_ascii=False))
        state["blocks"] = 0
        _save(path, state)
        return
    state["blocks"] += 1
    _save(path, state)
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"issue にコメントを足しましたが、本文のまとめが未更新です: {_describe(state['pending'])}。"
            + _rule()
            + " gh が使えないなど、更新できない場合は、その理由をユーザーに伝えてください。"
        ),
    }, ensure_ascii=False))


def on_session_start(event: dict):
    state = _load(_state_path(event.get("cwd", "")))
    if not state["pending"]:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                f"前のセッションで、まとめが未更新のまま残った issue があります: "
                f"{_describe(state['pending'])}。最初に、これを更新してください。" + _rule()
            ),
        }
    }, ensure_ascii=False))


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    handlers = {
        "PostToolUse": on_post_tool_use,
        "Stop": on_stop,
        "SessionStart": on_session_start,
    }
    handler = handlers.get(event.get("hook_event_name", ""))
    if handler:
        handler(event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
