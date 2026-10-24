"""
`lab-kit init` / `lab-kit update` の本体。

方針: 既存ファイルを壊さない。
- 無いファイルは作る。
- 同じ内容のファイルは何もしない。
- 内容が違うファイルは上書きせず、横に `*.lab-kit.new` を置いて差分を見せる。
- `.gitignore` と `CLAUDE.md` は、`lab-kit:begin` 〜 `lab-kit:end` の管理ブロックだけを追記・更新する。
- `update` は、前回配ったときから変更されていないファイルだけを更新する。
"""

import difflib
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from lab_kit import __version__

SCAFFOLD_DIR = Path(__file__).parent / "scaffold"
MANIFEST_PATH = Path(".lab-kit") / "manifest.json"
NEW_SUFFIX = ".lab-kit.new"

# 管理ブロック: 配布先ファイル -> (開始マーカー, 終了マーカー, 元ファイル)
MANAGED_BLOCKS = {
    "CLAUDE.md": ("<!-- lab-kit:begin -->", "<!-- lab-kit:end -->", "blocks/CLAUDE.md.block"),
    ".gitignore": ("# lab-kit:begin", "# lab-kit:end", "blocks/gitignore.block"),
}

# 単独のファイル: 配布先 -> 元ファイル（scaffold/ からの相対）
SINGLE_FILES = {
    ".env.example": "env.example",
    "notebooks/_template.py": "notebook_template.py",
}

# 空フォルダを git に残すための .gitkeep
KEEP_DIRS = ["data/raw", "data/interim", "data/processed", "results"]


@dataclass
class Report:
    """何をしたか（またはしようとしたか）の記録"""

    entries: list = field(default_factory=list)

    def add(self, action: str, path: str, note: str = ""):
        self.entries.append((action, path, note))

    def count(self, action: str) -> int:
        return sum(1 for a, _, _ in self.entries if a == action)

    def print(self, dry_run: bool):
        labels = {
            "create": "作成",
            "update": "更新",
            "skip": "変更なし",
            "conflict": "差分あり(上書きせず)",
            "block-add": "ブロック追記",
            "block-update": "ブロック更新",
            "block-skip": "ブロック変更なし",
            "link": "リンク作成",
            "warn": "注意",
        }
        prefix = "[dry-run] " if dry_run else ""
        for action, path, note in self.entries:
            line = f"{prefix}{labels.get(action, action):<12} {path}"
            print(f"{line}  {note}" if note else line)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _scaffold_files() -> dict:
    """配布するファイルの一覧: 配布先(相対, POSIX表記) -> 内容(bytes)"""
    files = {}
    for dest, src in SINGLE_FILES.items():
        files[dest] = (SCAFFOLD_DIR / src).read_bytes()

    skills_dir = SCAFFOLD_DIR / "skills"
    for src in sorted(skills_dir.rglob("*")):
        if src.is_file() and "__pycache__" not in src.parts:
            rel = src.relative_to(skills_dir).as_posix()
            files[f".claude/skills/{rel}"] = src.read_bytes()

    for directory in KEEP_DIRS:
        files[f"{directory}/.gitkeep"] = b""
    return files


def _load_manifest(root: Path) -> dict:
    path = root / MANIFEST_PATH
    if not path.exists():
        return {"version": None, "files": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": None, "files": {}}


def _save_manifest(root: Path, files: dict):
    path = root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"version": __version__, "files": dict(sorted(files.items()))}
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _short_diff(old: bytes, new: bytes, name: str, max_lines: int = 20) -> str:
    try:
        old_lines = old.decode("utf-8").splitlines()
        new_lines = new.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return "(テキストではないため差分は表示しません)"
    diff = list(
        difflib.unified_diff(
            old_lines, new_lines, fromfile=f"{name} (いま)", tofile=f"{name} (lab-kit)", lineterm=""
        )
    )
    shown = diff[:max_lines]
    if len(diff) > max_lines:
        shown.append(f"... (残り {len(diff) - max_lines} 行)")
    return "\n".join(shown)


def _sync_files(root: Path, mode: str, dry_run: bool, report: Report, manifest_files: dict):
    """単独ファイル(Skill を含む)を配る。mode は "init" か "update"。"""
    old_hashes = _load_manifest(root)["files"]

    for dest, content in _scaffold_files().items():
        target = root / dest
        new_hash = _sha256(content)

        if not target.exists():
            report.add("create", dest)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            manifest_files[dest] = new_hash
            continue

        current = target.read_bytes()
        current_hash = _sha256(current)

        if current_hash == new_hash:
            report.add("skip", dest)
            manifest_files[dest] = new_hash
            continue

        unmodified_by_user = old_hashes.get(dest) == current_hash
        if mode == "update" and unmodified_by_user:
            report.add("update", dest)
            if not dry_run:
                target.write_bytes(content)
            manifest_files[dest] = new_hash
            continue

        # 利用者が編集したか、init で既に別の内容がある: 上書きしない
        new_path = target.with_name(target.name + NEW_SUFFIX)
        report.add("conflict", dest, f"-> {new_path.relative_to(root).as_posix()}")
        if not dry_run:
            new_path.write_bytes(content)
        if dry_run:
            print(_short_diff(current, content, dest))
        if dest in old_hashes:
            manifest_files[dest] = old_hashes[dest]


def _block_text(begin: str, end: str, body: str) -> str:
    return f"{begin}\n{body.rstrip()}\n{end}\n"


def _sync_blocks(root: Path, mode: str, dry_run: bool, report: Report):
    """`.gitignore` と `CLAUDE.md` の管理ブロックを追記・更新する。"""
    for dest, (begin, end, src) in MANAGED_BLOCKS.items():
        body = (SCAFFOLD_DIR / src).read_text(encoding="utf-8")
        block = _block_text(begin, end, body)
        target = root / dest

        if not target.exists():
            report.add("create", dest, "(管理ブロックのみ)")
            if not dry_run:
                target.write_text(block, encoding="utf-8")
            continue

        text = target.read_text(encoding="utf-8")
        has_begin = begin in text
        has_end = end in text

        if has_begin != has_end:
            report.add(
                "warn",
                dest,
                "管理ブロックの開始/終了マーカーが片方しかありません。手で直してください",
            )
            continue

        if not has_begin:
            report.add("block-add", dest)
            if not dry_run:
                separator = "" if text == "" else ("\n" if text.endswith("\n") else "\n\n")
                target.write_text(text + separator + block, encoding="utf-8")
            continue

        start_idx = text.index(begin)
        end_idx = text.index(end, start_idx) + len(end)
        # 終了マーカーの直後の改行も、ブロックに含めて置き換える
        if text[end_idx : end_idx + 1] == "\n":
            end_idx += 1
        current_block = text[start_idx:end_idx]

        if current_block == block:
            report.add("block-skip", dest)
        elif mode == "update":
            report.add("block-update", dest)
            if not dry_run:
                target.write_text(text[:start_idx] + block + text[end_idx:], encoding="utf-8")
        else:
            report.add("block-skip", dest, "(既にブロックがあります。更新は `lab-kit update`)")


def _link_agents(root: Path, dry_run: bool, report: Report):
    """.agents/skills/<name> から .claude/skills/<name> へのシンボリックリンクを作る。"""
    skills_dir = SCAFFOLD_DIR / "skills"
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        link = root / ".agents" / "skills" / skill.name
        rel = f".agents/skills/{skill.name}"
        if link.exists() or link.is_symlink():
            report.add("skip", rel)
            continue
        report.add("link", rel, f"-> ../../.claude/skills/{skill.name}")
        if not dry_run:
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(f"../../.claude/skills/{skill.name}", link)


def run(root, mode: str = "init", dry_run: bool = False, agents: bool = False) -> Report:
    """
    足場を配る。

    Parameters:
    -----------
    root : str or Path
        配布先（自分のプロジェクトのルート）
    mode : str
        "init"（初回。既存ファイルは上書きしない）か
        "update"（変更されていないファイルと管理ブロックを最新にする）
    dry_run : bool
        True なら、何もせず予定だけ表示する
    agents : bool
        True なら `.agents/skills/` にもリンクを作る
    """
    if mode not in {"init", "update"}:
        raise ValueError("mode は 'init' か 'update' です")

    root = Path(root).resolve()
    report = Report()

    if not any((root / marker).exists() for marker in (".git", "pyproject.toml")):
        report.add(
            "warn", str(root), "ここは .git も pyproject.toml もありません。正しいフォルダですか"
        )

    manifest_files: dict = {}
    _sync_files(root, mode, dry_run, report, manifest_files)
    _sync_blocks(root, mode, dry_run, report)
    if agents:
        _link_agents(root, dry_run, report)

    if not dry_run:
        _save_manifest(root, manifest_files)
    return report
