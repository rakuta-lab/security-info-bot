# 実装計画：月額0円 セキュリティ情報Bot（自分専用・網羅型）

## 前提条件
| 項目 | 回答 | 設計への影響 |
|---|---|---|
| 利用者 | 自分のみ | 認証・マルチユーザー不要／ストア公開不要 → 構成を大幅に簡略化 |
| チャット | Slack / Discord / LINE | **Discordをメイン**、Slackはサブ、LINEは緊急のみ（理由は後述） |
| 範囲 | 網羅型 | 情報量が多いため**通知の振り分け（優先度別）が必須** |
| 予算 | **0円** | サーバーは借りず、無料枠だけで動く構成にする |

---

## 1. 0円構成

```mermaid
flowchart LR
  GA["GitHub Actions<br/>(定期実行・無料枠)<br/>Python"] -->|RSS/API取得| SRC["情報ソース<br/>JVN / JPCERT / IPA / CISA KEV<br/>MSRC / Apple / Chrome / Mozilla<br/>各社Status Page など"]
  GA -->|要約・分類(任意)| GEM["Gemini API<br/>無料枠"]
  GA -->|既読管理| ST[("state.json<br/>リポジトリ内に保存")]
  GA --> D["Discord（メイン）<br/>カテゴリ別チャンネル"]
  GA --> S["Slack（サブ）"]
  GA --> L["LINE（緊急のみ）"]
```

| 役割 | サービス | 無料枠 | 想定使用量 |
|---|---|---|---|
| 定期実行 | **GitHub Actions**（privateリポジトリ） | 月2,000分 | 30分間隔×約1分 ≒ 月1,500分 ✅ |
| データ保存 | リポジトリ内の JSON ファイル | 無料 | 既読IDのみ（数MB以内） |
| AI要約 | Gemini API 無料枠 | 1日あたりのリクエスト上限あり（※変更の可能性あり） | 新着のみ要約、上限時は要約なしで配信 |
| メイン配信 | Discord Webhook | 無制限・履歴も無期限 | — |
| サブ配信 | Slack Incoming Webhook | 無料（無料プランは**履歴90日**） | — |
| 緊急配信 | LINE Messaging API | **月200通まで** | 緊急のみなら月数十通 ✅ |

> [!NOTE]
> 支払い方法を登録しなければ、無料枠を超えても**課金されず止まるだけ**なので、0円は守れます（GitHubの初期設定は使用上限\$0）。

### なぜDiscordがメインか
- 無料で**履歴が無期限**、チャンネルを分ければそのまま「カテゴリ別ダッシュボード」になる
- Slack無料プランは90日で履歴が見られなくなる
- LINEは月200通の制限があるため、網羅型の全件配信には向かない

---

## 2. 通知の振り分け（網羅型でも埋もれないための工夫）

| 優先度 | 条件の例 | Discord | Slack | LINE |
|---|---|---|---|---|
| 🔴 緊急 | CISA KEV新規掲載（実際に悪用されている）、JPCERT/CC注意喚起、CVSS 9.0以上、ゼロデイ／緊急パッチ | `#🚨緊急` | ✅ | ✅ |
| 🟠 重要 | CVSS 7.0以上、主要ベンダーのセキュリティ更新（MS月例パッチ・Apple・Chrome等） | カテゴリ別チャンネル | ✅ | — |
| 🟢 通常 | 通常のバージョンアップ、障害の復旧報告、How-to記事 | カテゴリ別チャンネル | — | — |
| 📋 まとめ | 低〜中程度の脆弱性（大量） | 1日1回 `#日次まとめ` に一覧で | — | — |

**Discordチャンネル案**：`#🚨緊急` / `#脆弱性` / `#OS・アプリ更新` / `#ブラウザ` / `#障害情報` / `#対策・howto` / `#日次まとめ`

※ ルールは設定ファイル（YAML）で後から自由に調整できるようにします。

---

## 3. 情報ソース（初期セット・すべて無料のRSS/API）

| カテゴリ | ソース |
|---|---|
| 脆弱性 | JVN（新着RSS）、CISA KEV（JSON）、NVD API（CVSS取得用）、GitHub Security Advisories |
| 注意喚起 | JPCERT/CC 注意喚起、IPA 重要なセキュリティ情報、CISA Alerts |
| OS・アプリ更新 | Microsoft MSRC、Windows Release Health、Apple Security Releases、Android Security Bulletin、Adobe |
| ブラウザ | Chrome Releases、Mozilla Security Advisories、Microsoft Edge セキュリティ更新 |
| 障害情報 | 各社 Status Page（GitHub、Slack、Discord、Cloudflare、AWS、Google Cloud、Microsoft 365 等。多くはRSSを提供） |
| 二次情報・How-to | セキュリティ系ニュースサイトのRSS（ScanNetSecurity、BleepingComputer 等） |

> [!WARNING]
> Downdetector や X（旧Twitter）は規約・費用の面で**対象外**とします（0円条件と両立しないため）。

---

## 4. ディレクトリ構成（予定）
```
情報収集Bot/
├─ .github/workflows/collect.yml   # 30分ごとの定期実行
├─ config/
│   ├─ sources.yaml                 # 情報ソース一覧（追加・削除が簡単）
│   └─ rules.yaml                   # 優先度・振り分けルール
├─ src/
│   ├─ collectors/                  # RSS / JSON API 取得
│   ├─ normalize.py                 # 名寄せ・重複排除（CVE ID・URL）
│   ├─ classify.py                  # カテゴリ・優先度判定
│   ├─ summarize.py                 # Gemini要約（失敗時は要約なしで続行）
│   ├─ notifiers/                   # discord / slack / line
│   └─ main.py
├─ state/state.json                 # 既読ID（自動コミット）
└─ README.md                        # セットアップ手順
```

---

## 5. 懸念点と対策（0円構成ならでは）
| 懸念 | 対策 |
|---|---|
| GitHub Actionsのcronは**数分〜数十分遅れることがある** | 「即時」ではなく「30分以内」を目標にする。速報性が必要なら代替案（GAS）を併用 |
| Gemini無料枠の上限・仕様変更 | 要約は任意機能。失敗してもタイトル＋リンク＋ルールベースの分類で配信は続ける |
| 無料枠の入力データはGoogleのモデル改善に使われる場合あり | 扱うのは公開情報のみなので実害なし |
| 初回実行で過去記事が大量に流れる | 初回は「既読登録のみ・通知しない」モード |
| ワークスペースがGoogleドライブ上 | Git管理するフォルダをドライブ同期すると衝突することがある → 本体はGitHub上で管理し、ドライブはコピー扱いにすることを推奨 |

### 代替案：Google Apps Script（GAS）
GitHubアカウントがない／より短い間隔で動かしたい場合の選択肢です。Googleアカウントだけで無料で動き、間隔を1〜5分まで短くでき、スプレッドシートを閲覧画面として使えます。ただしJavaScriptでの実装になり、実行時間の制限（1回6分・トリガーは1日90分）があるため、大量のソースを回すには工夫が要ります。

---

## 6. ご用意いただくもの（実装後にREADMEで手順を案内します）
1. GitHubアカウント（privateリポジトリを1つ作成）
2. Discord：自分用サーバー＋チャンネルごとのWebhook URL
3. Slack：Incoming Webhook URL
4. LINE：LINE Developers で Messaging APIチャネルを作成（アクセストークン・自分のユーザーID）
5. （任意）Gemini APIキー（Google AI Studioから無料で発行）

これらは**GitHub Secrets**に登録し、コードには一切書きません。

---

## 7. 進め方
1. **ステップ1**：収集＋振り分け＋Discord通知（AI要約なし）をローカルで動作確認
2. **ステップ2**：Slack・LINE通知、Gemini要約を追加
3. **ステップ3**：GitHub Actionsで自動運用開始
4. **ステップ4（任意）**：Chrome拡張（自分用は「パッケージ化されていない拡張機能を読み込む」で**ストア登録料なしの0円**で使えます）
