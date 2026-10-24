from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from lab_kit import (
    load_data_with_metadata,
    save_data_with_metadata,
    trace_data_lineage,
)


@pytest.fixture
def df():
    return pd.DataFrame({"id": [1, 2, 3], "value": [0.1, 0.2, 0.3], "name": ["あ", "い", "う"]})


@pytest.mark.parametrize("fmt, ext", [("csv", "csv"), ("parquet", "parquet"), ("sqlite", "db")])
def test_dataframe_roundtrip(tmp_path, df, fmt, ext):
    out = tmp_path / "sub" / f"data.{ext}"
    save_data_with_metadata(df, out, created_by="test.py", format=fmt)
    loaded, meta = load_data_with_metadata(out)
    pd.testing.assert_frame_equal(loaded, df)
    assert meta["created_by"] == "test.py"
    assert meta["rows"] == 3
    assert (tmp_path / "sub" / "data_metadata.yaml").exists()


def test_numpy_and_pickle_roundtrip(tmp_path):
    arr = np.arange(6, dtype=float).reshape(2, 3)
    save_data_with_metadata(arr, tmp_path / "a.npy", created_by="t.py", format="npy")
    loaded, meta = load_data_with_metadata(tmp_path / "a.npy")
    np.testing.assert_array_equal(loaded, arr)
    assert meta["shape"] == [2, 3]

    save_data_with_metadata(np.array([1]), tmp_path / "b.pkl", created_by="t.py", format="pickle")
    loaded, _ = load_data_with_metadata(tmp_path / "b.pkl")
    np.testing.assert_array_equal(loaded, np.array([1]))


def test_created_by_is_required(tmp_path, df):
    with pytest.raises(ValueError):
        save_data_with_metadata(df, tmp_path / "x.csv", created_by=None)
    with pytest.raises(ValueError):
        save_data_with_metadata(df, tmp_path / "x.csv", created_by="")


def test_unsupported_format_raises(tmp_path, df):
    with pytest.raises(ValueError):
        save_data_with_metadata(df, tmp_path / "x.xyz", created_by="t.py", format="xyz")


def test_metadata_is_plain_yaml_with_path_and_numpy_values(tmp_path, df):
    save_data_with_metadata(
        df,
        tmp_path / "x.csv",
        created_by="t.py",
        source_info=tmp_path / "raw.csv",
        config={"alpha": np.float64(0.3), "seeds": (0, 1), "dir": Path("a/b")},
    )
    text = (tmp_path / "x_metadata.yaml").read_text(encoding="utf-8")
    assert "!!python" not in text
    meta = yaml.safe_load(text)  # safe_load で読める = python 固有のタグがない
    assert meta["config"] == {"alpha": 0.3, "seeds": [0, 1], "dir": "a/b"}
    assert meta["source_info"] == str(tmp_path / "raw.csv")


def test_filename_only_output_path(tmp_path, df, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_data_with_metadata(df, "plain.csv", created_by="t.py")
    assert (tmp_path / "plain.csv").exists()


def test_sklearn_model_metadata(tmp_path):
    sklearn = pytest.importorskip("sklearn.preprocessing")
    le = sklearn.LabelEncoder().fit(["a", "b", "a"])
    save_data_with_metadata(le, tmp_path / "le.pkl", created_by="t.py", format="pickle")
    loaded, meta = load_data_with_metadata(tmp_path / "le.pkl")
    assert list(loaded.classes_) == ["a", "b"]
    assert meta["classes"] == ["a", "b"]


def test_trace_data_lineage(tmp_path, df):
    raw = tmp_path / "raw.csv"
    save_data_with_metadata(df, raw, created_by="make_raw.py")
    mid = tmp_path / "mid.csv"
    save_data_with_metadata(df, mid, created_by="clean.py", source_info=str(raw))
    final = tmp_path / "final.csv"
    save_data_with_metadata(df, final, created_by="train.py", source_info=str(mid))

    lineage = trace_data_lineage(str(final))
    top = lineage[str(final)]
    assert top["created_by"] == "train.py"
    mid_node = top["children"][str(mid)]
    assert mid_node["created_by"] == "clean.py"
    assert mid_node["children"][str(raw)]["created_by"] == "make_raw.py"


def test_trace_data_lineage_depth_limit_and_missing_metadata(tmp_path, df):
    raw = tmp_path / "raw.csv"
    df.to_csv(raw, index=False)  # メタデータなしの元データ
    mid = tmp_path / "mid.csv"
    save_data_with_metadata(df, mid, created_by="clean.py", source_info=str(raw))
    final = tmp_path / "final.csv"
    save_data_with_metadata(df, final, created_by="train.py", source_info=[str(mid)])

    full = trace_data_lineage(final)[str(final)]
    assert full["children"][str(mid)]["children"][str(raw)] == {"note": "メタデータなし"}

    limited = trace_data_lineage(final, depth=1)[str(final)]
    assert "children" in limited
    assert "children" not in limited["children"][str(mid)]


def test_trace_data_lineage_cycle_does_not_loop(tmp_path, df):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    save_data_with_metadata(df, a, created_by="a.py", source_info=str(b))
    save_data_with_metadata(df, b, created_by="b.py", source_info=str(a))
    lineage = trace_data_lineage(a)
    assert lineage[str(a)]["children"][str(b)]["created_by"] == "b.py"
