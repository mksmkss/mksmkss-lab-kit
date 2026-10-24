---
name: result-graphs
description: Use whenever an experiment or diagnostic produces results to report or record (結果の報告・記録・発表資料). Makes one plotly graph per check, saves it as PNG with Japanese-safe fonts, verifies the image by looking at it, and keeps the data behind it with metadata. Optionally embeds the PNG in a GitHub issue comment.
---

# 結果はグラフにして残す

発表やスライドにそのまま使える材料と、決定の根拠を視覚的に辿れる記録が欲しい。**表だけで終わらせず、1つの確認(1つの論点)ごとにグラフを作って残す。**

## 何をグラフにするか
- パラメータを動かした結果(例: 設定値を変えていったときの指標の折れ線)。
- 条件どうしの比較(例: 手法A と 手法B、n を変えたときの値とばらつき)。
- 意思決定に使えるもの(最適値の位置、平らな範囲、危険な領域)が見えるものを優先する。
- 1枚に詰め込みすぎない。ただし、同じ論点の指標(選択基準・評価指標・副作用)は、横に並べて1枚にする。

## 作り方
- `plotly` を使い、`lab_kit.viz` で日本語が文字化けしないようにする。
  ```python
  from lab_kit import results_path
  from lab_kit.viz import save_figure

  png = save_figure(fig, results_path("<実験名>", "figures", "<図の名前>"))
  ```
  PNG の保存には `kaleido` が必要(`uv add kaleido` か `uv add "lab-kit[viz]"`)。
- 題に、条件(手法、何 seed、何件)を書く。基準線(従来の値、下限など)を入れる。ばらつきがあれば、seed ごとの細線や ±1 std の帯を入れる。
- 保存先は `results/<実験名>/figures/`。HTML は確認用で、`.gitignore` 対象。
- 図の元になったデータ(CSV など)は `save_data_with_metadata` で、メタ情報と一緒に保存する。

## 残す前に必ず確認する
- 作った PNG を `Read` で開いて、目で確認する。よくある不具合: 不要な注釈、x軸の範囲が広すぎる、第2軸が分かれていない、凡例・題が切れている、日本語が □ になっている。直してから残す。
- 軸の意味が、図だけで読める(軸名・単位・対数軸かどうか)。

## issue に載せる(`decision-log` を使っている場合)
1. PNG だけをコミットして push する(CSV・HTML は `.gitignore`)。コミットはユーザーの許可を得る。他の未コミット分を混ぜない。
2. issue のコメントには、**commit sha 固定**の URL で貼る。
   `![題](https://github.com/<owner>/<repo>/blob/<commit sha>/<PNGのパス>?raw=true)`
   `<owner>/<repo>` は `gh repo view --json nameWithOwner --jq .nameWithOwner` で取得する。
3. 図の直下に、図の読み方を1行(細線・太線・破線が何か)書く。表も併記する。
4. 結果の説明は `explain-results` の型、決定の記録は `decision-log` の型に従う。
5. 投稿後、画像が表示されるかをユーザーに確認してもらう。
6. 公開リポジトリでは、元データの内容が写っていないか確認してから貼る。

## 守ること
- 図の中の値と、本文の表の値が一致していること。
- 図からは分からない結論を書かない。未確認のことは「未確認」と書く。
- 失敗した条件、効かなかった方向のグラフも残す。
