# Snowflake エージェント（プレビュー）とセマンティックビュー（プレビュー）まとめ

> **要点**
> エージェントもセマンティックビューも、Snowflake のスキーマレベルの「オブジェクト」。
> テーブルやビューと同じで、作り方（SQL / Snowsight GUI / CoCo / Workspaces）が違っても出来上がるオブジェクトは同じ。
> 画像にある「エージェント（プレビュー）／セマンティックビュー（プレビュー）」は、**Snowsight の Workspaces（ワークスペース）の「+ 新規追加」メニュー**から、
> **YAML 定義ファイルとして作成 → 「デプロイ」ボタンでオブジェクト化**する、新しいファイルベースの作成インターフェース。
> （詳細は「4. Workspaces の＋新規追加からの作成」を参照）

---

## 0. 前提の補足（CoCo について）

CoCo（旧 Cortex Code）で対話形式にエージェントやセマンティックビューを作れる、という理解は正しい。ただし CoCo が呼び出しているのは「バンドルスキル」で、作成ワークフローごとに担当スキルが分かれている。

| ワークフロー | 担当スキル |
| --- | --- |
| エージェント作成の全体フロー | `agent-studio`（CoCo が自動読み込み、またはプロンプトで指定） |
| セマンティックビュー生成 | `semantic-view` |
| エージェント作成 | `cortex-agent` |

> **補足（実環境での確認）**：上表は公式ドキュメントに記載のスキル名。ただし実環境の Workspaces では、`/semantic_studio` という**統合スキル**が使われており、これ 1 つで**セマンティックビューとエージェントの両方**を作成できる（後述の「4. Workspaces の＋新規追加からの作成」を参照）。当初想定した個別スキル名（`semantic-view` / `cortex-agent` / `agent-studio`）は、実環境ではこの統合スキルに集約されている。

---

## 1. エージェントとセマンティックビューの機能

### セマンティックビュー（Semantic View）

ビジネス概念をデータベース内に直接格納するスキーマレベルのオブジェクト。物理的なテーブル構造とビジネス用語のギャップを埋めるのが役割。

- 例：「gross revenue（総収益）」が実際には `amt_ttl_pre_dsc` のような分かりにくいカラム名で保存されていても、セマンティックビューが**正しい集計ロジック付きで一貫した定義**を与える。
- すべてのエージェントとアナリストが同じ**ガバナンスされた定義**を参照するため、AI がビジネスロジックを取り違える（ハルシネーション）のを防ぐ。

**構成要素**

| 要素 | 役割 |
| --- | --- |
| **TABLES** | ビジネスエンティティを物理テーブルにマッピングし、主キーを宣言 |
| **RELATIONSHIPS** | テーブル間の結合パスを明示的に定義（Cortex Analyst に結合方法を教える） |
| **FACTS** | 集計前の行レベルの定量属性（個々の売上額など） |
| **DIMENSIONS** | カテゴリでのスライス軸（商品カテゴリ、地域、注文日など） |
| **METRICS** | fact を集計して導出するビジネス KPI（総収益、平均注文額など） |

### エージェント（Cortex Agents）

セマンティックビューなどを「ツール」として使い、自然言語の質問に答えるオーケストレーター。

- まずツールを持たないエージェントを作成（この時点では言語モデルの一般知識だけで回答）。
- その後セマンティックビューを作り **Cortex Analyst ツール**を付与すると、質問から SQL を生成してそのビューに対して実行できるようになる。
- Cortex Analyst（構造化データ）だけでなく、**Cortex Search（非構造化テキスト）／Web 検索／カスタムツール**も束ねられる。
- **Snowflake Intelligence** のチャット UI のエンジンとしても動作する。

---

## 2. これまでの作成方法との違い

### 作成手段の全体像

**従来からある方法**

- **SQL コマンド**
  `CREATE SEMANTIC VIEW` / `CREATE AGENT` を直接記述。最も細かく制御できるが記述量が多い。
- **CoCo（対話型）**
  対話でオブジェクトを生成。`semantic-view` スキルがテーブルのメタデータからセマンティックビューを自動生成し、カラムに説明・サンプル値・シノニムを注釈付けしてデプロイまで行う。SQL を書かずに済む。
- **YAML / Autopilot / dbt**
  YAML からの生成、既存クエリや BI 資産から自動生成する **Semantic View Autopilot**、dbt でのコード管理など。

**今回の「Snowsight 上のネイティブ UI」**

- 会話（CoCo）でもコード（SQL）でもなく、**Snowsight の画面（ウィザード／オブジェクトエクスプローラー）から直接オブジェクトとして作成・管理する方法**。
- セマンティックビュー：ウィザードが作成プロセスをガイドし、YAML 仕様のアップロードも可能。
- エージェント：Snowsight から Python や REST API を使わずに作成・設定でき、画面上でエージェントと会話して挙動を確認したり、**トレース（思考ログ）を表示してデバッグ**したりできる。

### 3 つの作成体験の位置づけ

| 作成方法 | 性格 | 向いているユーザー |
| --- | --- | --- |
| SQL コマンド | コードで完全制御 | エンジニア／細かい制御が必要な人 |
| **Snowsight UI（今回）** | GUI ウィザードで項目を埋めるフォーム型 | 構造を確認しながら自分で作りたい人 |
| CoCo | AI に任せる会話型 | SQL を書きたくない業務ユーザー |

> **違いは「出来上がるオブジェクト」ではなく「作成体験（UX）」。**
> 今回の Snowsight UI は SQL と CoCo の中間で、SQL を書けない業務ユーザーでも、会話任せにせず自分で構造を確認しながら作れるのが狙い。

---

## 3. 実際の作成の流れ（CoCo での作成）

CoCo は、自然言語のプロンプトを投げるだけで、対応する**バンドルスキル**を自動で読み込み、セマンティックビュー → エージェントを一気通貫で作成できる。以下は Snowflake 公式クイックスタート（Summit Gear Co. の営業アシスタントを作る例）に沿った流れ。

### STEP 0. 事前準備（CLI の場合）

```bash
# インストール（macOS / Linux / WSL）
curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh

# 起動 → 初回はアカウント接続をガイドしてくれる
cortex
```

> Snowsight を使う場合は、画面右下の **CoCo アイコン**から起動する（インストール不要）。

### STEP 1. （必要なら）データを用意する

CoCo に自然言語で指示すると、データベース・スキーマ・テーブル・サンプルデータの生成／ロードまで行える。

```
Set up a sales database for Summit Gear Co. ...
（DEALS テーブルと SALES_CONVERSATIONS テーブルを作成し、合成データを投入する指示）
```

作成後は件数などで確認する。

```
How many rows are in SUMMIT_GEAR_CO.SALES.DEALS and SUMMIT_GEAR_CO.SALES.SALES_CONVERSATIONS?
```

### STEP 2. セマンティックビューを作る

対象テーブルを指定して依頼するだけ。CoCo が `semantic-view` スキルを読み込む。

```
Create a semantic view for the SUMMIT_GEAR_CO.SALES.DEALS table
```

`semantic-view` スキルの動作:

1. テーブルのメタデータからセマンティックビューを**自動生成**
2. カラムに**説明・サンプル値・シノニム**を注釈付け
3. Snowflake 上に**作成・デプロイ**

> 命名や保存先などを聞かれたら、基本はデフォルトを選べばよい。

### STEP 3. （任意）非構造化データ用の検索サービスを作る

会話ログなどを扱う場合は、Cortex Search サービスも自然言語で作成できる。

```
Create a Cortex Search service called SALES_CALL_SEARCH on the transcript_text column ...
```

### STEP 4. エージェントを作る

使わせたいツール（セマンティックビュー＋検索サービス）を指定して依頼。CoCo が `cortex-agent` スキルを読み込む。

```
Create an agent called SUMMIT_GEAR_AGENT in SUMMIT_GEAR_CO.SALES
that uses the SALES_CALL_SEARCH cortex search service and the deals semantic view
```

`cortex-agent` スキルの動作:

1. エージェントのワークスペースを初期化
2. 両ツールを含む**エージェント仕様を構築**
3. 質問を適切なツールに振り分ける**オーケストレーション指示を生成**
4. REST API 経由で**デプロイ**

完成したエージェントは 2 つのツールを持つ:

| ツール | 役割 |
| --- | --- |
| **Cortex Search** | 会話トランスクリプトの検索 |
| **Cortex Analyst** | セマンティックビュー経由で構造化データを text-to-SQL で照会 |

### STEP 5. エージェントをテストする

CoCo から直接チャットして挙動を検証できる。

```
# 構造化データ（Cortex Analyst 経由）
Chat with agent SUMMIT_GEAR_CO.SALES.SUMMIT_GEAR_AGENT and ask:
What is our win rate by territory this quarter?

# 非構造化データ（Cortex Search 経由）
Ask the agent: What objections came up in recent calls about our Alpine Pro boots?

# 両ツールの複合
Ask the agent: How is Sophie Nakamura performing in the Northeast,
and what themes come up in her sales calls?
```

質問の内容に応じて、CoCo が構築したエージェントが Cortex Analyst / Cortex Search を自動で使い分ける。

> **ポイント**：CoCo が提案・実行する各オブジェクト（セマンティックビュー・エージェント等）は、SQL を実行させる前に**内容をレビューすること**が推奨されている。

---

## 4. Workspaces の「＋新規追加」からの作成（画像のプレビュー機能）

質問の起点となった画像は、**Snowsight の Workspaces（ワークスペース）の「＋ 新規追加」メニュー**であり、ここに **セマンティックビュー（PREVIEW）** と **エージェント（PREVIEW）** が加わっている。Workspaces はファイルベースの開発環境なので、ここでの作成は「**YAML 定義ファイルを作る → デプロイしてオブジェクト化する**」という流れになる。前述の SQL / Cortex Analyst ウィザード / CoCo とは別の、**第4の作成インターフェース**にあたる。

> **本セクションの位置づけ**：以下のうち、YAML 仕様・デプロイの一般動作・CoCo スキルの仕組みは公式ドキュメントで裏づけがある。一方、3択パネル・デプロイボタン・`/semantic_studio` の自動起動といった画面挙動は、**実環境での確認に基づく（2026年8月時点・プレビュー）**。プレビュー機能のため、UI や名称は今後変わる可能性がある。

### 共通の仕組み

- 成果物は **ワークスペース内の YAML 定義ファイル**（セマンティックビュー・エージェントいずれも）。
- ファイル上部の **「デプロイ」ボタン**で、スキーマ上の実体オブジェクトに変換する。
- **格納先（データベース・スキーマ）は、デプロイ／保存の段階で指定**する（作成開始時ではない）。

### セマンティックビュー（PREVIEW）の流れ

1. 「＋ 新規追加」→ **セマンティックビュー（PREVIEW）** を選択。
2. 作成方式を選ぶ **3択パネル**が表示される。
   - **ウィザード**：GUI で項目を埋めて作成。
   - **CoCo**：`/semantic_studio` スキルに対話で作成を任せる。
   - **テンプレート**：雛形の YAML を自分で編集して作成。
3. いずれの方式でも、**セマンティックビュー定義の YAML ファイル**が生成される。
4. 内容を確認し、**「デプロイ」ボタン**でスキーマ上のセマンティックビューとして作成。

### エージェント（PREVIEW）の流れ

1. 「＋ 新規追加」→ **エージェント（PREVIEW）** を選択。
2. **CoCo が自動起動**し、`/semantic_studio ＋「エージェントの作成を手伝ってください」` というメッセージが自動送信される。
3. 対話に沿って、**エージェントの YAML/spec ファイル**が生成される。
   - **ツール（セマンティックビュー／検索サービス）を紐づける欄**がある。
   - **テスト用のチャット（プレイグラウンド）**で挙動を確認できる。
4. 内容を確認し、**「デプロイ」ボタン**でスキーマ上のエージェントとして作成（セマンティックビューと同じデプロイ操作）。

### `/semantic_studio` について

`/semantic_studio` は、**セマンティックビューとエージェントの両方を作成できる CoCo の統合スキル**。セマンティックビュー作成時の「3択の CoCo」と、エージェント作成時に自動送信される `/semantic_studio` は、同じスキルを指している。

### 他の作成方法との関係（早見表）

| 作成方法 | 起点 | 成果物 | オブジェクト化 |
| --- | --- | --- | --- |
| SQL | 任意の SQL 実行環境 | ― | `CREATE SEMANTIC VIEW` / `CREATE AGENT` を実行 |
| Cortex Analyst ウィザード | AI & ML » Cortex Analyst | ― | ウィザード内で直接作成 |
| CoCo（CLI/チャット） | CoCo | （内部で spec を生成） | CoCo がデプロイまで実施 |
| **Workspaces ＋新規追加（本章）** | **Projects » Workspaces** | **YAML 定義ファイル** | **「デプロイ」ボタン** |

> Workspaces 方式の利点は、定義が**ファイルとして残る**こと。Git 連携やバージョン管理と相性がよく、レビューや再利用がしやすい。

---

## 補足

- 環境で両方が「プレビュー」表示なのは、リージョンやロールアウト状況によるもの（セマンティックビューの Snowsight 作成自体は一部で一般提供に移行済み）。
- 画像の「セマンティックビュー（PREVIEW）／エージェント（PREVIEW）」は、Workspaces の「＋新規追加」メニューに新設されたファイルベースの作成経路（第4の方法）。
- **文書化の状況**：この Workspaces 経由の作成フローを正面から解説した専用の公式ドキュメントページは、2026年8月時点では確認できなかった。本まとめの「4章」の画面挙動は実環境での確認に基づく。裏づけとなる公式一次情報（YAML 仕様・エージェント spec・Workspaces のファイル操作）は下記「データソース」を参照。

---

## データソース（参考 URL）

**Snowflake 公式ドキュメント**

- セマンティックビューの概要
  <https://docs.snowflake.com/en/user-guide/views-semantic/overview>
- CREATE SEMANTIC VIEW（SQL リファレンス）
  <https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view>
- セマンティックビューのベストプラクティス（日本語）
  <https://docs.snowflake.com/ja/user-guide/views-semantic/best-practices-dev>
- Get started with Cortex Agents（作成手順・SQL 例）
  <https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-get-started>
- 2025 年の新機能リリースノート（プレビュー／GA の時系列）
  <https://docs.snowflake.com/en/release-notes/new-features-2025>

**Workspaces 関連（4章の裏づけ）**

- Workspaces 概要 — <https://docs.snowflake.com/en/user-guide/ui-snowsight/workspaces>
- Working with workspaces（ファイルの作成・編集・操作） — <https://docs.snowflake.com/en/user-guide/ui-snowsight/workspaces-working>
- CoCo in Snowsight（Workspaces 内アシスタント、`/` スキル） — <https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-snowsight>
- YAML specification for semantic views（セマンティックビュー YAML 仕様） — <https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec>
- Semantic View Editor（作成後のビジュアル編集） — <https://docs.snowflake.com/en/user-guide/views-semantic/editor>
- Create and manage agents（エージェント作成・管理、`FROM SPECIFICATION`） — <https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage>

**Snowflake 公式クイックスタート／ブログ**

- Getting Started with Cortex Agents with Snowflake CoCo CLI（本章 3 の元ネタ）
  <https://www.snowflake.com/en/developers/guides/getting-started-with-cortex-agents-with-coco/>
- Snowflake CoCo Foundations（`$semantic-view` / `$cortex-agent` の使用例）
  <https://www.snowflake.com/en/developers/guides/coco-foundations/>
- Build Agentic Analytics with Semantic Views
  <https://www.snowflake.com/en/developers/guides/snowflake-semantic-view-agentic-analytics/>
- Semantic View Autopilot の一般提供（自動生成）
  <https://www.snowflake.com/en/blog/semantic-view-autopilot/>

**技術記事（日本語・第三者）**

- Snowflake のセマンティックビューを AI で自動生成しよう（Zenn / Snowflake JP）
  <https://zenn.dev/snowflakejp/articles/ce732d628a9bee>
- Snowflake Intelligence を触ってみた（Zenn / NTT DATA）
  <https://zenn.dev/nttdata_tech/articles/f7465996741f34>
- Snowsight から簡単設定！データ分析向け AI エージェント（DevelopersIO）
  <https://dev.classmethod.jp/articles/snowflake-ai-agent-preview-data-analysis-from-snowsight/>

> 注：クイックスタートは「現状のまま提供され、継続的にメンテナンスされるものではない（最新の Snowflake 環境とは差異が生じうる）」旨が明記されている。実装時は必ず公式ドキュメントの最新版を確認すること。
