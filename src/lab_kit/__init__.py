"""研究用の共通道具。使い方は README を参照。"""

from importlib.metadata import PackageNotFoundError, version

from lab_kit.device import get_device
from lab_kit.io import (
    check_sqlite_database,
    load_data_with_metadata,
    save_data_with_metadata,
    trace_data_lineage,
)
from lab_kit.paths import data_path, project_root, results_path

try:
    __version__ = version("lab-kit")
except PackageNotFoundError:  # 開発中など、インストールされていないとき
    __version__ = "0.0.0"

__all__ = [
    "check_sqlite_database",
    "data_path",
    "get_device",
    "load_data_with_metadata",
    "project_root",
    "results_path",
    "save_data_with_metadata",
    "trace_data_lineage",
]
