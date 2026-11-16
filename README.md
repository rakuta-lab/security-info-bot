# セキュリティ情報キャッチアップBot（月額0円版）

OS・アプリ・ブラウザの更新情報、脆弱性、注意喚起、サービス障害情報を自動で収集し、Discord / Slack / LINE へ優先度別に配信するBotです。

---

## 特徴
- **月額0円運用**：GitHub Actions（非公開リポジトリの月2,000分無料枠）で30分ごとに実行します。
- **優先度別の振り分け**：
  - 🚨 **緊急**：実際に悪用されている脆弱性（CISA KEV）や公的機関の注意喚起 → Discord `#🚨緊急` + Slack + LINE
  - ⚠️ **重要**：OS/ブラウザのセキュリティ更新、CVSS 7.0以上 → Discordカテゴリ別 + Slack
  - ℹ️ **通常**：通常更新、障害情報、How-to → Discordカテゴリ別
  - 📋 **日次まとめ**：低〜中程度の個別脆弱性 → 1日1回 Discord `#日次まとめ` に一覧で送信
- **ブラウザ更新促し**：Chrome / Firefox 等の更新情報には「ブラウザの更新確認」メッセージを自動付与します。
- **AI要約（任意）**：`GEMINI_API_KEY` を設定すると、緊急・重要記事を日本語で要約＋対応策を抽出します。

---

## セットアップ手順

### 1. ローカル作業フォルダへの配置（推奨）
Googleドライブ上ではGitの同期衝突が起きやすいため、ローカルディスク（`D:\Develop\security-bot`）にコピーして運用することを推奨します。

1. `D:\Develop\security-bot` フォルダを作成し、このフォルダの中身をすべてコピーします。
2. GitHubで **Private（非公開）リポジトリ** を1つ作成します（例：`security-info-bot`）。
3. `D:\Develop\security-bot` で以下を実行してGitHubへアップロードします：
   ```powershell
   cd D:\Develop\security-bot
   git init
   git add .
   git commit -m "feat: initial security bot"
   git branch -M main
   git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
   git push -u origin main
   ```

---

### 2. 配信先・APIキーの準備（使うものだけでOK）

#### A. Discord（メイン・必須おすすめ）
1. 自分専用のDiscordサーバーを作成します。
2. チャンネルを作ります（最初は `一般` だけでも動きます）。
   - おすすめ構成：`#🚨緊急` / `#脆弱性` / `#注意喚起` / `#os・アプリ更新` / `#ブラウザ` / `#障害情報` / `#対策・howto` / `#日次まとめ`
3. 各チャンネルの「設定（歯車）」→「連携サービス」→「ウェブフック」→「新しいウェブフック」から **ウェブフックURLをコピー** します。

#### B. Slack（サブ・任意）
1. Slack App（[api.slack.com/apps](https://api.slack.com/apps)）を作成し、「Incoming Webhooks」を有効化します。
2. 通知したいチャンネルを選んで Webhook URL を発行します。

#### C. LINE（緊急通知のみ・任意）
1. [LINE Developers](https://developers.line.biz/) で Messaging API チャネルを作成します。
2. 「チャネルアクセストークン（長期）」を発行します。
3. 「あなたのユーザーID」（チャネル基本設定画面の下部に表示される `U` から始まる文字列）を控えます。
4. 作成した公式アカウントをLINEで友だち追加します。

#### D. Gemini API（AI日本語要約・任意）
1. [Google AI Studio](https://aistudio.google.com/) で API キーを無料で発行します。

---

### 3. GitHub Secrets への登録
GitHubリポジトリの **Settings → Secrets and variables → Actions → New repository secret** から以下を登録します（使わないものは登録不要です）。

| Secret名 | 内容 |
|---|---|
| `DISCORD_WEBHOOK_DEFAULT` | デフォルトのDiscord Webhook URL（個別チャンネル未設定時はここへ送信） |
| `DISCORD_WEBHOOK_URGENT` | `#🚨緊急` チャンネル用 |
| `DISCORD_WEBHOOK_VULNERABILITY` | `#脆弱性` チャンネル用 |
| `DISCORD_WEBHOOK_ADVISORY` | `#注意喚起` チャンネル用 |
| `DISCORD_WEBHOOK_OS_APP` | `#os・アプリ更新` チャンネル用 |
| `DISCORD_WEBHOOK_BROWSER` | `#ブラウザ` チャンネル用 |
| `DISCORD_WEBHOOK_OUTAGE` | `#障害情報` チャンネル用 |
| `DISCORD_WEBHOOK_HOWTO` | `#対策・howto` チャンネル用 |
| `DISCORD_WEBHOOK_DIGEST` | `#日次まとめ` チャンネル用 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API チャネルアクセストークン |
| `LINE_USER_ID` | LINE 送信先のユーザーID |
| `GEMINI_API_KEY` | Gemini API キー |

---

### 4. 動作確認（初回実行）
1. GitHubリポジトリの **Actions** タブを開き、「Collect Security Info」を選択します。
2. **Run workflow** をクリックして手動実行します。
3. **初回は過去の記事が一気に通知されるのを防ぐため、「既読登録のみ」が行われます。**
4. 2回目以降（30分ごとの自動実行、または手動実行）から、新着情報のみが配信されます。

---

## 週1回のGoogleドライブ自動バックアップ（任意）
`scripts/backup_to_gdrive.ps1` を使うと、`D:\Develop\security-bot` を日付付きZIPにしてGoogleドライブへ自動保存できます（直近10世代を保持）。

PowerShellで手動テスト：
```powershell
powershell -ExecutionPolicy Bypass -File D:\Develop\security-bot\scripts\backup_to_gdrive.ps1
```
Windowsの「タスクスケジューラ」に週1回で登録すれば自動化できます。

---

## カスタマイズ方法
- **情報源を増やす・減らす**：`config/sources.yaml` を編集して push するだけ
- **緊急にするキーワードを変える**：`config/rules.yaml` を編集して push するだけ
