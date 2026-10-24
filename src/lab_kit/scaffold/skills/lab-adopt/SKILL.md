---
name: lab-adopt
description: Use right after `lab-kit init`, or when the user says "lab-kit に移行したい", "既存コードを lab-kit に合わせて", "ipynb を marimo にして". Surveys an existing research codebase, then proposes how to move it to lab-kit conventions — first Jupyter → marimo, then save_data_with_metadata, project paths, folder layout. Proposes first and rewrites only what the user approves, one file at a time.
---

# 既存コードを lab-kit 流にそろえる

**書き換える前に、必ず提案を見せる。** 承認された分だけ、1ファイルずつ直す。データ本体は動かさない。専門用語は避け、「直すと何が良くなるか」を1行で添える。

## 始める前に
- `uv run lab-kit doctor` が通っているか確認する。
- `git status` がきれいか確認する。未コミットの変更があれば、先にコミットしてもらう(直した箇所を戻せるように)。

## 手順

### 1. Jupyter を marimo に変換する(最初にやる)
以降の手順は、変換後の `.py` に対して行う。

1. 対象を一覧にする: `uv run lab-kit to-marimo --dry-run`
2. 承認されたら変換する: `uv run lab-kit to-marimo`
   - 元の `.ipynb` は残る。同名の `.py` があれば飛ばす。
   - `.ipynb` に保存されていた出力(表や図)は、変換後の `.py` には残らない。残したいものは、先に別の場所へ保存してもらう。
3. `marimo check` で指摘が出たものは、`marimo-notebook` Skill(marimo 公式)に従って直す。よくある指摘は、複数のセルで同じ変数名を定義していること。
   - 変換が難しいノートブックは、`jupyter-to-marimo` Skill(marimo 公式)を使う。
   - 公式 Skill が無ければ、入れてよいかユーザーに確認する:
     `npx skills add marimo-team/skills --agent claude-code --skill jupyter-to-marimo --skill marimo-notebook`
4. 変換後のノートブックを実行して、元と同じ結果になるか確認する。実行していなければ「未実行」と報告する。
5. 元の `.ipynb` を消すかどうかは、ユーザーに決めてもらう(git の履歴には残る)。

### 2. 調べる(まだ何も変えない)
次を探して、ファイル名と行番号つきで一覧にする。

| 探すもの | 例 | 直すと良くなること |
|---|---|---|
| データの保存 | `to_csv` `to_parquet` `to_pickle` `np.save` `torch.save` `pickle.dump` | 作成者・元データ・処理内容が `*_metadata.yaml` に残り、後から辿れる |
| 固定パス | `"/Users/..."` `"C:\\..."` | 別の PC・別の人の環境でも動く |
| `sys.path` の操作 | `sys.path.append(...)` | 普通の `import` で書ける |
| 日本語フォント | 図ごとに `font=dict(family=...)` | 文字化けしない設定を1か所にまとめられる |
| デバイス判定 | `torch.device("cuda" if ...)` | MPS / CUDA / CPU を自動で選べる |
| フォルダ構成 | `temp/`、同名ファイルの二重配置、`data/` と `results/` の両方に図 | 置き場所が決まる |

### 3. 提案する(表で見せる)
```markdown
| # | ファイル:行 | いま | 直したあと | 動作が変わる点 |
|---|---|---|---|---|
| 1 | src/prep.py:42 | df.to_csv("data/a.csv") | save_data_with_metadata(df, data_path("interim", "a.csv"), created_by="prep.py", ...) | a_metadata.yaml が横にできる |
```
- **動作が変わる点**を必ず書く(出力ファイルが増える、パスの基準が変わる、など)。
- フォルダの移動は、移動前と移動後の対応表で見せる。移動すると壊れる参照(他のスクリプトからのパス)も書く。

### 4. 承認された分だけ直す
- ユーザーが「#1 と #3 だけ」のように選んだ分だけ直す。
- 1ファイル直すごとに `python -m py_compile <file>` で構文を確認する。
- 実行できるスクリプトは、直した後で動かして確認する。動かしていなければ「未実行」と報告する。
- コミットは許可を得てから、直したファイルを個別に指定して行う。

### 5. 後始末
- 既存のデータには `*_metadata.yaml` がなく、系譜(`lab-kit lineage`)が途中で切れる。**主要なデータだけ**、`source_info` と `created_by` を後付けする手順を案内する。分かる範囲だけ書き、不明な点は「不明」と書く。
- 直したあとの構成と、残った課題をまとめて報告する。

## 書き換えの型

```python
from lab_kit import data_path, project_root, results_path, save_data_with_metadata, get_device
from lab_kit.viz import apply_jp_font, save_figure

save_data_with_metadata(
    df,
    data_path("interim", "cleaned.csv"),         # 文字列でも Path でもよい
    created_by="prep.py",                         # 必須。作ったスクリプト名
    source_info=data_path("raw", "input.csv"),    # 元データ(複数ならリスト)
    processing_steps=["欠損値の除去", "正規化"],
    config={"drop_na": True},
    format="csv",                                 # csv / parquet / npy / pt / pickle / sqlite
)
```

## 守ること
- 勝手に書き換えない。提案 → 承認 → 適用の順を崩さない。
- データ本体(`*.db` `*.csv` `*.pt` など)は動かさない・消さない。
- `.env` や認証情報、個人情報を提案に書かない。
- 「動作が変わる点」を隠さない。分からないことは「未確認」と書く。
- 方針に関わる決定(フォルダ構成を変える、など)は、`decision-log` Skill で issue に残すよう勧める。
