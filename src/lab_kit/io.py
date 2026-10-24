"""
データを保存するとき、作成者・元データ・処理内容を `*_metadata.yaml` として横に残す。

データ本体は git に入れず、メタ情報だけを追跡することで、
「このデータはどこから、どう作ったか」を後から辿れるようにする。
"""

import inspect
import os
import pickle
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _to_yamlable(obj):
    """
    YAML に安全に書き出せる形へ変換する（Path、numpy の数値、tuple、set など）

    config や source_info に Path や numpy.float64 が入っていても、
    yaml.dump が python 固有のタグを書き出さないようにする。
    """
    if isinstance(obj, dict):
        return {str(k): _to_yamlable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_yamlable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def save_data_with_metadata(
    data,
    output_path,
    created_by,
    source_info=None,
    processing_steps=None,
    config=None,
    format="csv",
    table_name=None,
):
    """
    データフレーム、NumPy配列、または機械学習モデルを処理し、指定された形式で保存し、メタデータを追加する関数

    Parameters:
    -----------
    data : pandas.DataFrame, numpy.ndarray, torch.Tensor, umap.UMAP, or sklearn model
        保存するデータ
    output_path : str
        出力ファイルのパス
    created_by : str
        データ作成者・作成スクリプト名（必須）
    source_info : str, list, dict, optional
        元データの情報
    processing_steps : list, optional
        実行した処理ステップのリスト
    config : dict, optional
        処理時の設定情報
    format : str, default "csv"
        出力形式（"csv", "parquet", "npy", "pt", "pickle", "sqlite"）。"pt"はtorch.Tensor用
    table_name : str, optional
        SQLite使用時のテーブル名（指定しない場合はファイル名から自動生成）

    Returns:
    --------
    data : pandas.DataFrame, numpy.ndarray, umap.UMAP, or sklearn model
        入力されたデータ（そのまま返却）

    Raises:
    -------
    ValueError
        created_byが指定されていない場合、またはサポートされていない形式の場合
    """
    import hashlib
    import os
    from datetime import datetime

    import numpy as np
    import pandas as pd
    import yaml

    # created_byの必須チェック
    if created_by is None or created_by == "":
        raise ValueError("created_by is required and cannot be None or empty string")

    if not isinstance(created_by, str):
        raise ValueError("created_by must be a string")

    # 処理ステップがNoneの場合は空リストを使用
    if processing_steps is None:
        processing_steps = []

    # Path も受け付ける
    output_path = os.fspath(output_path)

    # 出力ディレクトリがなければ作成（ファイル名だけの指定ならカレントディレクトリ）
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # ファイル名の拡張子を取得（後でメタデータ用に使用）
    base_path, _ = os.path.splitext(output_path)

    # データの種類を判定
    is_dataframe = isinstance(data, pd.DataFrame)
    is_numpy = isinstance(data, np.ndarray)

    # torch.Tensorの判定（モジュールが存在する場合のみ）
    is_torch = False
    try:
        import torch

        is_torch = isinstance(data, torch.Tensor)
    except ImportError:
        pass

    # UMAPオブジェクトの判定（モジュールが存在する場合のみ）
    is_umap = False
    try:
        import umap.umap_ as umap_module

        is_umap = isinstance(data, umap_module.UMAP)
    except ImportError:
        pass

    # scikit-learnモデルの判定
    is_sklearn_model = False
    try:
        from sklearn.base import BaseEstimator

        is_sklearn_model = isinstance(data, BaseEstimator)
    except ImportError:
        pass

    # その他の機械学習モデルの判定（LabelEncoder、PCA等）
    is_ml_object = False
    if not (is_dataframe or is_numpy or is_torch or is_umap or is_sklearn_model):
        # sklearn以外のMLオブジェクトも含める
        ml_object_types = [
            "LabelEncoder",
            "StandardScaler",
            "MinMaxScaler",
            "PCA",
            "TruncatedSVD",
            "Pipeline",
            "GridSearchCV",
            "RandomizedSearchCV",
        ]
        is_ml_object = any(obj_type in str(type(data)) for obj_type in ml_object_types)

    if not (is_dataframe or is_numpy or is_torch or is_umap or is_sklearn_model or is_ml_object):
        raise ValueError(
            "data must be pandas.DataFrame, numpy.ndarray, torch.Tensor, umap.UMAP, "
            "sklearn model, or other machine learning object"
        )

    # データハッシュを計算（データの追跡性向上のため）
    if is_dataframe:
        data_hash = hashlib.md5(np.asarray(pd.util.hash_pandas_object(data)).tobytes()).hexdigest()
    elif is_numpy:  # numpy array
        data_hash = hashlib.md5(data.tobytes()).hexdigest()
    elif is_torch:  # torch tensor
        data_hash = hashlib.md5(data.detach().cpu().numpy().tobytes()).hexdigest()
    else:  # UMAP, sklearn models, or other objects
        # オブジェクトは文字列表現でハッシュ化
        data_hash = hashlib.md5(str(data).encode("utf-8")).hexdigest()

    # 指定された形式で保存
    if format.lower() == "npy":
        if not is_numpy:
            raise ValueError("npy format requires numpy.ndarray input")
        actual_path = f"{base_path}.npy"
        np.save(actual_path, data)

    elif format.lower() == "pt":
        if not is_torch:
            raise ValueError("pt format requires torch.Tensor input")
        actual_path = f"{base_path}.pt"
        torch.save(data, actual_path)

    elif format.lower() == "csv":
        if not is_dataframe:
            raise ValueError("csv format requires pandas.DataFrame input")
        actual_path = f"{base_path}.csv"
        data.to_csv(actual_path, index=False)

    elif format.lower() == "parquet":
        if not is_dataframe:
            raise ValueError("parquet format requires pandas.DataFrame input")
        actual_path = f"{base_path}.parquet"
        data.to_parquet(actual_path, index=False)

    elif format.lower() == "pickle":
        actual_path = f"{base_path}.pkl"
        with open(actual_path, "wb") as f:
            pickle.dump(data, f)

    elif format.lower() == "sqlite":
        if not is_dataframe:
            raise ValueError("sqlite format requires pandas.DataFrame input")
        actual_path = f"{base_path}.db"

        # テーブル名の決定
        if table_name is None:
            table_name = os.path.basename(base_path)
            # ファイル名をテーブル名として使用可能な形式に変換
            table_name = table_name.replace("-", "_").replace(" ", "_")
            # 数字で始まる場合は先頭にアンダースコアを追加
            if table_name[0].isdigit():
                table_name = f"table_{table_name}"

        # SQLiteデータベースに保存
        conn = sqlite3.connect(actual_path)
        try:
            # データフレームをSQLiteテーブルに保存
            data.to_sql(table_name, conn, if_exists="replace", index=False)

            # 基本的なインデックスを作成（可能な場合）
            cursor = conn.cursor()

            # 'id', 'rowid', 'original_rowid'などの列があればインデックスを作成
            columns = data.columns.tolist()
            index_candidates = ["id", "rowid", "original_rowid", "merge_obj-cuz"]
            indexes_created = []

            for col in index_candidates:
                if col in columns:
                    try:
                        # カラム名に特殊文字が含まれる場合はクォートで囲む
                        safe_col_name = f'"{col}"' if "-" in col or " " in col else col
                        index_name = f"idx_{col.replace('-', '_').replace(' ', '_')}"
                        cursor.execute(
                            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({safe_col_name})"
                        )
                        indexes_created.append(index_name)
                    except Exception as e:
                        print(f"インデックス作成に失敗 ({col}): {e}")

            conn.commit()
            print(f"SQLiteデータベースに保存完了: {actual_path}")
            print(f"テーブル名: {table_name}")
            if indexes_created:
                print(f"作成されたインデックス: {', '.join(indexes_created)}")

        except Exception as e:
            print(f"SQLite保存時にエラーが発生: {e}")
            raise
        finally:
            conn.close()

    else:
        raise ValueError(
            f"Unsupported format: {format}. Supported formats: csv, parquet, npy, pt, pickle, sqlite"
        )

    # メタデータの作成
    if is_dataframe:
        metadata = {
            "data_type": "pandas.DataFrame",
            "source_info": source_info,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "processing_steps": processing_steps,
            "config": config,
            "rows": len(data),
            "columns": list(data.columns),
            "data_hash": data_hash,
            "format": format.lower(),
            "dtypes": data.dtypes.astype(str).to_dict(),  # データ型情報を追加
        }

        # SQLite固有の情報を追加
        if format.lower() == "sqlite":
            metadata.update(
                {
                    "table_name": table_name,
                    "indexes_created": (indexes_created if "indexes_created" in locals() else []),
                }
            )

    elif is_numpy:  # numpy array
        metadata = {
            "data_type": "numpy.ndarray",
            "source_info": source_info,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "processing_steps": processing_steps,
            "config": config,
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "size": int(data.size),
            "data_hash": data_hash,
            "format": format.lower(),
            "array_stats": (
                {
                    "min": float(data.min()),
                    "max": float(data.max()),
                    "mean": float(data.mean()),
                    "std": float(data.std()),
                }
                if data.dtype.kind in "biufc"
                else None
            ),
        }
    elif is_torch:  # torch tensor
        metadata = {
            "data_type": "torch.Tensor",
            "source_info": source_info,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "processing_steps": processing_steps,
            "config": config,
            "shape": list(data.shape),
            "dtype": str(data.dtype),
            "size": int(data.numel()),
            "data_hash": data_hash,
            "format": format.lower(),
            "array_stats": (
                {
                    "min": float(data.min()),
                    "max": float(data.max()),
                    "mean": float(data.float().mean()),
                    "std": float(data.float().std()),
                }
                if not data.dtype.is_complex
                else None
            ),
        }
    else:  # UMAP, sklearn models, or other ML objects
        metadata = {
            "data_type": type(data).__name__,
            "source_info": source_info,
            "created_at": datetime.now().isoformat(),
            "created_by": created_by,
            "processing_steps": processing_steps,
            "config": config,
            "data_hash": data_hash,
            "format": format.lower(),
            "object_module": type(data).__module__,
            "object_class": type(data).__qualname__,
        }

        # UMAPの場合は追加情報を保存
        if is_umap:
            try:
                metadata.update(
                    {
                        "n_components": getattr(data, "n_components", None),
                        "n_neighbors": getattr(data, "n_neighbors", None),
                        "min_dist": getattr(data, "min_dist", None),
                        "metric": getattr(data, "metric", None),
                        "is_fitted": hasattr(data, "embedding_"),
                        "embedding_shape": (
                            list(data.embedding_.shape) if hasattr(data, "embedding_") else None
                        ),
                    }
                )
            except Exception as e:
                metadata["umap_info_error"] = str(e)

        # scikit-learnモデルの場合は追加情報を保存
        if is_sklearn_model:
            try:
                # 共通の属性
                sklearn_info = {}

                # 特徴量名（学習済みモデルの場合）
                if hasattr(data, "feature_names_in_"):
                    sklearn_info["feature_names_in"] = list(data.feature_names_in_)

                # 学習済みかどうかの判定
                if hasattr(data, "_sklearn_fitted"):
                    sklearn_info["is_fitted"] = data._sklearn_fitted
                elif hasattr(data, "n_features_in_"):
                    sklearn_info["is_fitted"] = True
                    sklearn_info["n_features_in"] = int(data.n_features_in_)

                # モデル固有のパラメータ
                if hasattr(data, "get_params"):
                    try:
                        params = data.get_params()
                        # JSON serializable な値のみ保存
                        serializable_params = {}
                        for key, value in params.items():
                            if isinstance(value, (str, int, float, bool, type(None))):
                                serializable_params[key] = value
                            else:
                                serializable_params[key] = str(value)
                        sklearn_info["model_params"] = serializable_params
                    except Exception as e:
                        sklearn_info["params_error"] = str(e)

                # 回帰モデルの場合
                if hasattr(data, "feature_importances_"):
                    sklearn_info["has_feature_importances"] = True
                    sklearn_info["n_features"] = len(data.feature_importances_)

                # 分類モデルの場合
                if hasattr(data, "classes_"):
                    sklearn_info["classes"] = list(data.classes_)
                    sklearn_info["n_classes"] = len(data.classes_)

                # クラスタリングモデルの場合
                if hasattr(data, "cluster_centers_"):
                    sklearn_info["n_clusters"] = len(data.cluster_centers_)

                metadata.update(sklearn_info)

            except Exception as e:
                metadata["sklearn_info_error"] = str(e)

        # その他のMLオブジェクト（LabelEncoder、PCA等）の場合
        if is_ml_object and not is_sklearn_model:
            try:
                ml_info = {}

                # LabelEncoderの場合
                if hasattr(data, "classes_"):
                    ml_info["classes"] = list(data.classes_)

                # PCAの場合
                if hasattr(data, "explained_variance_ratio_"):
                    ml_info["explained_variance_ratio"] = list(data.explained_variance_ratio_)
                    ml_info["n_components"] = len(data.explained_variance_ratio_)

                # Scalerの場合
                if hasattr(data, "scale_"):
                    ml_info["n_features_scale"] = len(data.scale_)

                if hasattr(data, "mean_"):
                    ml_info["n_features_mean"] = len(data.mean_)

                metadata.update(ml_info)

            except Exception as e:
                metadata["ml_object_info_error"] = str(e)

    # メタデータの保存
    metadata_path = f"{base_path}_metadata.yaml"
    with open(metadata_path, "w", encoding="utf-8") as f:
        yaml.dump(_to_yamlable(metadata), f, default_flow_style=False, allow_unicode=True)

    print(f"データを保存しました: {actual_path}")
    print(f"メタデータを保存しました: {metadata_path}")
    print(f"作成者: {created_by}")

    return data


def load_data_with_metadata(file_path, table_name=None):
    """
    データファイル（DataFrame or NumPy配列 or MLモデル）とその関連メタデータを読み込む関数

    Parameters:
    -----------
    file_path : str
        読み込むデータファイルのパス
    table_name : str, optional
        SQLiteの場合のテーブル名（指定しない場合はメタデータから取得）

    Returns:
    --------
    tuple
        (data, metadata) - 読み込まれたデータとメタデータ辞書
    """
    file_path = os.fspath(file_path)
    base_path, ext = os.path.splitext(file_path)
    metadata_path = f"{base_path}_metadata.yaml"

    # メタデータの読み込み
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"警告: メタデータファイルが見つかりません: {metadata_path}")
        metadata = None

    # データの形式に基づいて読み込み
    if ext.lower() == ".npy":
        data = np.load(file_path)
    elif ext.lower() == ".pt":
        import torch

        data = torch.load(file_path)
    elif ext.lower() == ".csv":
        data = pd.read_csv(file_path)
    elif ext.lower() == ".parquet":
        data = pd.read_parquet(file_path)
    elif ext.lower() in [".pkl", ".pickle"]:
        with open(file_path, "rb") as f:
            data = pickle.load(f)
    elif ext.lower() == ".db":
        conn = sqlite3.connect(file_path)
        try:
            # テーブル名の決定
            if table_name is None:
                if metadata and "table_name" in metadata:
                    table_name = metadata["table_name"]
                else:
                    # メタデータがない場合はファイル名から推測
                    table_name = os.path.basename(base_path)
                    table_name = table_name.replace("-", "_").replace(" ", "_")
                    if table_name[0].isdigit():
                        table_name = f"table_{table_name}"

            # テーブルの存在確認
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                # 指定されたテーブルが存在しない場合、利用可能なテーブルを表示
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                available_tables = [row[0] for row in cursor.fetchall()]
                raise ValueError(
                    f"テーブル '{table_name}' が見つかりません。利用可能なテーブル: {available_tables}"
                )

            data = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        finally:
            conn.close()
    elif ext.lower() == ".json":
        data = pd.read_json(file_path, lines=True)
    else:
        raise ValueError(f"サポートされていないファイル形式です: {ext}")

    return data, metadata


def check_sqlite_database(db_path, table_name=None):
    """
    SQLiteデータベースの内容を確認する関数

    Parameters:
    -----------
    db_path : str
        データベースファイルのパス
    table_name : str, optional
        確認するテーブル名（指定しない場合は全テーブルを表示）
    """
    if not os.path.exists(db_path):
        print(f"データベースファイルが見つかりません: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # 利用可能なテーブル一覧を取得
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"データベース: {db_path}")
        print(f"利用可能なテーブル: {', '.join(tables)}")

        if table_name is None:
            if len(tables) == 1:
                table_name = tables[0]
                print(f"テーブル '{table_name}' を自動選択")
            else:
                print("複数のテーブルがあります。table_nameを指定してください。")
                return

        if table_name not in tables:
            print(f"指定されたテーブル '{table_name}' が見つかりません。")
            return

        # テーブル情報の確認
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        # カラム情報の確認
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        # インデックス情報の確認
        cursor.execute(f"PRAGMA index_list({table_name})")
        indexes = cursor.fetchall()

        # サンプルデータの確認
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample_data = cursor.fetchall()

        print(f"\nテーブル名: {table_name}")
        print(f"総行数: {row_count:,}")

        print("\nカラム情報:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        if indexes:
            print("\nインデックス:")
            for idx in indexes:
                print(f"  - {idx[1]}")

        print("\nサンプルデータ（最初の3行）:")
        column_names = [col[1] for col in columns]
        for i, row in enumerate(sample_data):
            print(f"  行{i + 1}:")
            for name, value in zip(column_names, row):
                if isinstance(value, str) and len(value) > 50:
                    print(f"    {name}: {value[:50]}...")
                else:
                    print(f"    {name}: {value}")
            print()

    except Exception as e:
        print(f"データベース確認時にエラー: {e}")
    finally:
        conn.close()


def get_caller_info():
    """
    関数を呼び出したファイルの情報を取得するヘルパー関数

    Returns:
    --------
    dict
        呼び出し元の情報（ファイル名、関数名、行番号など）
    """
    try:
        caller_frame = inspect.currentframe().f_back.f_back
        caller_filename = caller_frame.f_code.co_filename
        caller_function = caller_frame.f_code.co_name
        caller_lineno = caller_frame.f_lineno

        return {
            "filename": os.path.basename(caller_filename),
            "function": caller_function,
            "line_number": caller_lineno,
            "full_path": caller_filename,
        }
    except Exception as e:
        return {"error": str(e), "filename": "unknown"}


def _node_info(metadata):
    """メタデータから、系譜の1ノード分の情報を取り出す"""
    node_info = {
        "created_at": metadata.get("created_at"),
        "created_by": metadata.get("created_by"),
        "processing_steps": metadata.get("processing_steps"),
        "config": metadata.get("config"),
        "data_type": metadata.get("data_type", "unknown"),
        "format": metadata.get("format", "unknown"),
    }
    data_type = metadata.get("data_type") or ""

    if data_type == "pandas.DataFrame":
        node_info.update(
            {
                "rows": metadata.get("rows"),
                "columns": metadata.get("columns"),
                "dtypes": metadata.get("dtypes"),
            }
        )
        if metadata.get("format") == "sqlite":
            node_info.update(
                {
                    "table_name": metadata.get("table_name"),
                    "indexes_created": metadata.get("indexes_created"),
                }
            )
    elif data_type in ("numpy.ndarray", "torch.Tensor"):
        node_info.update(
            {
                "shape": metadata.get("shape"),
                "dtype": metadata.get("dtype"),
                "array_stats": metadata.get("array_stats"),
            }
        )
    elif "UMAP" in data_type:
        for key in (
            "n_components",
            "n_neighbors",
            "min_dist",
            "metric",
            "is_fitted",
            "embedding_shape",
        ):
            node_info[key] = metadata.get(key)
    else:
        # その他のMLオブジェクト（sklearn等）の情報
        for key in (
            "feature_names_in",
            "is_fitted",
            "n_features_in",
            "model_params",
            "has_feature_importances",
            "classes",
            "n_classes",
            "n_clusters",
        ):
            if key in metadata:
                node_info[key] = metadata[key]
    return node_info


def _source_paths(source_info):
    """source_info（文字列・リスト・辞書）から、実在するファイルのパスだけを取り出す"""
    if isinstance(source_info, str):
        candidates = [source_info]
    elif isinstance(source_info, dict):
        candidates = list(source_info.values())
    elif isinstance(source_info, list):
        candidates = source_info
    else:
        candidates = []
    return [c for c in candidates if isinstance(c, str) and os.path.exists(c)]


def trace_data_lineage(file_path, depth=None):
    """
    データの系譜（lineage）を再帰的に追跡する関数

    Parameters:
    -----------
    file_path : str
        追跡を開始するファイルのパス
    depth : int or None
        追跡する深さの上限（Noneの場合は制限なし）

    Returns:
    --------
    dict
        {パス: ノード情報} の辞書。元データは "children" の中に入れ子で入る。
        メタデータがないファイルは {"note": "メタデータなし"}。
    """
    file_path = os.fspath(file_path)

    def _trace(path, level, visited):
        base_path, _ = os.path.splitext(path)
        metadata_path = f"{base_path}_metadata.yaml"

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {"note": "メタデータなし"}

        node = _node_info(metadata)
        if depth is not None and level >= depth:
            return node

        children = {}
        for source in _source_paths(metadata.get("source_info")):
            if source in visited:  # 循環参照の防止
                continue
            children[source] = _trace(source, level + 1, visited | {source})
        if children:
            node["children"] = children
        return node

    return {file_path: _trace(file_path, 0, {file_path})}
