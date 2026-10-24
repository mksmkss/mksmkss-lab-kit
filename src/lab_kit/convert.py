"""
`lab-kit to-marimo`: Jupyter ノートブック(.ipynb)を marimo(.py)に一括変換する。

- 元の .ipynb は消さない(出力は変換時に消える。必要なら先に別名で控える)
- 同名の .py が既にあれば、上書きせず飛ばす
- 変換後に `marimo check` をかけ、直す必要がありそうなものを知らせる
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm

EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".ipynb_checkpoints"}


def find_notebooks(root, paths=None) -> list:
    """変換対象の .ipynb を返す。paths を渡せば、そのファイル・フォルダだけを対象にする。"""
    root = Path(root).resolve()
    targets = [Path(p).resolve() for p in paths] if paths else [root]
    found = []
    for target in targets:
        if target.is_file():
            if target.suffix == ".ipynb":
                found.append(target)
            continue
        for path in sorted(target.rglob("*.ipynb")):
            if not EXCLUDE_DIRS & set(path.relative_to(target).parts):
                found.append(path)
    return sorted(set(found))


def marimo_command():
    """marimo を呼ぶコマンドの先頭部分。見つからなければ None。"""
    if importlib.util.find_spec("marimo"):
        return [sys.executable, "-m", "marimo"]
    if shutil.which("marimo"):
        return ["marimo"]
    if shutil.which("uvx"):
        return ["uvx", "marimo"]
    return None


def run_marimo(args: list) -> subprocess.CompletedProcess:
    """marimo を実行する(テストで差し替えられるよう、関数に分けてある)"""
    command = marimo_command()
    if command is None:
        raise FileNotFoundError("marimo も uvx も見つかりません")
    return subprocess.run([*command, *args], capture_output=True, text=True)


def run(root, paths=None, dry_run: bool = False, check: bool = True) -> int:
    """
    ノートブックを変換する。

    Returns:
    --------
    int
        終了コード(0: 失敗なし、1: 変換に失敗したものがある、または marimo がない)
    """
    root = Path(root).resolve()
    notebooks = find_notebooks(root, paths)
    if not notebooks:
        print("変換する .ipynb が見つかりませんでした。")
        return 0

    if not dry_run and marimo_command() is None:
        print("marimo が見つかりません。`uv add marimo` か、uv を入れてください。")
        return 1

    converted, skipped, failed, to_fix = [], [], [], []
    for notebook in tqdm(notebooks, desc="変換", unit="件", disable=dry_run):
        out = notebook.with_suffix(".py")
        rel = notebook.relative_to(root).as_posix() if root in notebook.parents else str(notebook)
        if out.exists():
            skipped.append(rel)
            print(f"飛ばす  {rel}  (同名の .py が既にあります)")
            continue
        if dry_run:
            converted.append(rel)
            print(f"[dry-run] 変換  {rel} -> {out.name}")
            continue

        result = run_marimo(["convert", str(notebook), "-o", str(out)])
        if result.returncode != 0 or not out.exists():
            failed.append(rel)
            lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
            print(f"失敗    {rel}: {lines[-1][:200] if lines else '原因不明'}")
            continue
        converted.append(rel)
        if check and run_marimo(["check", str(out)]).returncode != 0:
            to_fix.append(out.relative_to(root).as_posix() if root in out.parents else str(out))

    prefix = "[dry-run] " if dry_run else ""
    print()
    print(
        f"{prefix}変換: {len(converted)} 件 / 飛ばした: {len(skipped)} 件 / 失敗: {len(failed)} 件"
    )
    if to_fix:
        print("`marimo check` で指摘があるため、直す必要があります:")
        for item in to_fix:
            print(f"  - {item}")
        print("(変数名の重複など。Claude に「marimo-notebook の Skill で直して」と頼めます)")
    if converted and not dry_run:
        print("元の .ipynb は残してあります。動作を確認してから、消すかどうかを決めてください。")
    return 1 if failed else 0
