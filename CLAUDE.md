# このリポジトリについて

研究用の共通道具と Skill を、他のプロジェクトに入れるためのキット(`lab-kit`)。入れ方は `README.md` にある。

## 「〇〇に導入して」と頼まれたとき

導入先のプロジェクトを `<target>` とする。**書き換える前に、必ず内容を見せて、承認を得る。**

1. **導入先を決める。** パスが分からなければ聞く。`<target>` が git リポジトリか確認する(`git -C <target> status`)。未コミットの変更があれば、先にコミットするよう勧める。
2. **前提を確認する。** `uv`、`git`、`gh` の有無。無いものは入れ方を伝える(勝手に入れない)。
3. **パッケージを入れる。** `<target>` で次を実行する。ローカルのパスではなく、**git の URL** を使う(パスを使うと、`pyproject.toml` に自分の PC のパスが入ってしまう)。
   ```bash
   cd <target>
   uv init --bare        # pyproject.toml が無いときだけ
   uv add git+https://github.com/mksmkss/mksmkss-lab-kit
   ```
4. **何が変わるか見せる。** `uv run lab-kit init --dry-run` の出力を見せ、承認を得る。
5. **入れる。** `uv run lab-kit init`。`*.lab-kit.new` ができたら、差分を見せて、取り込むか聞く。
6. **確認する。** `uv run lab-kit doctor`。注意が出たら、直し方を伝える。
7. **marimo 公式の Skill を入れてよいか聞く。** 承認されたら、`<target>` で実行する(node が必要)。
   ```bash
   npx skills add marimo-team/skills --agent claude-code --skill jupyter-to-marimo --skill marimo-notebook
   ```
8. **GitHub のラベル。** `decision-log` を使うなら、`uv run lab-kit labels --dry-run` を見せ、承認を得て `uv run lab-kit labels` を実行する(`gh auth status` が通っていること)。
9. **既存の Jupyter があれば、marimo に変換する案を出す。** `uv run lab-kit to-marimo --dry-run` を見せ、承認を得てから変換する。
10. **既存コードの移行は、`lab-adopt` Skill で行う。** 導入先で Claude を開き直して頼むよう、案内する(Skill は次のセッションから読み込まれる)。

導入後は、何を入れ、何を変えず、何が残っているか(未実行のものを含む)を短く報告する。

## このリポジトリを開発するとき

- 配布物は `src/lab_kit/scaffold/`(Skill、`CLAUDE.md` / `.gitignore` のブロック、`.env.example`、marimo テンプレート)。`init` / `update` はそこから配る。
- **`init` は既存ファイルを壊さない。** 無いものは作る、同じなら何もしない、違えば `*.lab-kit.new` を置く、が決まり。この性質を変える変更には、テストを足す。
- 変更したら、次を通す。
  ```bash
  uv run ruff check src tests
  uv run pytest -q
  ```
- Skill や README は、短く、自然な日本語で書く。直訳調や、重複した説明を避ける。
- 数値は Python で計算する。
