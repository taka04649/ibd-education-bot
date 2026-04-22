# IBD Education Bot

PubMed から **IBD（炎症性腸疾患）関連の信頼度の高い論文**を自動取得し、Claude Sonnet で **教育的解説** を生成して Discord に **1日4回** 投稿する bot です。

- **対象**: UC, CD, IBDU, pouchitis, IBD 関連合併症（広め）
- **論文範囲**: 直近 **1年以内**
- **品質**: RCT / Meta-analysis / Systematic Review / Practice Guideline / Phase II-III + IBD主要誌
- **投稿頻度**: 1日4回（JST 07:00 / 12:00 / 18:00 / 22:00）× **2本/回 = 合計8本/日**
- **想定コスト**: 約 **$5〜7 / 月**

---

## 特徴

### 🎯 信頼度スコアリングで「本当に読む価値のある論文」を選定

毎回 **80本の候補**から PubMed で取得し、**信頼度スコア**で上位 2 本を自動選定:

| 基準 | 配点 |
|---|---|
| Practice Guideline | +100 |
| Meta-Analysis | +85 |
| Systematic Review | +80 |
| RCT | +70 |
| NEJM / Lancet 掲載 | +30 |
| Gastroenterology / Gut 掲載 | +25 |
| 構造化 abstract（結論明記） | +3〜8 |

→ 1年以内の論文でも玉石混交の中から、**ガイドライン > meta > RCT** の順で教育的価値の高いものを優先します。

### 📚 教育的解説の3本柱

単なる要約ではなく、以下の3つをバランス良く含む解説を生成:

1. **エビデンスの読み方** — 研究デザイン、バイアス、統計、エンドポイントの妥当性
2. **臨床推論** — 診断・鑑別・治療選択のロジック、現場での活用法
3. **アルゴリズム位置づけ** — ガイドラインや既存エビデンスの中での相対位置

### ⏰ 時間帯別ヘッダー

投稿時刻に応じてヘッダーが変わります:

- ☀️ **朝のIBDダイジェスト** (07:00)
- 🍱 **昼のIBDダイジェスト** (12:00)
- 🌇 **夕のIBDダイジェスト** (18:00)
- 🌙 **夜のIBDダイジェスト** (22:00)

### 🔒 重複投稿防止

投稿済み PMID を `data/posted_pmids.json` に最大 5,000 件記録。1日4回投稿しても同じ論文が流れません。

---

## 構成

```
ibd-education-bot/
├── .github/
│   └── workflows/
│       └── daily_digest.yml     # 1日4回実行
├── src/
│   ├── main.py                  # エントリポイント
│   ├── config.py                # IBD全般クエリ
│   ├── pubmed_client.py         # PubMed + 信頼度スコアリング
│   ├── claude_client.py         # 教育的解説プロンプト
│   └── discord_client.py        # 時間帯別ヘッダー
├── data/
│   └── posted_pmids.json
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 導入手順

### 1. Discord Webhook の作成（専用チャンネル推奨）

1. Discord で **IBD 論文専用のチャンネル** を新規作成（例: `#ibd-education`）
2. チャンネル設定 → 連携サービス → ウェブフック → 新しいウェブフック
3. 名前: `IBD Education Bot`
4. Webhook URL をコピー

### 2. Anthropic API キーの取得

既存の appendix / UC / CD bot と同じキーで OK（リポジトリごとに Secrets に登録する必要はあり）。

1. <https://console.anthropic.com/> にログイン
2. API Keys → Create Key
3. Billing で $10〜20 チャージ
4. Usage limits で月額上限を設定（全 bot 合算で $15〜20 が目安）

### 3. PubMed API キー（推奨）

他 bot と同じキーを使い回せます。

### 4. 新規 GitHub リポジトリの作成

**他の bot とは別リポジトリ** として作成してください:

- Repository name: `ibd-education-bot`
- Public
- README は追加しない

### 5. ファイルのアップロード

zip を解凍して、中身すべてを GitHub にアップロード。**必ず `.github/workflows/daily_digest.yml` が含まれていることを確認**してください。

### 6. GitHub Secrets の登録

Settings → Secrets and variables → Actions で以下を登録:

| Secret 名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `DISCORD_WEBHOOK_URL` | 専用チャンネルの Webhook URL |
| `PUBMED_API_KEY` | NCBI で発行（任意） |
| `PUBMED_EMAIL` | 自分のメールアドレス（任意） |

### 7. Workflow permissions の確認

Settings → Actions → General → **Read and write permissions** を有効化。

### 8. 初回手動テスト

Actions タブ → **IBD Education Daily Digest (4 times/day)** → Run workflow。

Discord に 2 本の論文が流れてくれば成功 🎉

---

## cron 実行時刻の調整

デフォルトは JST 07:00 / 12:00 / 18:00 / 22:00。変更したい場合は `.github/workflows/daily_digest.yml` の cron を編集:

```yaml
on:
  schedule:
    - cron: '0 22 * * *'   # UTC 22:00 = JST 07:00
    - cron: '0 3 * * *'    # UTC 03:00 = JST 12:00
    - cron: '0 9 * * *'    # UTC 09:00 = JST 18:00
    - cron: '0 13 * * *'   # UTC 13:00 = JST 22:00
```

> ⚠️ GitHub Actions の cron は **完全な定時実行ではなく、数分〜数十分の遅延**が発生することがあります（混雑時）。厳密な時刻保証が必要な場合は外部スケジューラの使用を検討してください。

---

## コスト試算

Claude Sonnet 4.5（$3/Mtok input, $15/Mtok output）:

| 項目 | 使用量/日 | 月額 |
|---|---|---|
| 入力トークン（8論文/日、abstract + prompt） | ~12,000 tok | ~$1.08 |
| 出力トークン（8論文/日、900-1100字/本） | ~10,000 tok | ~$4.50 |
| **合計** | | **~$5.58/月** |

### 既存 bot との合算（4 bot 運用時）

| Bot | 月額 |
|---|---|
| Appendix | ~$2.25 |
| UC | ~$3.10 |
| CD | ~$3.16 |
| **IBD Education** | **~$5.58** |
| **合計** | **~$14.09/月** |

$20 予算内に十分収まります。

---

## カスタマイズ

### 信頼度スコアの調整

`src/pubmed_client.py` の `PTYPE_SCORE` / `JOURNAL_BONUS` を編集。自分の関心に合わせて重み付けできます。

例: PSC-IBD 関連を優先したいなら、タイトルに "sclerosing cholangitis" を含む論文に加点する処理を `_calculate_trust_score` に追加:

```python
if "sclerosing cholangitis" in paper.get("title", "").lower():
    score += 20
```

### 検索期間の変更

`src/config.py` の `'"1 year"[PDat]'` を `'"6 months"[PDat]'` などに変更。

### 1回の投稿本数変更

`src/config.py` の `MAX_PAPERS_PER_RUN = 2` を変更。ただし3本以上にするとコストが増える点に注意。

### 解説の深さ調整

`src/claude_client.py` の `SYSTEM_PROMPT` を編集。「エビデンスの読み方」セクションを削れば簡潔に、「臨床推論」を強化すれば現場寄りに。

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| 論文が全然ヒットしない | 検索期間が `"1 year"[PDat]` なので、初回は多く出るはず。0件なら PUBMED_QUERY の主要誌フィルタが厳しすぎる可能性 |
| 同じ論文が複数回投稿される | `data/posted_pmids.json` が commit されていない。Workflow permissions を確認 |
| cron 実行が予定時刻より遅れる | GitHub Actions の仕様。数分〜30分程度の遅延は通常 |
| 複数 cron が同時実行される | `concurrency` 設定済みなので、実質直列実行される |
| ヘッダーの時間帯が合わない | サーバーは UTC で動くが、コード側で JST 変換済み。問題なければそのまま |

---

## 教育的論文の例（このBotが拾うべき論文）

- **Guidelines**: ECCO / AGA / 日本消化器病学会のガイドライン更新
- **Meta-analyses**: biologic の network meta-analysis、treatment sequencing 比較
- **RCT**: 新規薬剤の Phase III、治療戦略比較（top-down vs step-up）
- **Major trials**: SEQUENCE (risankizumab vs ustekinumab in CD)、VEGA、DUET-UC など
- **Real-world evidence**: 日本を含むアジアコホート、高齢者 IBD、妊娠中の治療

---

## ライセンス

MIT
