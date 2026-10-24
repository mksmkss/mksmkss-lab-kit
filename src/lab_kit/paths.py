"""
プロジェクトルートの検出と、data/ results/ 配下のパス組み立て。

ルートの決め方（上が優先）:
1. 環境変数 `MAIN_PATH`
2. カレントディレクトリ（または start）から上へたどった最初の `.env` にある `MAIN_PATH`
3. 上へたどって最初に見つかる `.git` か `pyproject.toml` があるディレクトリ

`sys.path.append(...)` や、絶対パスの直書きは不要になる。
"""

import os
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

ROOT_MARKERS = (".git", "pyproject.toml")


def project_root(start=None) -> Path:
    """プロジェクトルートを返す。見つからなければ FileNotFoundError。"""
    env_root = os.environ.get("MAIN_PATH")
    if env_root:
        return Path(env_root).expanduser().resolve()

    start_dir = Path(start).resolve() if start is not None else Path.cwd().resolve()
    if start_dir.is_file():
        start_dir = start_dir.parent

    dotenv_path = find_dotenv(usecwd=True) if start is None else _find_up(start_dir, ".env")
    if dotenv_path:
        value = dotenv_values(dotenv_path).get("MAIN_PATH")
        if value:
            return Path(value).expanduser().resolve()

    for directory in (start_dir, *start_dir.parents):
        if any((directory / marker).exists() for marker in ROOT_MARKERS):
            return directory

    raise FileNotFoundError(
        "プロジェクトルートが見つかりません。"
        ".git か pyproject.toml があるフォルダで実行するか、環境変数 MAIN_PATH を設定してください。"
    )


def _find_up(start_dir: Path, name: str):
    for directory in (start_dir, *start_dir.parents):
        candidate = directory / name
        if candidate.is_file():
            return str(candidate)
    return None


def data_path(*parts) -> Path:
    """<root>/data/<parts...>"""
    return project_root().joinpath("data", *parts)


def results_path(*parts) -> Path:
    """<root>/results/<parts...>"""
    return project_root().joinpath("results", *parts)
