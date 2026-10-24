---
name: lab-adopt
description: Use right after `lab-kit init` (or when the user says "lab-kit に移行したい", "既存コードを lab-kit に合わせて", "保存処理をメタ情報付きに") to survey an existing research codebase and propose how to move it to lab-kit conventions — save_data_with_metadata, project paths, folder layout. Proposes first, rewrites only what the user approves, one file at a time.
---

# 既存コードを lab-kit 流に移行する

**書き換える前に必ず提案を見せる。承認された分だけ、1ファイルずつ直す。** データ本体は動かさない。専門用語はなるべく避け、「これを直すと何が良くなるか」を1行で添える。

## 前提を確認する
- `uv run lab-kit doctor` が通っているか(通らなければ、まずそれを直す)。
- `git status` がきれいか。未コミットの変更があれば、先にコミットするよう勧める(直した箇所を戻せるように)。

## 手順

### 1. 調査(まだ何も変えない)
次を探して、ファイル名と行番号つきで一覧にする。

| 探すもの | 例 | 直すと良くなること |
|---|---|---|
| データの保存 | `to_csv` `to_parquet` `to_pickle` `np.save` `torch.save` `pickle.dump` | 作成者・元データ・処理内容が `*_metadata.yaml` に残り、後から辿れる |
| 固定パス | `"/Users/..."` `"C:\\..."` `os.getenv("MAIN_PATH")` の自前処理 | 別の PC・別の人の環境でも動く |
| `sys.path` の操作 | `sys.path.append(...)` | 普通の `import` で書ける |
| 日本語フォント | `font=dict(family=...)` が図ごとにバラバラ | 文字化けしない設定を1か所にまとめられる |
| デバイス判定 | `torch.device("cuda" if ...)` | MPS / CUDA / CPU を自動で選べる |
| フォルダ構成 | `temp/` `tmp/`、同名ファイルの二重配置、`data/` と `results/` の両方に図 | 置き場所が決まっていて迷わない |

### 2. 提案(表で見せる)
```markdown
| # | ファイル:行 | いま | 直したあと | 動作が変わる点 |
|---|---|---|---|---|
| 1 | src/prep.py:42 | df.to_csv("data/a.csv") | save_data_with_metadata(df, data_path("interim", "a.csv"), created_by="prep.py", source_info=..., processing_steps=[...]) | a_metadata.yaml が横にできる |
```
- 置き換えの書き方は下の「書き換えの型」に従う。
- **動作が変わる点**を必ず書く(出力ファイルが増える、パスの基準が変わる、など)。
- フォルダの移動は、移動前・移動後の対応表で見せる。移動すると壊れるパス(他のスクリプトからの参照)も書く。

### 3. 承認と適用
- ユーザーが「#1 と #3 だけ」のように選んだ分だけ直す。
- 1ファイル直すごとに `python -m py_compile <file>` で構文を確認する。
- 実行できるスクリプトなら、直した後で動かして確認する。実行していなければ、「未実行」と報告する。
- コミットはユーザーの許可を得てから、直したファイルを個別に指定して行う。

### 4. 後始末
- 既に作ってあるデータには `*_metadata.yaml` がなく、系譜(`lab-kit lineage`)が途中で途切れる。**主要なデータだけ**、`source_info`(何から作ったか)と `created_by`(どのスクリプトか)を後付けする手順を案内する。後付けする場合は、事実の分かる範囲だけを書き、不明なところは「不明」と書く。
- 直したあとのフォルダ構成と、残った課題をまとめて報告する。

## 書き換えの型

保存:
```python
from lab_kit import data_path, save_data_with_metadata

save_data_with_metadata(
    df,
    data_path("interim", "cleaned.csv"),        # Path でも文字列でもよい
    created_by="prep.py",                        # 必須。作ったスクリプト名
    source_info=data_path("raw", "input.csv"),   # 元データ(複数ならリスト)
    processing_steps=["欠損値の除去", "正規化"],
    config={"drop_na": True},
    format="csv",                                # csv / parquet / npy / pt / pickle / sqlite
)
```
パス:
```python
from lab_kit import project_root, data_path, results_path
```
フォント・図の保存:
```python
from lab_kit.viz import apply_jp_font, save_figure
```
デバイス:
```python
from lab_kit import get_device
device = get_device()
```

## 守ること
- 勝手に書き換えない。提案 → 承認 → 適用の順を崩さない。
- データ本体(`*.db` `*.csv` `*.pt` など)は動かさない・消さない。
- `.env`、認証情報、個人情報を読み上げたり、提案に書いたりしない。
- 「動作が変わる点」を隠さない。分からないときは「未確認」と書く。
- 直した理由と、その決定が研究の方針に関わる場合は、`decision-log` Skill で issue に残すことを勧める。
