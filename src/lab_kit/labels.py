"""`lab-kit labels`: decision-log が使う GitHub ラベルを作る（無いものだけ）。"""

import shutil
import subprocess

# (名前, 色, 説明)
STAGE_LABELS = [
    ("idea", "FBCA04", "考え中。方針が未確定"),
    ("decided", "1D76DB", "方針が固まり、実装の直前"),
    ("doing", "F9A03F", "実装・実験中"),
    ("done", "0E8A16", "完了"),
]
MEETING_LABEL = ("meeting", "8957E5", "先生・共同研究者との相談の記録")
DEFAULT_KIND_LABELS = [
    ("experiment", "C5DEF5", "実験・評価の結果を扱う"),
    ("method", "BFD4F2", "手法・モデルの変更"),
    ("data", "D4C5F9", "データの作成・加工・前処理"),
    ("analysis", "BFDADC", "分析・可視化"),
]
FALLBACK_COLOR = "EDEDED"


def run_gh(args: list) -> subprocess.CompletedProcess:
    """gh を実行する（テストで差し替えられるよう、関数に分けてある）"""
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def wanted_labels(kinds) -> list:
    """作りたいラベルの一覧。kinds は None / "default" / カンマ区切りの名前。"""
    labels = [*STAGE_LABELS, MEETING_LABEL]
    if kinds:
        known = {name: (name, color, desc) for name, color, desc in DEFAULT_KIND_LABELS}
        names = (
            [n for n, _, _ in DEFAULT_KIND_LABELS]
            if kinds == "default"
            else [k.strip() for k in kinds.split(",") if k.strip()]
        )
        for name in names:
            labels.append(known.get(name, (name, FALLBACK_COLOR, "")))
    return labels


def _repo_path(repo) -> str:
    """REST の URL に使うリポジトリ部分。省略時は gh が、いまのフォルダのリポジトリに置き換える。"""
    return repo if repo else "{owner}/{repo}"


def run(kinds=None, repo=None, dry_run: bool = False) -> int:
    """
    足りないラベルを作る。既にあるラベルは変更しない。

    GraphQL が使えない環境でも動くよう、`gh label` ではなく REST(`gh api`)を使う。

    Returns:
    --------
    int
        終了コード（0: 成功、1: gh が使えない、など）
    """
    if shutil.which("gh") is None:
        print("gh(GitHub CLI) が見つかりません。https://cli.github.com/ から入れてください。")
        return 1

    base = f"repos/{_repo_path(repo)}/labels"
    listed = run_gh(["api", f"{base}?per_page=100", "--paginate", "--jq", ".[].name"])
    if listed.returncode != 0:
        print(
            "ラベル一覧を取得できませんでした。`gh auth login` 済みか、リポジトリの中か確認してください。"
        )
        print(listed.stderr.strip())
        return 1

    existing = {line.strip().lower() for line in listed.stdout.splitlines() if line.strip()}
    created, skipped = [], []
    for name, color, description in wanted_labels(kinds):
        if name.lower() in existing:
            skipped.append(name)
            continue
        created.append(name)
        command = ["api", "-X", "POST", base, "-f", f"name={name}", "-f", f"color={color}"]
        if description:
            command += ["-f", f"description={description}"]
        if dry_run:
            print("[dry-run] gh " + " ".join(command))
            continue
        result = run_gh(command)
        if result.returncode != 0:
            print(f"ラベル '{name}' を作れませんでした: {result.stderr.strip()}")
            return 1

    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}作成: {', '.join(created) if created else 'なし'}")
    print(f"{prefix}既にある(変更なし): {', '.join(skipped) if skipped else 'なし'}")
    return 0
