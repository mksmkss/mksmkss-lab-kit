"""
`*_metadata.yaml`（save_data_with_metadata が出力）の source_info をたどり、
データの依存関係を Mermaid のグラフとして出力する。

CLI: `lab-kit lineage`
"""

import glob
import os
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List

import yaml
from tqdm import tqdm

from lab_kit.paths import project_root

# 検索から除外するディレクトリ名
EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


def safe_yaml_loader():
    """
    安全なYAMLローダーを作成（Python tupleを適切に処理）
    """

    # Pythonのtuple型をリストとして読み込むためのカスタムローダー
    class SafeLoader(yaml.SafeLoader):
        pass

    def tuple_constructor(loader, node):
        return tuple(loader.construct_sequence(node))

    SafeLoader.add_constructor("tag:yaml.org,2002:python/tuple", tuple_constructor)
    return SafeLoader


def find_yaml_files(main_path):
    """
    ルート配下の全てのメタデータ YAML を検索する

    Parameters:
    -----------
    main_path : str
        検索対象のルートパス

    Returns:
    --------
    list
        YAMLファイルのパスリスト
    """
    yaml_patterns = [
        os.path.join(main_path, "**", "*_metadata.yaml"),
        os.path.join(main_path, "**", "*_metadata.yml"),
    ]

    yaml_files = []
    for pattern in yaml_patterns:
        yaml_files.extend(glob.glob(pattern, recursive=True))

    # 重複と、仮想環境などの除外ディレクトリ配下を取り除く
    yaml_files = [
        f
        for f in set(yaml_files)
        if not EXCLUDE_DIRS & set(os.path.relpath(f, main_path).split(os.sep))
    ]
    print(f"発見されたYAMLファイル数: {len(yaml_files)}")

    return yaml_files


def load_metadata_from_yaml(yaml_file):
    """
    YAMLファイルからメタデータを読み込む（安全な読み込み）

    Parameters:
    -----------
    yaml_file : str
        YAMLファイルのパス

    Returns:
    --------
    dict or None
        メタデータ辞書（読み込み失敗時はNone）
    """
    try:
        with open(yaml_file, "r", encoding="utf-8") as f:
            # カスタムローダーを使用してtuple型を適切に処理
            metadata = yaml.load(f, Loader=safe_yaml_loader())
        return metadata
    except Exception as e:
        print(f"警告: {yaml_file} の読み込みに失敗しました - {e}")
        return None


def normalize_source_info(source_info):
    """
    source_infoを正規化して文字列のリストに変換する

    Parameters:
    -----------
    source_info : various
        様々な形式のsource_info

    Returns:
    --------
    list
        ファイルパスの文字列リスト
    """
    sources = []

    if source_info is None:
        return sources

    # 文字列の場合
    if isinstance(source_info, str):
        # ファイルパスとして有効そうな文字列のみを追加
        if os.path.sep in source_info or source_info.endswith(
            (".csv", ".db", ".parquet", ".xlsx", ".json", ".npy", ".pkl")
        ):
            sources.append(source_info)

    # リストの場合
    elif isinstance(source_info, (list, tuple)):
        for item in source_info:
            if isinstance(item, str):
                # ファイルパスとして有効そうな文字列のみを追加
                if os.path.sep in item or item.endswith(
                    (".csv", ".db", ".parquet", ".xlsx", ".json", ".npy", ".pkl")
                ):
                    sources.append(item)
            # 数値や他の型は無視

    # 辞書の場合
    elif isinstance(source_info, dict):
        for key, value in source_info.items():
            # 再帰的に処理
            nested_sources = normalize_source_info(value)
            sources.extend(nested_sources)

    return sources


def extract_data_relationships(yaml_files):
    """
    全てのYAMLファイルからデータの依存関係を抽出する

    Parameters:
    -----------
    yaml_files : list
        YAMLファイルのパスリスト

    Returns:
    --------
    tuple
        (relationships, file_metadata) - 依存関係とメタデータ情報
    """
    relationships = {}
    file_metadata = {}

    print("YAMLファイルの解析中...")
    for yaml_file in tqdm(yaml_files):
        metadata = load_metadata_from_yaml(yaml_file)
        if metadata is None:
            continue

        # データファイルのパスを推定（YAMLファイル名から_metadata部分を除去）
        data_file_path = yaml_file.replace("_metadata.yaml", "").replace("_metadata.yml", "")

        # メタデータの保存
        file_metadata[data_file_path] = {
            "yaml_path": yaml_file,
            "metadata": metadata,
            "created_at": metadata.get("created_at"),
            "created_by": metadata.get("created_by"),
            "processing_steps": metadata.get("processing_steps", []),
            "source_info": metadata.get("source_info"),
            "format": metadata.get("format"),
            "rows": metadata.get("rows", metadata.get("rows_total")),
            "columns": metadata.get("columns"),
        }

        # source_infoから依存関係を抽出（正規化）
        source_info = metadata.get("source_info")
        sources = normalize_source_info(source_info)

        relationships[data_file_path] = sources

    return relationships, file_metadata


def normalize_filename(file_path):
    """
    ファイル名を正規化して類似ファイルを検出しやすくする

    Parameters:
    -----------
    file_path : str
        ファイルパス

    Returns:
    --------
    str
        正規化されたファイル名
    """
    basename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(basename)[0]

    # 正規化パターン
    normalized = name_without_ext.lower()

    # 数字やアンダースコアの除去（バージョン番号など）
    normalized = re.sub(r"_\d+$", "", normalized)  # 末尾の_1, _2など
    normalized = re.sub(r"\d+$", "", normalized)  # 末尾の数字

    return normalized


def calculate_filename_similarity(file1, file2):
    """
    2つのファイル名の類似度を計算する

    Parameters:
    -----------
    file1, file2 : str
        比較するファイルパス

    Returns:
    --------
    float
        類似度（0.0-1.0）
    """
    name1 = normalize_filename(file1)
    name2 = normalize_filename(file2)

    return SequenceMatcher(None, name1, name2).ratio()


def group_similar_files(all_files, similarity_threshold=0.8):
    """
    類似したファイル名をグループ化する

    Parameters:
    -----------
    all_files : set
        全ファイルのセット
    similarity_threshold : float
        類似度の閾値

    Returns:
    --------
    dict
        {group_name: [files]} の辞書
    """
    file_groups = {}
    processed = set()

    for file_path in all_files:
        if file_path in processed:
            continue

        # 現在のファイルと類似したファイルを探す
        group = [file_path]
        processed.add(file_path)

        for other_file in all_files:
            if other_file in processed:
                continue

            similarity = calculate_filename_similarity(file_path, other_file)
            if similarity >= similarity_threshold:
                group.append(other_file)
                processed.add(other_file)

        # グループ名を決定（最も一般的な名前を使用）
        group_name = normalize_filename(file_path)
        file_groups[group_name] = group

    return file_groups


def find_enhanced_linear_chains(
    relationships: Dict[str, List[str]], file_metadata: Dict
) -> List[List[str]]:
    """
    拡張された線形チェーン検出（類似ファイル名と時系列を考慮）

    Parameters:
    -----------
    relationships : dict
        ファイル間の依存関係
    file_metadata : dict
        ファイルメタデータ

    Returns:
    --------
    list
        線形チェーンのリスト
    """
    # 全ファイルを収集
    all_files = set(relationships.keys())
    for sources in relationships.values():
        all_files.update(sources)

    # 類似ファイルのグループ化
    file_groups = group_similar_files(all_files, similarity_threshold=0.7)

    print(f"検出されたファイルグループ数: {len(file_groups)}")
    for group_name, files in file_groups.items():
        if len(files) > 1:
            print(f"グループ '{group_name}': {[os.path.basename(f) for f in files]}")

    # 各ファイルの入次数と出次数を計算
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)

    for target_file, sources in relationships.items():
        for source_file in sources:
            if source_file in all_files:
                out_degree[source_file] += 1
                in_degree[target_file] += 1

    # グループ内での時系列順序を考慮したチェーン構築
    chains = []
    visited = set()

    # まず、グループごとに処理
    for group_name, group_files in file_groups.items():
        if len(group_files) <= 1:
            continue

        # グループ内のファイルを作成日時でソート
        group_files_with_time = []
        for file_path in group_files:
            if file_path in file_metadata:
                created_at = file_metadata[file_path]["metadata"].get("created_at")
                group_files_with_time.append((file_path, created_at))
            else:
                group_files_with_time.append((file_path, None))

        # 作成日時でソート（Noneは最後に）
        group_files_with_time.sort(key=lambda x: x[1] if x[1] else "9999-12-31")
        sorted_group_files = [f[0] for f in group_files_with_time]

        # グループ内での依存関係チェック
        group_chain = []
        for i, current_file in enumerate(sorted_group_files):
            if current_file in visited:
                continue

            # 前のファイルとの依存関係をチェック
            is_connected = False
            if i > 0:
                prev_file = sorted_group_files[i - 1]
                # 直接的な依存関係または間接的な関係
                if prev_file in relationships.get(current_file, []) or any(
                    calculate_filename_similarity(prev_file, src) > 0.8
                    for src in relationships.get(current_file, [])
                ):
                    is_connected = True

            if i == 0 or is_connected:
                group_chain.append(current_file)
                visited.add(current_file)

        if len(group_chain) >= 2:
            chains.append(group_chain)
            print(
                f"グループチェーン '{group_name}': {' → '.join([os.path.basename(f) for f in group_chain])}"
            )

    # 個別の線形チェーンも検出（従来のロジック）
    for file_path in all_files:
        if file_path in visited:
            continue

        # チェーンの開始点を探す
        if in_degree[file_path] <= 1:
            chain = []
            current = file_path

            # チェーンを前方向に辿る
            while current and current not in visited:
                chain.append(current)
                visited.add(current)

                # 次のファイルを探す
                next_files = []
                for target, sources in relationships.items():
                    if current in sources and target not in visited:
                        next_files.append(target)

                # 線形チェーンの条件
                if len(next_files) == 1 and in_degree[next_files[0]] == 1:
                    current = next_files[0]
                else:
                    current = None

            # チェーンが2つ以上のファイルを含む場合のみ追加
            if len(chain) >= 2:
                chains.append(chain)
            elif len(chain) == 1:
                chains.append(chain)

    return chains


def create_node_id(file_path):
    """
    ファイルパスから安全なノードIDを生成する

    Parameters:
    -----------
    file_path : str
        ファイルパス

    Returns:
    --------
    str
        安全なノードID
    """
    basename = os.path.basename(file_path)
    # 拡張子を除去
    name_without_ext = os.path.splitext(basename)[0]
    # 英数字とアンダースコアのみに変換
    safe_id = re.sub(r"[^\w]", "_", name_without_ext)
    return f"node_{safe_id}"


def generate_mermaid_graph_enhanced(relationships, file_metadata):
    """
    拡張された線形チェーンを縦に配置するMermaidグラフ形式の文字列を生成する

    Parameters:
    -----------
    relationships : dict
        ファイル間の依存関係
    file_metadata : dict
        ファイルのメタデータ情報

    Returns:
    --------
    str
        Mermaidグラフの文字列
    """
    mermaid_lines = ["```mermaid", "graph TD"]

    # 拡張された線形チェーンを検出
    chains = find_enhanced_linear_chains(relationships, file_metadata)

    print(f"\n検出された全チェーン数: {len(chains)}")
    for i, chain in enumerate(chains):
        if len(chain) > 1:
            print(
                f"チェーン {i + 1} ({len(chain)}ファイル): {' → '.join([os.path.basename(f) for f in chain])}"
            )

    # 全ての関連ファイルを収集
    all_files = set(relationships.keys())
    for sources in relationships.values():
        all_files.update(sources)

    # ノードIDの作成（重複を避けるために番号を付与）
    node_mapping = {}
    used_ids = set()
    for file_path in all_files:
        base_id = create_node_id(file_path)
        node_id = base_id
        counter = 1
        while node_id in used_ids:
            node_id = f"{base_id}_{counter}"
            counter += 1
        used_ids.add(node_id)
        node_mapping[file_path] = node_id

    # ノードの定義
    def create_node_label(file_path):
        basename = os.path.basename(file_path)

        # メタデータがある場合はそれを使用、ない場合は推定
        if file_path in file_metadata:
            metadata = file_metadata[file_path]["metadata"]
            format_type = metadata.get("format", "unknown")
            rows = metadata.get("rows", metadata.get("rows_total", 0))
        else:
            # 拡張子から形式を推定
            ext = os.path.splitext(file_path)[1].lower()
            format_map = {
                ".csv": "csv",
                ".db": "sqlite",
                ".parquet": "parquet",
                ".json": "json",
                ".xlsx": "excel",
                ".xls": "excel",
                ".npy": "numpy",
                ".pkl": "pickle",
            }
            format_type = format_map.get(ext, "unknown")
            rows = 0

        return basename, format_type, rows

    # ノード定義の生成
    for file_path in all_files:
        node_id = node_mapping[file_path]
        basename, format_type, rows = create_node_label(file_path)

        # ノードの形状と情報を決定
        if format_type == "csv":
            if rows and rows > 0:
                shape = f'{node_id}["{basename}<br/>CSV<br/>{rows:,}行"]'
            else:
                shape = f'{node_id}["{basename}<br/>CSV"]'
        elif format_type == "sqlite":
            if rows and rows > 0:
                shape = f'{node_id}[("{basename}<br/>SQLite<br/>{rows:,}行")]'
            else:
                shape = f'{node_id}[("{basename}<br/>SQLite")]'
        elif format_type == "parquet":
            if rows and rows > 0:
                shape = f'{node_id}["{basename}<br/>Parquet<br/>{rows:,}行"]'
            else:
                shape = f'{node_id}["{basename}<br/>Parquet"]'
        elif format_type == "json":
            if rows and rows > 0:
                shape = f'{node_id}["{basename}<br/>JSON<br/>{rows:,}行"]'
            else:
                shape = f'{node_id}["{basename}<br/>JSON"]'
        elif format_type == "excel":
            shape = f'{node_id}["{basename}<br/>Excel"]'
        elif format_type == "numpy":
            shape = f'{node_id}["{basename}<br/>NumPy"]'
        elif format_type == "pickle":
            shape = f'{node_id}["{basename}<br/>Pickle"]'
        else:
            shape = f'{node_id}["{basename}"]'

        mermaid_lines.append(f"    {shape}")

    # 線形チェーンのエッジを定義（縦方向の配置を強制）
    processed_edges = set()

    # まず線形チェーンのエッジを処理
    for chain in chains:
        if len(chain) > 1:
            for i in range(len(chain) - 1):
                source_file = chain[i]
                target_file = chain[i + 1]

                if source_file in node_mapping and target_file in node_mapping:
                    source_id = node_mapping[source_file]
                    target_id = node_mapping[target_file]
                    mermaid_lines.append(f"    {source_id} --> {target_id}")
                    processed_edges.add((source_file, target_file))

    # 残りのエッジを処理（線形チェーンでカバーされていないもの）
    for target_file, sources in relationships.items():
        if not sources:
            continue

        target_id = node_mapping.get(target_file)
        if not target_id:
            continue

        for source_file in sources:
            # 自己ループを除外し、有効なファイルパスのみ処理
            if (
                source_file != target_file
                and source_file in node_mapping
                and isinstance(source_file, str)
                and (source_file, target_file) not in processed_edges
            ):
                source_id = node_mapping[source_file]
                mermaid_lines.append(f"    {source_id} --> {target_id}")

    # サブグラフで線形チェーンをグループ化（縦配置を強化）
    mermaid_lines.append("")
    mermaid_lines.append("    %% 処理フローチェーンのサブグラフ定義")

    significant_chains = [chain for chain in chains if len(chain) >= 2]
    for i, chain in enumerate(significant_chains):
        chain_name = f"flow_{i + 1}"

        # チェーンの代表的な名前を決定
        representative_name = normalize_filename(chain[0])
        if len(chain) > 2:
            display_name = f"処理フロー: {representative_name} ({len(chain)}段階)"
        else:
            display_name = f"処理ペア: {representative_name}"

        mermaid_lines.append(f'    subgraph {chain_name} ["{display_name}"]')
        mermaid_lines.append("        direction TB")

        for file_path in chain:
            if file_path in node_mapping:
                node_id = node_mapping[file_path]
                mermaid_lines.append(f"        {node_id}")

        mermaid_lines.append("    end")

    # スタイル定義（フォントカラーを黒に固定）
    mermaid_lines.extend(
        [
            "",
            "    %% スタイル定義（フォントカラー黒固定）",
            "    classDef csv fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#000000",
            "    classDef sqlite fill:#f3e5f5,stroke:#4a148c,stroke-width:2px,color:#000000",
            "    classDef parquet fill:#e8f5e8,stroke:#2e7d32,stroke-width:2px,color:#000000",
            "    classDef json fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#000000",
            "    classDef excel fill:#fff8e1,stroke:#f57c00,stroke-width:2px,color:#000000",
            "    classDef numpy fill:#f1f8e9,stroke:#33691e,stroke-width:2px,color:#000000",
            "    classDef pickle fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px,color:#000000",
            "    classDef unknown fill:#fafafa,stroke:#616161,stroke-width:2px,color:#000000",
        ]
    )

    # ノードにクラスを適用
    for file_path in all_files:
        node_id = node_mapping[file_path]
        _, format_type, _ = create_node_label(file_path)
        mermaid_lines.append(f"    class {node_id} {format_type}")

    mermaid_lines.append("```")

    return "\n".join(mermaid_lines)


def print_relationships_summary(relationships, file_metadata):
    """
    依存関係の概要を表示する

    Parameters:
    -----------
    relationships : dict
        ファイル間の依存関係
    file_metadata : dict
        ファイルのメタデータ情報
    """
    print("=== データファイル依存関係概要 ===")

    # 全ファイル数
    all_files = set(relationships.keys())
    for sources in relationships.values():
        all_files.update(sources)

    print(f"総ファイル数: {len(all_files)}")
    print(f"メタデータ付きファイル数: {len(file_metadata)}")

    # ルートファイル（他から参照されていないファイル）
    referenced_files = set()
    for sources in relationships.values():
        referenced_files.update(sources)

    root_files = all_files - referenced_files
    print(f"ルートファイル数: {len(root_files)}")

    # 類似ファイルのグループ化
    file_groups = group_similar_files(all_files, similarity_threshold=0.7)
    multi_file_groups = {k: v for k, v in file_groups.items() if len(v) > 1}

    print(f"類似ファイルグループ数: {len(multi_file_groups)}")

    if multi_file_groups:
        print("\n=== 類似ファイルグループ ===")
        for group_name, files in multi_file_groups.items():
            print(f"グループ '{group_name}' ({len(files)}ファイル):")
            for file_path in files:
                basename = os.path.basename(file_path)
                if file_path in file_metadata:
                    created_at = file_metadata[file_path]["metadata"].get("created_at", "不明")
                    print(f"  - {basename} ({created_at})")
                else:
                    print(f"  - {basename} (メタデータなし)")

    # 拡張された線形チェーンの検出と表示
    chains = find_enhanced_linear_chains(relationships, file_metadata)
    linear_chains = [chain for chain in chains if len(chain) > 1]

    print(f"\n線形処理チェーン数: {len(linear_chains)}")

    if linear_chains:
        print("\n=== 検出された処理フロー ===")
        for i, chain in enumerate(linear_chains):
            chain_files = [os.path.basename(f) for f in chain]
            print(f"フロー {i + 1} ({len(chain)}段階): {' → '.join(chain_files)}")


def main(root=None, out_dir=None, verbose=True):
    """
    メイン処理

    Parameters:
    -----------
    root : str or Path, optional
        メタデータを探すルート（省略時はプロジェクトルート）
    out_dir : str or Path, optional
        Mermaid の出力先（省略時は <root>/docs/data_lineage）
    verbose : bool
        Mermaid のコードを標準出力にも表示するか

    Returns:
    --------
    str or None
        保存した Markdown のパス（依存関係が見つからなければ None）
    """
    root = str(root) if root is not None else str(project_root())
    print("=== データ系譜の可視化 ===")
    print(f"分析開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"ルート: {root}")
    print()

    # YAMLファイルの検索
    yaml_files = find_yaml_files(root)

    if not yaml_files:
        print("YAMLファイルが見つかりませんでした。")
        return None

    # 依存関係の抽出
    relationships, file_metadata = extract_data_relationships(yaml_files)

    if not relationships:
        print("依存関係情報が見つかりませんでした。")
        return None

    # 関係の概要表示
    print_relationships_summary(relationships, file_metadata)

    # 出力ディレクトリの作成
    results_dir = (
        str(out_dir) if out_dir is not None else os.path.join(root, "docs", "data_lineage")
    )
    os.makedirs(results_dir, exist_ok=True)

    # Mermaidグラフの生成と保存
    print("\n=== Mermaidグラフ生成中 ===")
    mermaid_graph = generate_mermaid_graph_enhanced(relationships, file_metadata)
    date = datetime.now().strftime("%Y%m%d")
    mermaid_path = os.path.join(results_dir, f"data_lineage_{date}.md")

    with open(mermaid_path, "w", encoding="utf-8") as f:
        f.write(mermaid_graph)

    print(f"Mermaidグラフを保存しました: {mermaid_path}")

    if verbose:
        print("\n=== Mermaidグラフ（コピー&ペースト用） ===")
        print(mermaid_graph)

    print("\n使用方法:")
    print("1. 保存された .md を GitHub や Mermaid 対応のエディタで開く")
    print("2. または https://mermaid.live/ にコードを貼り付けて確認する")
    return mermaid_path


if __name__ == "__main__":
    main()
