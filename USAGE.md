# 使い方ガイド

## 🚀 デプロイ済み環境

### APIエンドポイント
```
https://api-sl3kzkbdma-an.a.run.app
```

### GCPプロジェクト
- プロジェクトID: `auto-proposal-drafter`
- リージョン: `asia-northeast1`

---

## 📝 基本的な使い方

### 1. ドラフト生成リクエスト

```bash
curl -X POST https://api-sl3kzkbdma-an.a.run.app/v1/drafts:generate \
  -H "Content-Type: application/json" \
  -d '{
    "source": "manual",
    "record_id": "test-001",
    "payload": {
      "id": "OPP-001",
      "title": "新規LP制作",
      "company": "株式会社サンプル",
      "goal": "リード獲得",
      "persona": "企業の経営者",
      "deadline": "2025-12-31",
      "budget_band": "200-300万円",
      "must_have": ["問い合わせフォーム", "実績掲載"],
      "references": [],
      "constraints": ["短納期"],
      "assets": {"copy": false, "photo": true}
    }
  }'
```

レスポンス：
```json
{
  "job_id": "job_test-001_abc123",
  "status": "QUEUED"
}
```

### 2. ジョブステータス確認

```bash
curl https://api-sl3kzkbdma-an.a.run.app/v1/jobs/job_test-001_abc123
```

レスポンス：
```json
{
  "id": "job_test-001_abc123",
  "status": "COMPLETED",
  "progress": 1.0,
  "created_at": "2025-10-02T08:00:00Z",
  "updated_at": "2025-10-02T08:00:15Z",
  "outputs": {
    "structure": { ... },
    "wire": { ... },
    "estimate": { ... },
    "summary": "## 提案サマリ\n..."
  }
}
```

---

## 🎨 出力データの構造

### Structure JSON (サイト構造)
```json
{
  "site_map": [
    {
      "page_id": "top",
      "sections": [
        {
          "kind": "Hero",
          "variant": "Center",
          "h": 800,
          "design_hours": 4.0
        }
      ]
    }
  ]
}
```

### Wire JSON (Figmaワイヤーフレーム用)
```json
{
  "project": {
    "id": "OPP-001",
    "title": "株式会社サンプル 新規LP制作"
  },
  "frames": ["Desktop", "Tablet", "Mobile"],
  "pages": [
    {
      "page_id": "top",
      "sections": [
        {
          "kind": "Hero",
          "variant": "Center",
          "placeholders": {
            "headline": "株式会社サンプルがリード獲得を加速",
            "sub": "企業の経営者向けのリード獲得"
          }
        }
      ]
    }
  ]
}
```

### Estimate JSON (見積)
```json
{
  "line_items": [
    {
      "item": "IA設計",
      "qty": 1,
      "hours": 6.0,
      "rate": 8000,
      "cost": 48000
    }
  ],
  "coefficients": [
    {
      "name": "素材未提供（コピー）",
      "multiplier": 1.2,
      "reason": "コピー素材が未支給"
    }
  ],
  "assumptions": ["写真素材は支給前提"]
}
```

### Summary (マークダウンサマリー)
```markdown
## 提案サマリ
- 案件ID: OPP-001
- 目的: リード獲得
- セクション数: 8
- 基本見積: ¥319,200
- 係数適用後見積: ¥383,040

## 係数
- 素材未提供（コピー） ×1.20 (コピー素材が未支給)
```

---

## 🔧 Notionから自動取得（将来）

### 必要な設定
1. Notion Database IDを環境変数に設定
2. Cloud Schedulerが15分毎にポーリング
3. 新規レコードを自動的に処理

### 手動トリガー
```bash
curl -X POST https://api-sl3kzkbdma-an.a.run.app/v1/ingest/notion/poll
```

---

## 📊 管理画面

### GCPコンソール
- Cloud Run: https://console.cloud.google.com/run?project=auto-proposal-drafter
- Firestore: https://console.cloud.google.com/firestore?project=auto-proposal-drafter
- Logs: https://console.cloud.google.com/logs?project=auto-proposal-drafter

### ログ確認
```bash
# APIログ
gcloud run services logs read api --region=asia-northeast1 --limit=50

# Workerログ
gcloud run services logs read worker --region=asia-northeast1 --limit=50
```

### Figma Feed確認
```bash
# Cloud Storageの内容確認
gsutil ls gs://auto-proposal-drafter-figma-feeds/

# 特定のジョブのFigma feed
gsutil cat gs://auto-proposal-drafter-figma-feeds/job_xxx/wire.json
```

---

## 🔐 Secret Manager

設定済み：
- ✅ `notion-api-key` - Notion API key
- ✅ `asana-access-token` - Asana personal access token

未設定（必要なら追加）：
- `hubspot-api-key` - HubSpot API key
- `slack-signing-secret` - Slack signing secret
- `slack-bot-token` - Slack bot token

追加方法：
```bash
echo -n "YOUR_SECRET" | gcloud secrets versions add SECRET_NAME --data-file=-
```

---

## 🎨 Figmaプラグインでワイヤーを自動配置

1. `figma-plugin` ディレクトリで `npm install && npm run build` を実行。
2. Figma の **資産 → プラグイン → 開発 → manifest からインポート** を開き、`figma-plugin/dist/manifest.json` を指定。
3. プラグインを起動し、署名付きURLまたはローカルJSONを指定すると Desktop/Tablet/Mobile フレームが生成されます。
4. UIキットに存在しない `Section/<Kind>/<Variant>` は破線のプレースホルダーとして挿入され、警告エリアに一覧表示されます。

> テキスト差し込みはレイヤー名と JSON の `placeholders` キーを照合しています。UIキット側のレイヤー名を `headline`, `cta` など英数字で揃えておくと自動で流し込みされます。

---

## 🐛 トラブルシューティング

### ジョブがFAILEDになる
```bash
# エラー確認
curl https://api-sl3kzkbdma-an.a.run.app/v1/jobs/JOB_ID | jq '.errors'

# ログ確認
gcloud run services logs read api --region=asia-northeast1 | grep ERROR
```

### Figma feedが生成されない
現在dev環境のためバックグラウンドタスクで処理されます。
本番環境ではPub/Sub経由でWorkerが処理します。

### デプロイ更新
```bash
# コード変更後
gcloud builds submit --tag asia-northeast1-docker.pkg.dev/auto-proposal-drafter/containers/api:latest .
gcloud run services update api --region=asia-northeast1 --image=...
```

---

## 📚 関連ドキュメント

- `DEPLOYMENT.md` - デプロイ手順
- `CLAUDE.md` - アーキテクチャ概要
- `README.md` - プロジェクト概要
- `terraform/README.md` - インフラ詳細
