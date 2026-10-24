---
name: research-direction
description: Use when deciding what experiment or method change to try next, when reporting results against a baseline, or when choosing what goes into a comparison table. Reads the user's own goal and baseline policy from docs/research-direction.md (and helps write it if it is missing), then follows an evidence-first way of proposing next steps. Also use for "次に何を試す?", "研究の目的を整理して", "比較表に何を載せる?".
---

# 研究の目的と進め方

目的と比較の基準は、人によって違う。それは `docs/research-direction.md` に書いてもらい、この Skill には**進め方だけ**を置く。

## 最初にやること

`docs/research-direction.md` を読む。**無い、または「〈未記入〉」が残っていれば、先に書く手伝いをする**(下の「書く手伝い」)。目的が分からないまま、次の手を提案しない。

## 次の手を決める手順(思いつきで提案しない)

1. **結果A と 結果B を、同じ条件で比べる。** どの実験の、どの値かを、具体的に示す。
2. そこから言えること(示唆)を、1〜2文で書く。
3. その示唆から、**手法の案**を出す。なぜその案になるかを、示唆とつなげて書く。
4. **成功基準を、実験の前に決める。** 何を何と比べて、どの値を超えたら成功か。
5. 実験して、基準に照らして判断する。満たさなければ、その方向は見込みなしと書く。

- 数値による診断なしに、手法を提案しない。
- 真のラベルなどを使った分析は、「余地の見積もり」と明記する。結果の表には混ぜない。

## 結果を報告するとき

- 結論は、`docs/research-direction.md` の「目的」に沿って書く。目的と関係ないこと(例: 比較の基準を強くしただけ)を、成果にしない。
- 比較表に載せるものは、同じファイルの「比較の基準」に従う。参考として測っただけのものは、表に入れず、載せるかどうかを別に聞く。
- 何が効いていて、何が足りないかを書く。
- 説明は `explain-results`、図は `result-graphs` の型に従う。

## 守ること

- **リークなし**: 学習やハイパーパラメータの選択に、評価用の正解を使わない。使った分析は、余地の見積もりとして区別する。
- 比べる値は、同じ条件のものにする。
- 決まったことは、背景・根拠・検討した代替案とともに、`decision-log` で issue に残す。
- `docs/research-direction.md` の「守ること」も、同じ重みで守る。

## 書く手伝い

`docs/research-direction.md` が無いとき、または未記入のとき。

1. 次の4つを、**1つずつ**質問する。答えが短くてよい。
   1. 目的: 何を良くしたいのか。成功すると何が言えるのか。
   2. 比較の基準: 何と比べるのか(ベースライン)。比較表に載せるもの、載せないもの。
   3. 条件・制約: 実務や論文の設定、使えるデータ、前提。
   4. 守ること: 研究室や分野の決まり、避けたいこと(リークなど)。
2. 下書きを見せ、直しを受けてから、`docs/research-direction.md` に保存する。ユーザーが答えていない項目は、推測で埋めず「〈未記入〉」のままにする。
3. 決まった内容は、`decision-log` で issue に残すことを勧める。

雛形:

```markdown
# 研究の目的と進め方

## 目的
- <何を良くしたいか。成功すると何が言えるか>

## 比較の基準
- 比較表に載せる: <手法・ベースライン>
- 参考として測るが、表には載せない: <あれば>

## 条件・制約
- <設定、データ、前提>

## 守ること
- <決まり、避けたいこと>
```
