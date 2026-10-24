# mksmkss-lab-kit

研究用の共通道具と Claude Code の Skill を、**既存のリポジトリに壊さずに入れる**ためのキット。

- 研究の決定の経緯を GitHub の issue に残す(Skill `decision-log`)
- データを保存するとき、元データ・作成者・処理内容を `*_metadata.yaml` に残す(`save_data_with_metadata`)
- データの系譜図(Mermaid)、日本語が化けない plotly、MPS / CUDA / CPU の自動選択
- 既存コードをこのやり方に寄せる手伝い(Skill `lab-adopt`)

## 入っているもの

| 種類 | 名前 | 中身 |
|---|---|---|
| Skill | `decision-log` | 1テーマ = 1 issue。本文に現状、コメントに決定の記録(D1, D2…)。段階ラベルと、相談(`meeting`)の記録 |
| Skill | `explain-results` | 結果の説明の型(何をしたくて → 計算 → 値 → 意味) |
| Skill | `result-graphs` | 結果を plotly の図にして残す手順 |
| Skill | `lab-adopt` | 既存コードを調べ、移行案を出し、承認された分だけ書き換える |
| Python | `lab_kit` | `save_data_with_metadata` / `load_data_with_metadata` / `trace_data_lineage`、`project_root` / `data_path` / `results_path`、`get_device`、`lab_kit.viz`(日本語フォント・PNG 保存) |
| コマンド | `lab-kit` | `init` / `update` / `labels` / `doctor` / `lineage` |
| 配布物 | `CLAUDE.md` ブロック、`.gitignore` ブロック、`.env.example`、marimo テンプレート、`data/` `results/` の雛形 | `init` が入れる |

## 前提

- Python 3.10 以上と [uv](https://docs.astral.sh/uv/)
- git
- [Claude Code](https://claude.com/claude-code)
- (`decision-log` を使うなら)[GitHub CLI(`gh`)](https://cli.github.com/) にログイン済みであること
  ```bash
  gh auth login      # 初回のみ
  gh auth status     # ログイン済みか確認
  ```

> このリポジトリが**非公開**の間は、招待された人だけが取得できる。招待されたら、`gh auth setup-git` を一度実行しておくと、`uv` が `git` 経由で取得できる。

## 導入

自分のプロジェクトのルートで実行する。新しいリポジトリでも、既存のリポジトリでも手順は同じ。

```bash
# 1) パッケージを入れる(プロジェクトが uv で管理されていない場合は、先に `uv init --bare`)
uv add git+https://github.com/mksmkss/mksmkss-lab-kit

# 2) 何が入るか、先に確認する(何も変更しない)
uv run lab-kit init --dry-run

# 3) 入れる
uv run lab-kit init

# 4) 環境を確認する
uv run lab-kit doctor

# 5) GitHub に decision-log 用のラベルを作る(gh のログインが必要。無いものだけ作る)
uv run lab-kit labels                 # 段階ラベル + meeting
uv run lab-kit labels --kinds default # 種類ラベル(experiment, method, data, analysis)も作る
```

プロジェクトに `uv add` したくない場合は、`init` だけ実行することもできる(Python の機能 `lab_kit` は使えない)。

```bash
uvx --from git+https://github.com/mksmkss/mksmkss-lab-kit lab-kit init
```

### 既存のリポジトリに入れるとき、何が起きるか(AsIs / ToBe)

| 対象 | 既に無いとき | 既にあるとき |
|---|---|---|
| `.claude/skills/<Skill名>/` | 作る | **上書きしない。** 内容が違えば横に `SKILL.md.lab-kit.new` を置き、差分を表示する |
| `.env.example`、`notebooks/_template.py` | 作る | 同上(`*.lab-kit.new`) |
| `CLAUDE.md` | 管理ブロックだけで作る | **自分の記述は残し**、末尾に管理ブロック(`<!-- lab-kit:begin -->` 〜 `<!-- lab-kit:end -->`)を追記する |
| `.gitignore` | 管理ブロックだけで作る | **自分の記述は残し**、末尾に管理ブロック(`# lab-kit:begin` 〜 `# lab-kit:end`)を追記する |
| `data/{raw,interim,processed}/`、`results/` | `.gitkeep` を置く | 中身には触らない |
| `src/` などのコード、データ、`pyproject.toml` | — | **触らない**(`uv add` が `pyproject.toml` に依存を1行足すだけ) |
| `.lab-kit/manifest.json` | 作る(配ったファイルの記録) | `update` が「手元で編集されたか」を判定するのに使う |

- `init` は何度実行しても同じ結果になる(2回目は何も変わらない)。
- `--dry-run` は、何も変更せず、予定だけを表示する。
- `--agents` を付けると、Claude Code 以外のエージェント向けに `.agents/skills/` へのリンクも作る。

### 導入前後の変化

| 項目 | AsIs(導入前) | ToBe(導入後) |
|---|---|---|
| 決定の記録 | 頭の中、チャット、メモに散らばる | テーマごとの issue に、背景・根拠つきで時系列に残る |
| 「なぜそうしたか」を辿る | 思い出すか、コードやログから推測する | issue のコメントを上から読めば分かる |
| 現状の把握 | 過去の会話を読み返す | issue の本文(最新のまとめ)を読む |
| 先生との相談 | 口頭、または自分のメモだけ | 相談ごとの issue に、指摘・決定・TODO が残る |
| 方針の変更点(AsIs / ToBe) | 資料や会話に散在 | issue 本文の「変更内容」の表にまとまる |
| 作業の進み具合 | 自分しか分からない | ラベル(`idea` → `decided` → `doing` → `done`)で一目で分かる |
| データの来歴 | 「このファイルはどこから?」が分からなくなる | `*_metadata.yaml` に元データ・作成者・処理が残り、系譜図にできる |
| パス | `/Users/...` の直書き、`sys.path.append` | `project_root()` / `data_path()`。別の PC でも動く |
| 図の日本語 | 図ごとにフォント指定がバラバラ、□ に化ける | `lab_kit.viz` に1か所 |
| データの置き場 | 図やデータが `data/` と `results/` に二重に置かれる | データは `data/`、図・表は `results/<実験名>/` |

### 更新

```bash
uv lock --upgrade-package lab-kit && uv sync   # パッケージを最新にする
uv run lab-kit update --dry-run                # 何が変わるか確認
uv run lab-kit update                          # 手元で編集していないファイルと、管理ブロックだけ最新にする
```

手元で編集した Skill は上書きされず、`*.lab-kit.new` が横に置かれる。差分を見て、必要な部分だけ取り込む。

## 使い方

### Skill(Claude Code に日本語で頼む)

コマンドは覚えなくてよい。

| やりたいこと | 頼み方の例 |
|---|---|
| 考え中のことを残す | 「この実験の論点を整理して、issue に残して」 |
| 決まったことを残す | 「いま決めた α の設定を、理由つきで記録して」 |
| 実装に入る | 「方針が固まったので、AsIs / ToBe をまとめて、実装段階にして」 |
| 作業を始める・終える | 「この issue を作業中にして」「完了にして閉じて」 |
| 先生との相談を準備する | 「明日の相談の issue を作って。論点は…」 |
| 相談の結果を残す | 「相談の結果を記録して。先生の指摘は…、決まったのは…」 |
| 結果を説明してもらう | 「この値は何?」(`explain-results` が型に沿って答える) |
| 結果を図にして残す | 「この結果をグラフにして残して」 |
| 既存コードを移行する | 「lab-adopt で、このリポジトリを lab-kit 流に移行して」 |

Claude は、**投稿する前に下書きを見せる**。内容を確認して「OK」と答えると、はじめて GitHub に投稿される。ただし「残して」「記録して」と頼んだ決定の記録は、そのまま投稿し、あとで内容を報告する。

流れ:

```text
考え中 ──▶ 決まった ──▶ 作業中 ──▶ 完了
 idea       decided      doing      done
  │           │            │         │
  │ 論点を     │ 変更内容    │ コミット  │ 結果を書いて
  │ 整理する   │ (AsIs/ToBe) │ から      │ close する
  │           │ を本文に足す │ #N で参照  │
  └─ 決定が出るたびに、コメントに D1, D2… を追記し、本文を最新にする
```

### Python

```python
import pandas as pd
from lab_kit import data_path, results_path, save_data_with_metadata, get_device
from lab_kit.viz import save_figure

raw = data_path("raw", "input.csv")          # <プロジェクトルート>/data/raw/input.csv
df = pd.read_csv(raw)

save_data_with_metadata(
    df,
    data_path("interim", "cleaned.csv"),     # 文字列でも Path でもよい
    created_by="prep.py",                    # 必須。作ったスクリプト名
    source_info=raw,                         # 元データ(複数ならリスト)
    processing_steps=["欠損値の除去"],
    config={"drop_na": True},
    format="csv",                            # csv / parquet / npy / pt / pickle / sqlite
)
# → data/interim/cleaned.csv と、data/interim/cleaned_metadata.yaml ができる

png = save_figure(fig, results_path("exp1", "figures", "alpha_sweep"))  # 日本語対応で PNG 保存
device = get_device()                        # "mps" > "cuda" > "cpu"
```

- プロジェクトルートは、環境変数 `MAIN_PATH`、`.env` の `MAIN_PATH`、`.git` か `pyproject.toml` のあるフォルダの順で決まる(普通は何も設定しなくてよい)。
- PNG の保存には、`kaleido` と Google Chrome が必要(`uv add kaleido`。Chrome は `uv run plotly_get_chrome` でも入る)。
- 追加の依存: `uv add "lab-kit[ml]"`(scikit-learn のモデルのメタ情報)、`[torch]`、`[marimo]`、`[viz]`(kaleido)。

### コマンド

| コマンド | 内容 |
|---|---|
| `lab-kit init [--dry-run] [--agents] [--dir DIR]` | Skill、`.gitignore` / `CLAUDE.md` のブロック、`.env.example`、marimo テンプレート、フォルダの雛形を入れる |
| `lab-kit update [--dry-run]` | 入れたものを最新にする(手元で編集したものは上書きしない) |
| `lab-kit labels [--kinds default\|名前,名前] [--repo OWNER/REPO] [--dry-run]` | decision-log 用のラベルを作る(無いものだけ。既にあるものは変更しない) |
| `lab-kit doctor` | Python、git、uv、gh のログイン、リポジトリの公開範囲、`init` 済みかを確認する |
| `lab-kit lineage [--dir DIR] [--out DIR] [--quiet]` | `*_metadata.yaml` からデータの系譜図(Mermaid)を `docs/data_lineage/` に出す |

## issue の使い方(GitHub を触ったことがない人向け)

### issue とは

作業や話題ごとに1ページ作れる、GitHub の記録用ページ。**本文**(上の部分)と、その下に時系列で積み上がる**コメント**でできている。このキットでは、**1つの研究テーマ = 1つの issue** にする。

### issue の見方

| 場所 | 書いてあること | 読み方 |
|---|---|---|
| タイトル | テーマ | |
| **本文** | **いまの結論**(現状のまとめ、方針、AsIs / ToBe、検証計画、決定の一覧、未解決の論点) | **まず本文だけ読めば、今どうなっているか分かる。** 決定が出るたびに更新される。 |
| **コメント** | 決定の記録(D1, D2…)、実験の経過、失敗 | **上から順に読めば、経緯が分かる。** 書き換えられず、追記だけされる。 |
| ラベル | 段階(`idea` `decided` `doing` `done`)、種類 | 一覧で、今どの段階かが分かる。 |
| open / closed | 開いている / 閉じている | `done` になったら closed。 |

### どこを見るか

ブラウザで自分のリポジトリを開き、上のタブの **Issues** を押す。

- 一覧の左のラベルで、段階が分かる。
- `label:idea` などで絞り込める(検索欄に `label:doing` と入れる)。
- 閉じたものも見るには、「Closed」を押す。

### 決定の記録(コメント)の読み方

1件が次の形でできている。迷ったら、「決定」と「背景」だけ読めばよい。

| 項目 | 意味 |
|---|---|
| 決定 | 何をどうすると決めたか |
| 決定者 | 自分か、先生との相談か、共同研究者か |
| 背景 | なぜその決定が必要になったか |
| 根拠 | データ・数値・ファイルのパス |
| 検討した代替案 | 他に何を考え、なぜ採らなかったか |
| 影響・残る問題 | その決定でできなくなること、未確認のこと |
| 過去の決定との関係 | 以前の決定を置き換えるか、前提にするか |

### ルール

1. **本文は最新の結論、コメントは時系列の記録。** コメントは書き換えない。方針が変わったら、本文を直し、変わった理由を新しいコメント(D)に書く。
2. **決定は、決めたらすぐ残す。** まとめて後で書かない。
3. **失敗も残す。** 試したが使えなかったものも、理由とともに書く。
4. **確認していないことは「未確認」と書く。** 推測と事実を混ぜない。
5. **元データの内容や個人情報は書かない。**
6. コミットのメッセージに `Refs #12` と書くと、issue #12 とコードの変更が結びつく。

### 先生との相談

相談は、テーマとは別に **`meeting` ラベルの issue** を作る。

- 相談の前: 「相談したいこと」を書く。
- 相談の後: 先生の指摘、**自分の理解**、決まったこと、TODO を書く。先生の発言と自分の解釈は分ける。
- 方針に関わる決定は、該当するテーマの issue に、決定の記録として追記する(「決定者」に相談の issue を書く)。
- **公開リポジトリでは作らない。** 先生や研究室の話が外から見えてしまうため、Skill が止める。

## 推奨するフォルダ構成

`lab-kit init` は `data/` と `results/` の雛形を作るだけで、他のフォルダは動かさない。移したいときは `lab-adopt` に頼む(移動案を表で見せ、承認された分だけ動かす)。

```text
.
├── pyproject.toml / uv.lock / .python-version
├── .env.example
├── CLAUDE.md
├── .claude/skills/        # Skill
├── .lab-kit/manifest.json # init が配ったファイルの記録(コミットしておく)
├── src/<project>/         # 再利用するコード
├── notebooks/             # marimo の .py だけ(_template.py が雛形)
├── scripts/               # CLI で回す重い処理
├── data/{raw,interim,processed}/   # 本体は gitignore。*_metadata.yaml だけ追跡
├── results/<実験名>/      # 図(PNG)・表。コミットするのはここ
└── docs/                  # 系譜図など、自動生成物
```

## 困ったとき

| 症状 | 原因と対処 |
|---|---|
| `uv add git+https://...` が認証で失敗する | このリポジトリが非公開で、招待されていない、または `gh auth setup-git` をしていない。 |
| 「`gh` が見つからない」 | GitHub CLI が未インストール。`doctor` の案内のリンクから入れる。 |
| 「ログインしていない」 | `gh auth login` を実行する。 |
| `lab-kit labels` が失敗する | `gh auth status` を確認する。リポジトリの外なら `--repo OWNER/REPO` を付ける。 |
| `*.lab-kit.new` ができた | 既に別の内容のファイルがあったため、上書きしなかった。差分を見て、必要なら取り込み、不要なら削除する。 |
| PNG が保存できない | `kaleido` と Chrome が必要。`uv add kaleido` と `uv run plotly_get_chrome`。 |
| 投稿されない | Claude が下書きを出して待っている。内容を確認して「OK」と答える。 |
| 間違えて投稿した | コメントは GitHub 上で編集・削除できる。ただし履歴に残り得るので、個人情報は特に注意する。 |

## 開発

```bash
uv sync
uv run ruff check src tests
uv run pytest -q
```

配布物(Skill など)は `src/lab_kit/scaffold/` にある。`init` / `update` は、そこから配る。

## ライセンス

MIT
