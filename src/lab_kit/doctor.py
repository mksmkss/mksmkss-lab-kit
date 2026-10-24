"""`lab-kit doctor`: 環境を確認して、足りないものを平易な日本語で伝える。"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

OK, WARN, NG = "OK ", "注意", "NG "


def _run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def check(root) -> list:
    """確認結果の一覧 [(状態, 項目, メッセージ)] を返す。"""
    root = Path(root).resolve()
    results = []

    # Python
    if sys.version_info >= (3, 10):
        results.append((OK, "Python", sys.version.split()[0]))
    else:
        results.append((NG, "Python", f"{sys.version.split()[0]} です。3.10 以上が必要です"))

    # git
    if shutil.which("git") is None:
        results.append((NG, "git", "見つかりません。https://git-scm.com/ から入れてください"))
    elif (root / ".git").exists():
        results.append((OK, "git", "このフォルダは git リポジトリです"))
    else:
        results.append(
            (WARN, "git", "このフォルダは git リポジトリではありません(`git init` で作れます)")
        )

    # uv
    if shutil.which("uv"):
        results.append((OK, "uv", "入っています"))
    else:
        results.append(
            (WARN, "uv", "見つかりません。https://docs.astral.sh/uv/ から入れてください")
        )

    # gh
    if shutil.which("gh") is None:
        results.append(
            (
                WARN,
                "gh",
                "見つかりません。decision-log(issue に残す機能)に必要です。https://cli.github.com/",
            )
        )
    else:
        auth = _run(["gh", "auth", "status"])
        if auth.returncode == 0:
            results.append((OK, "gh", "ログイン済みです"))
            repo = _run(["gh", "repo", "view", "--json", "nameWithOwner,visibility"])
            if repo.returncode == 0:
                info = json.loads(repo.stdout)
                visibility = info.get("visibility", "")
                note = f"{info.get('nameWithOwner')} ({visibility})"
                if visibility == "PUBLIC":
                    note += " 公開リポジトリです。相談の記録(meeting)は作らないでください"
                    results.append((WARN, "GitHub", note))
                else:
                    results.append((OK, "GitHub", note))
            else:
                results.append(
                    (WARN, "GitHub", "このフォルダに対応する GitHub リポジトリが見つかりません")
                )
        else:
            results.append((WARN, "gh", "ログインしていません。`gh auth login` を実行してください"))

    # lab-kit の足場
    if (root / ".lab-kit" / "manifest.json").exists():
        results.append((OK, "lab-kit init", "済みです"))
    else:
        results.append((WARN, "lab-kit init", "まだです。`uv run lab-kit init` を実行してください"))

    if (root / ".claude" / "skills" / "decision-log" / "SKILL.md").exists():
        results.append((OK, "Skill", "decision-log があります"))
    else:
        results.append(
            (WARN, "Skill", "decision-log がありません。`uv run lab-kit init` で入ります")
        )

    # 任意
    if importlib.util.find_spec("kaleido"):
        results.append((OK, "kaleido", "図を PNG で保存できます"))
    else:
        results.append(
            (WARN, "kaleido", "未インストール。PNG 保存には `uv add kaleido` が必要です")
        )

    return results


def run(root) -> int:
    """結果を表示し、終了コード（NG があれば 1）を返す。"""
    results = check(root)
    for status, name, message in results:
        print(f"[{status}] {name}: {message}")
    ng = sum(1 for status, _, _ in results if status == NG)
    warn = sum(1 for status, _, _ in results if status == WARN)
    print()
    if ng:
        print(f"直す必要があるもの: {ng} 件(注意: {warn} 件)")
        return 1
    print("必須の項目は問題ありません" + (f"(注意: {warn} 件)" if warn else ""))
    return 0
