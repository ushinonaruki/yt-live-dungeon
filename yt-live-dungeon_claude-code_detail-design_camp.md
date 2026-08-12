# yt-live-dungeon 現行仕様ベース再構築・CAMP基盤 詳細設計／Claude Code実装指示

## 1. 文書の目的

本書は、Obsidianの現行仕様を正本として、`ushinonaruki/yt-live-dungeon` のヘッドレス版APIを再構築するための詳細設計である。

- アイテム定義と所持アイテムLv
- 精霊・加護・精霊アイテムプール
- 所持アイテムからのSpell・ステータス集計
- マスター撃破後のCAMP
- CAMP中の `@login` / `@logout` / `@select` / `@ready` / `@move`
- CAMP終了と次フロアへの遷移
- UnityおよびYouTube Live連携から独立した公開HTTP API
- 後から方式を差し替えられる敵AI境界
- Docker内で完結する開発・テスト・migration環境

Claude Codeは、Obsidianを変更せず、実装リポジトリだけを変更すること。

本書で「仕様」と明記する箇所はObsidianの決定事項である。「実装設計」と明記する箇所は、現行仕様を単純かつ効率的に実装するための構造である。

### 1.1 最優先原則

旧コードを捨てること自体が目的ではない。**旧仕様・旧構成を設計判断の基準にして、現行仕様なら不要な層・互換処理・条件分岐を増やすことを禁止する**。

新実装の判断基準は、次の順とする。

1. Obsidianの現行仕様
2. 本詳細設計
3. このゲームを最も単純に表現できる構成
4. 使用中フレームワークの一般的な慣習

旧コードは、利用中の言語・外部依存の把握、テスト観点の発見、削除対象の特定にだけ参照してよい。旧コードに存在するという理由だけで、旧状態、旧コマンド、旧DBカラム、旧API、旧クラス名、旧Service/Repository分割、旧テストを維持してはならない。

旧コードと現行仕様が衝突した場合は現行仕様を採用し、旧コード・旧テストを削除または置換する。旧挙動へ戻す互換処理は作らない。

---

## 2. 参照する正本

Obsidianの正本は次のリポジトリ配下にある。

```text
repository: ushinonaruki/obsidian-vault
root: ゲーム/YTL100ダンジョン/
```

最低限、実装開始時に以下を再読すること。

```text
ゲーム全体仕様.md
資料責務マップ.md
キャラクター/ステータス.md
アイテム/アイテム定義仕様.md
アイテム/アイテム成長.md
進行/キャンプ.md
ダンジョン/フロア補正.md
ダンジョン/マスターとミニオン.md
呪文/呪文定義仕様.md
呪文/呪文効果処理仕様.md
```

この詳細設計の作成時点で確認した主な仕様ファイルのSHAは以下。

| ファイル | SHA |
|---|---|
| `進行/キャンプ.md` | `781a95bc019f39d1819fb82ff694a2e934b52ce8` |
| `キャラクター/ステータス.md` | `9a0c7b668d6f3cba28f525dab5b46bd7dab59605` |
| `アイテム/アイテム定義仕様.md` | `7e7301d220c773b98649198835fa7138968428b4` |
| `アイテム/アイテム成長.md` | `731be7726b0ccb081f71015f2c8b103627bf5b53` |
| `ダンジョン/フロア補正.md` | `d3078a6ba129488f748c1ad34bf59420918991e6` |

実装開始時に正本が更新されていた場合は、正本を優先し、差異を完了報告へ明記すること。

---

## 3. 今回の実装範囲

### 3.1 対象

今回の完成条件は、新しいヘッドレスAPI上で次の一連の流れを成立させることである。

```text
マスター撃破
↓
CAMP開始
↓
共有候補A / Bを1度だけ生成
↓
既存参加者がキャンプ行動を選択
↓
@login / @logoutで次フロア参加者を変更
↓
全員READYまたは5分経過
↓
参加者0人ならRETIRE
参加者がいればMPを全回復して次フロア開始
```

### 3.2 対象外

以下は今回実装しない。

- 10種類の精霊の最終名称・モチーフ
- 加護・通常アイテム・Spellの最終バランス値
- Unityの画面レイアウト
- YouTube Liveとの実接続
- Weak / Chain / Break / Interceptの新規実装
- 敵AIの最終方式。ただし、後から方式を差し替えるための内部インターフェースは今回設計・実装する
- CAMP画面の具体的な表示文言
- 鍛冶対象0件時の最終演出
- 初回参加受付フローの未確定部分

精霊・加護・アイテムプールにはテスト用の仮データを使用してよい。ただし、仮データをドメインロジックへハードコードしないこと。

### 3.3 未確定部分の扱い

未確定部分を補うために旧仕様を流用しない。今回必要でないものは未実装のままとし、必要な仮データはseedまたはfixtureへ閉じ込める。

初回参加受付が未確定であるため、旧 `@join`、pending join、旧start-floorを新アーキテクチャへ移植しない。CAMP中の `@login` は、それらと独立した現行仕様として実装する。

---

## 4. 旧コードの扱い

旧実装は以下の旧構造を持つが、新実装の互換要件ではなく削除・置換対象である。

| 現行実装 | 現行仕様 |
|---|---|
| マスター撃破後に `RunState.RESULT` | マスター撃破後にCAMP |
| 所持枠1～9 | 所持上限8枠 |
| slot 1に「ひのきのフタ」固定 | 加護Lv1＋精霊プールアイテムLv1 |
| 所持アイテムにLvなし | 所持アイテムごとに `current_level` |
| STR～CHAと6属性 | HP・MP・10属性 |
| 冒険者HP 255 | 基礎最大HP 500 |
| MPなし | 基礎最大MP 100、次フロア時全回復 |
| 旧フロアHP倍率 | 1階ごとに基礎HPの10%加算 |
| `@join`予約は最大9人・超過持越し | CAMP中の現在参加者上限8人、待機列なし |
| Spell処理が `hinokinofuta` 専用 | アイテム所持によるSpell使用可能判定 |

新実装は `src/yt_live_dungeon/` を唯一のアプリケーションルートとして構築する。

禁止事項:

- 新コードから旧コードをimportする
- `legacy/`、`v2/`、`compat/` を恒久的に作る
- 旧カラムの有無で処理を分ける
- 旧API互換のための別経路を作る
- 旧機能を残すfeature flagを作る
- 旧テストを通すためだけに現行仕様を曲げる

実装途中に旧アプリを一時的に残す場合も、新アプリとはimport・DB・API routeを共有しない。新しい縦断機能が成立した時点でentrypointを新アプリへ切り替え、旧コードを削除する。Git履歴を旧コードの保存先とし、リポジトリ内に旧構成を保存しない。

---

## 5. 全体アーキテクチャとファイル責務

### 5.1 外部境界

```text
YouTube Live Adapter ─┐
                     ├─ HTTP API ─ Use Case ─ Game Domain ─ DB/Redis Adapter
Unity Client ────────┘
```

UnityとYouTube Live連携は、公開HTTP APIだけを使用する。外部クライアントからPostgreSQL、Redis、ORM model、query関数、Use Case、内部イベントテーブルへ直接アクセスさせない。

UnityにもYouTube Live Adapterにもゲームルールを持たせない。コメント構文、参加可否、対象解決、最大HP、属性値、使用可能Spell、CAMP終了条件、敵行動の合法性は、すべてバックエンドが決定する。

依存方向:

```text
api → feature use case → domain contract
infrastructure → domain contract
```

domainおよび純粋なゲーム計算からFastAPI、SQLAlchemy、Redis client、YouTube SDK、Unity固有型をimportしない。

### 5.2 推奨ディレクトリ構成

フレームワークの層ごとに巨大ファイルを置くのではなく、ゲーム機能ごとに責任を分ける。

```text
src/yt_live_dungeon/
  app.py
  config.py
  api/
    errors.py
    command_routes.py
    state_routes.py
    schemas/
      command.py
      run_state.py
  features/
    commands/
      parse.py
      dispatch.py
      result.py
    adventurer/
      stats.py
      login.py
      logout.py
      status.py
    inventory/
      acquire.py
      forge.py
      reorder.py
      query.py
    camp/
      start.py
      select_action.py
      ready.py
      finish.py
      state.py
    battle/
      engine.py
      action.py
      enemy_context.py
      enemy_policy.py
      enemy_policy_registry.py
      policies/
        random_policy.py
      finish_floor.py
    floor/
      scaling.py
      start.py
  domain/
    attributes.py
    errors.py
    ids.py
    clock.py
    random_source.py
  persistence/
    database.py
    transaction.py
    models/
      run.py
      adventurer.py
      inventory.py
      camp.py
      spell.py
      item.py
      spirit.py
      enemy.py
    queries/
      run.py
      adventurer.py
      inventory.py
      camp.py
      master_data.py
    seed/
      load.py
      development.yaml
  cache/
    redis.py
    command_cooldown.py
  migrations/
tests/
  unit/
  integration/
  api/
Dockerfile
compose.yaml
pyproject.toml
```

### 5.3 ファイル責務の規則

- `api/*_routes.py`: HTTP入出力変換だけ。ゲーム判定を置かない
- `features/<feature>/*.py`: 1つのUse Caseまたは1種類の純粋計算
- `persistence/models/*.py`: 永続化構造だけ。ゲーム処理を置かない
- `persistence/queries/*.py`: 対象機能に必要なDB読書きだけ。commitしない
- `persistence/transaction.py`: transaction開始・commit・rollbackだけ
- `domain/*.py`: 複数機能が共有する小さな型・契約だけ
- `cache/*.py`: Redis固有処理だけ

「1ファイル1関数」へ機械的に細分化する必要はないが、1ファイルが独立した複数のゲーム機能を持ってはならない。`services.py`、`models.py`、`utils.py`、`helpers.py` のように責任が名前から分からない巨大ファイルは作らない。

全テーブルへRepositoryクラスを機械的に作らない。簡潔な機能別query関数で足りる場合は、それを使う。共通化は同じ概念が実際に2か所以上で必要になってから行う。

### 5.4 公開API一覧

#### コマンド入力

```http
POST /api/v1/runs/{run_id}/commands
```

```json
{
  "source": "youtube_live",
  "source_message_id": "message-id",
  "viewer_id": "youtube-channel-id",
  "viewer_display_name": "viewer name",
  "raw_text": "@ready",
  "received_at": "2026-08-11T12:34:56Z"
}
```

YouTube Live AdapterはコメントをこのDTOへ変換するだけとする。YouTube SDK型をAPI内部へ持ち込まない。`source_message_id` により同一コメントの二重適用を防ぐ。

#### 状態取得

```http
GET /api/v1/runs/{run_id}/state
```

Unityが描画に必要な完全な現在状態を返す。Unity側でゲーム数値を再計算しない。

#### 差分イベント取得

```http
GET /api/v1/runs/{run_id}/events?after={sequence}
```

Unityが演出に使う順序付きイベントを返す。初期実装はポーリングでよい。将来WebSocketまたはSSEを追加しても同じイベントDTOを配信し、ゲーム処理を配信方式へ依存させない。

禁止する結合:

- YouTube Live Adapterが `@ready` 等を解釈し、別々の内部関数を呼ぶ
- UnityがDB rowやRedis pub/subを直接操作する
- 外部クライアントが内部Python packageを共有する
- ORM modelをそのままHTTPレスポンスにする

---

## 6. 敵AI差し替えインターフェース

### 6.1 分離する責任

敵AIの最終方式は未確定である。敵AIは「現在の合法な候補から、どの行動と対象を選ぶか」だけを担当する。

以下は敵AIへ持たせず、常にBattle Engineが担当する。

- 行動・対象の合法性生成と再検証
- ダメージ・Effect計算
- MP消費・クールダウン
- HP・MP・状態異常の更新
- ログ・イベント生成
- DB transactionと永続化

### 6.2 内部契約

`features/battle/enemy_policy.py` に、フレームワーク非依存のProtocolを置く。

```python
from typing import Protocol

class EnemyPolicy(Protocol):
    async def choose_action(
        self,
        context: EnemyDecisionContext,
    ) -> EnemyIntent:
        ...
```

`EnemyDecisionContext` は読み取り専用DTOとし、最低限次を含む。

```text
run_id
floor
turn
acting_enemy snapshot
ally snapshots
opponent snapshots
使用可能かつ合法なaction候補
各actionで選択可能なtarget候補
policy_config
```

ORM model、DB session、Redis client、FastAPI Requestは渡さない。

`EnemyIntent` は判断結果だけを表す。

```text
action_id
target_ids
optional metadata
```

### 6.3 実行順

```text
Battle Engineが合法なaction・target候補を生成
↓
EnemyDecisionContextをPolicyへ渡す
↓
PolicyがEnemyIntentを返す
↓
Battle EngineがIntentを再検証
↓
合法なら通常のaction解決処理で適用・永続化
```

Policyが存在しない、timeout、例外、不正なIntentの場合は、定義済みの安全なfallback Policyへ切り替える。AIの失敗で戦闘状態を部分更新しない。

### 6.4 Policy選択

敵マスターデータに次を持たせる。

```text
ai_policy_key
ai_policy_config JSONB
```

`enemy_policy_registry.py` がkeyを実装へ解決する。Battle EngineへPolicy別の `if` / `match` を追加しない。

初期実装:

```text
random_v1 → RandomEnemyPolicy
```

将来の追加例:

```text
weighted_v1 → WeightedEnemyPolicy
utility_v1  → UtilityEnemyPolicy
search_v1   → SearchEnemyPolicy
remote_v1   → RemoteEnemyPolicyAdapter
```

外部AIへ変更する場合も、Adapterが同じ `EnemyPolicy` を実装する。timeoutを必須にし、AI応答を `EnemyIntent` として検証する。外部AIからDBへ直接接続させず、認証情報はsecretまたは環境変数から渡す。

### 6.5 必須テスト

- 固定乱数で `random_v1` の結果を再現できる
- Policyへ合法候補だけが渡る
- 不正action・存在しないtargetはfallbackする
- Policy例外・timeoutで状態を部分更新しない
- Policyを差し替えても同じBattle Engineテストが通る
- PolicyからDB sessionへ到達できない

---

## 7. 用語と不変条件

### 7.1 参加者

「現在参加中の冒険者」は、次をすべて満たす冒険者とする。

```text
run_idが対象ランと一致
is_alive = true
is_participating = true
```

過去に `@logout` した生存冒険者のレコードは履歴として残してよいが、参加者数・READY待ち・次フロア生成には含めない。

`@logout`は現在のrunからの恒久的な離脱である。同じ`run_id`・`youtube_id`の冒険者が既に存在する場合、状態を問わず`@login`を拒否する。再参加は扱わない。

### 7.2 所持アイテム

- 1冒険者につき最大8件
- slotは1～8
- 同じ `item_id` を複数行で持たない
- 重複取得は既存行をLv+5
- 鍛冶は対象全件をLv+1
- 新規取得はLv1
- Lv上限なし

### 7.3 加護

加護は専用挙動を持たない通常アイテムである。

```text
1枠使用
Spellを1つ付与
固定10属性補正を持つ
Lv補正を持てる
属性一致時は通常どおり鍛冶対象
```

加護であることを示す専用フラグは、表示・データ管理上必要なら持ってよい。ただし、ステータス計算、Spell使用判定、鍛冶、Lv上昇に加護専用分岐を作らないこと。

### 7.4 CAMP

- 1ラン・1フロアにつきCAMPは高々1件
- 候補A / Bは異なる2アイテム
- 候補はCAMP開始時に1度だけ生成し、再抽選しない
- 既存の生存参加者だけがキャンプ行動を1回選べる
- CAMP中に `@login` した冒険者はキャンプ行動を選べない
- 正常成立したキャンプ行動は変更不可
- 所持上限で新規取得に失敗した場合だけ、選択未確定のまま再選択可能
- READY取消しなし
- 現在参加者全員READY、または開始から5分経過で終了
- 5分経過時は未READY参加者をREADYにしたうえで終了

---

## 8. 推奨データモデル

### 8.1 RunState

新スキーマの `RunState` は現行仕様で必要な状態だけを持つ。

```python
WAITING = "waiting"
BATTLE = "battle"
CAMP = "camp"
RETIRE = "retire"
GAME_OVER = "game_over"
```

旧 `RESULT`、`FLOOR_TRANSITION` など現行仕様にない状態は、新enum・新DB制約へ含めない。旧データ互換のためにも追加しない。

### 8.2 `spells`

新スキーマでは、旧カラム名へ寄せず次を定義する。

| カラム | 型 | 制約・意味 |
|---|---|---|
| `id` | Integer | PK |
| `command` | `String(64)` | コメントで使う一意なSpellキー |
| `display_name` | `String(128)` | 表示名 |
| `attribute` | `String(2)` | 10属性のいずれか |
| `mp_cost` | `Integer` | 0以上 |
| `target_rule` | `String(32)` | 対象解決ルールID |
| `effects` | `JSONB` | 1件以上、定義順保持 |
| `is_active` | Boolean | 使用可否 |

旧 `formula` など現行Spell定義で不要なカラムは新スキーマへ作らない。

### 8.3 `items`

新スキーマに次を定義する。

| カラム | 型 | 制約・意味 |
|---|---|---|
| `item_key` | `String(64)` | 一意な安定キー |
| `display_name` | `String(128)` | 表示名 |
| `attribute` | `String(2)` | 10属性のいずれか |
| `granted_spell_id` | FK | 付与Spell、nullable |
| `base_stat_modifiers` | `JSONB` | 固定補正 |
| `per_level_stat_modifiers` | `JSONB` | Lvごとの補正 |
| `break_effects` | `JSONB` | 記述順を保持する配列 |
| `is_active` | Boolean | 抽選可否 |

補正JSONのキーは実装内で以下へ統一する。

```text
max_hp
max_mp
rr
yr
yy
gy
gg
bg
bb
pb
pp
rp
```

値は整数とし、負数を許可する。未知キー、整数以外、ネスト構造はアプリケーション層で拒否する。

### 8.4 `spirits`

新規テーブル。

| カラム | 型 | 制約・意味 |
|---|---|---|
| `id` | Integer | PK |
| `spirit_key` | `String(64)` | 一意な安定キー |
| `display_name` | `String(128)` | 仮名可 |
| `representative_attribute` | `String(2)` | 10属性のいずれか |
| `blessing_item_id` | FK `items.id` | 一意、加護アイテム |
| `is_active` | Boolean | 抽選対象か |

### 8.5 `spirit_item_pool_entries`

新規テーブル。

| カラム | 型 | 制約・意味 |
|---|---|---|
| `spirit_id` | FK | 複合PK |
| `item_id` | FK | 複合PK |

各active精霊に2種類以上の通常アイテムが必要である。加護自身はプールへ登録しない。

重み付き抽選は現行仕様にないため、weightは追加しない。

### 8.6 `enemies`と敵Spell

敵もマスターデータとしてDB管理する。

| カラム | 型 | 制約・意味 |
|---|---|---|
| `id` | Integer | PK |
| `enemy_key` | String | 一意な安定キー |
| `display_name` | String | 表示名 |
| `base_max_hp` | Integer | 基礎最大HP |
| `base_max_mp` | Integer | 基礎最大MP |
| `base_attributes` | JSONB | 基礎10属性 |
| `ai_policy_key` | String | Policy registryのキー |
| `ai_policy_config` | JSONB | Policy固有設定 |
| `is_active` | Boolean | 使用可否 |

敵とSpellの多対多テーブルを設け、敵が使用できるSpellをDBで管理する。敵名、能力値、Spell、Policy設定をPythonコードへハードコードしない。

### 8.7 `run_adventurers`

今回追加・変更する主要項目。

| カラム | 型 | 初期値・意味 |
|---|---|---|
| `hp` | Integer | 新規参加時の最終最大HP |
| `mp` | Integer | 新規参加時の最終最大MP |
| `base_max_hp` | Integer | 500 |
| `base_max_mp` | Integer | 100 |
| `spirit_id` | FK | `@login`時に抽選した精霊 |
| `is_participating` | Boolean | 現在参加中か |
| `is_alive` | Boolean | 生存中か |

固定初期10属性値は `run_adventurers` へ直接保存しない。加護アイテムの `base_stat_modifiers` から得る。

STR～CHA・旧6属性など現行仕様にないカラムは新スキーマへ作らない。既存DBを保持する要件が別途示されない限り、互換カラムも作らない。

### 8.8 `run_adventurer_items`

| カラム | 型 | 制約・意味 |
|---|---|---|
| `run_adventurer_id` | FK | 冒険者 |
| `item_id` | FK | アイテム |
| `slot` | Integer | 1～8 |
| `current_level` | Integer | 1以上、初期1 |
| `acquired_floor` | Integer | 取得フロア |
| `acquired_at` | DateTime | 取得時刻 |

追加制約:

```text
UNIQUE(run_adventurer_id, slot)
UNIQUE(run_adventurer_id, item_id)
CHECK(slot BETWEEN 1 AND 8)
CHECK(current_level >= 1)
```

### 8.9 `run_camps`

新規テーブル。候補と期限を永続化し、再起動してもCAMPを復元できるようにする。

| カラム | 型 | 制約・意味 |
|---|---|---|
| `id` | UUID | PK |
| `run_id` | FK | 対象ラン |
| `floor` | Integer | 突破したフロア |
| `spirit_id` | FK | このフロアに対応する精霊 |
| `candidate_a_item_id` | FK | 候補A |
| `candidate_b_item_id` | FK | 候補B |
| `started_at` | DateTime | UTC |
| `deadline_at` | DateTime | `started_at + 5分` |
| `ended_at` | DateTime nullable | 終了時刻 |

制約:

```text
UNIQUE(run_id, floor)
candidate_a_item_id != candidate_b_item_id
deadline_at > started_at
```

### 8.10 `run_camp_members`

新規テーブル。READYとキャンプ行動はCAMP単位で保持する。

| カラム | 型 | 意味 |
|---|---|---|
| `camp_id` | FK | 複合PK |
| `run_adventurer_id` | FK | 複合PK |
| `can_select_action` | Boolean | CAMP開始時の生存参加者だけtrue |
| `selected_action` | String nullable | `rest` / `candidate_a` / `candidate_b` / `forge` |
| `selected_at` | DateTime nullable | 正常成立時刻 |
| `ready_at` | DateTime nullable | READY時刻。非nullならREADY |
| `left_at` | DateTime nullable | CAMP中のlogout時刻 |

`@login`で作成したメンバーは `can_select_action=false` とする。`@logout` で行を削除せず `left_at` を設定する。

### 8.11 `run_events`

Unity向け差分イベントの正本として、`run_id`、単調増加する `sequence`、`event_type`、`body JSONB`、`created_at` を保存する。

```text
UNIQUE(run_id, sequence)
```

### 8.12 `processed_commands`

`source`、`source_message_id`、`run_id`、`viewer_id`、`raw_text`、`processed`、`reason`、`result JSONB`、受信・処理時刻を保存する。

```text
UNIQUE(source, source_message_id)
```

YouTube Live側の再送やAPI retryで同じコメントを二重適用しない。

---

## 9. ステータス集計

### 9.1 純粋関数

DBアクセスを含まない `features/adventurer/stats.py` を作る。

入力:

```text
base_max_hp
base_max_mp
所持アイテム定義
各所持アイテムのcurrent_level
```

アイテム1件・ステータス1種の補正:

```text
item_modifier
= base_stat_modifier
 + per_level_stat_modifier * current_level
```

最終値:

```text
max_hp = base_max_hp + 全アイテムのmax_hp補正合計
max_mp = base_max_mp + 全アイテムのmax_mp補正合計
各属性値 = 全アイテムの該当属性補正合計
```

属性値は正負無制限。アイテム補正によって最大HP・最大MPが0以下になり得る場合の下限は仕様未確定であるため、今回の仮データでは0以下にならない値だけを使う。勝手に下限を追加しないこと。

### 9.2 現在HP・MPの補正後処理

アイテム取得・Lv上昇後に最大値が変化しても、現在値は増加させない。

```text
hp = min(変更前hp, 新max_hp)
mp = min(変更前mp, 新max_mp)
```

### 9.3 使用可能Spell

```text
使用可能Spell
= 所持アイテムが参照するSpellの集合
```

加護だけを特別扱いしない。同一Spellを複数アイテムが付与しても、表示・使用判定では1件として扱う。

---

## 10. 精霊抽選と初期付与

### 10.1 抽選対象

`spirits.is_active=true` の全精霊から一様ランダムに1体選ぶ。

乱数生成器はサービスへ注入できる形にし、テストでは固定する。

### 10.2 `@login`成立時の同一トランザクション

```text
runをFOR UPDATEでロック
↓
RunState.CAMPか確認
↓
同じrun_id・youtube_idの冒険者が存在するか確認
↓
存在すればlogin拒否
↓
現在参加者数を再計算
↓
8人未満なら精霊を抽選
↓
冒険者を新規生成する
↓
加護をLv1・空きslotへ付与
↓
精霊プールから1件を抽選しLv1・空きslotへ付与
↓
run_camp_membersをcan_select_action=falseで作成
↓
commit
```

新規冒険者は2アイテムから開始するため、8枠制限内で必ず成立する。

`@login`が生成するのは新規冒険者だけである。既存冒険者を再利用・再参加させる分岐は持たない。同じ`run_id`・`youtube_id`の冒険者が既に存在する場合、現在参加中・`@logout`済み・戦死済みのいずれであっても、状態を区別せず同一のreasonでloginを拒否する。拒否は精霊抽選・アイテム付与・`run_camp_members`作成より前に行い、乱数を消費せず、既存の冒険者・所持品・`left_at`を一切変更しない。

### 10.3 満員時

参加者8人なら拒否して終了する。

- 待機列・参加予約へ保存しない
- 待機列を作らない
- 後から自動参加させない
- 乱数を消費しない

同時loginはrun行ロック後の処理順で最大8人まで成立させる。

---

## 11. CAMP開始

### 11.1 呼出点

Battle Engineがマスター撃破を確定するUse Case内で、`features/camp/start.py` のCAMP開始処理を呼ぶ。旧 `BattleService`、`RunState.RESULT`、旧 `CampService` は前提にしない。

### 11.2 同一トランザクションで行う処理

```text
マスター撃破を永続化
↓
対象フロア・精霊のアイテムプールを取得
↓
異なる2件を一様ランダムに抽選
↓
run_campsを作成
↓
その時点の生存中かつ参加中の冒険者をrun_camp_membersへ登録
↓
各メンバーをcan_select_action=true、READY未設定とする
↓
run.state = CAMP
↓
camp_startedログ
↓
commit
```

プールが2件未満の場合はデータ不整合としてCAMPを部分作成しない。409相当の業務エラーではなく、サーバー設定エラーとしてログへ残す。

### 11.3 ミニオン

マスター撃破時点で生存ミニオンがいてもフロア突破する。CAMP開始後は前フロアの敵を戦闘対象へ出さない。

---

## 12. CAMPコマンド

### 12.1 共通前処理

CAMPコマンドは次の順で処理する。

```text
runをFOR UPDATEで取得
↓
CAMP期限を評価
↓
期限超過ならCAMP終了処理を先に実行
↓
まだRunState.CAMPならコマンド固有処理
```

期限到達と同時に届いたコマンドは、バックエンド受信時刻が `deadline_at` 以上なら時間切れを優先して拒否する。

### 12.2 `@select 1` 休憩

対象条件:

```text
現在参加中
run_camp_members.can_select_action = true
selected_action is null
```

処理:

```text
hp = min(max_hp, hp + 100)
selected_action = rest
selected_at = now
```

### 12.3 `@select 2` / `@select 3` 候補取得

候補A/Bの `item_id` を取得し、以下を分岐する。

```text
同じitem_idを所持
→ current_level += 5
→ selected_action確定

未所持かつ所持数 < 8
→ 最小空きslotへLv1で追加
→ selected_action確定

未所持かつ所持数 = 8
→ 何も変更しない
→ selected_actionはnullのまま
→ processed=false, reason=inventory_full
```

Lv変化後はステータスを再計算し、現在HP・MPを新最大値でclampする。

### 12.4 `@select 4` 鍛冶

このCAMPの精霊代表属性と同じ `items.attribute` を持つ全所持アイテムをLv+1する。

加護も同じ検索条件へ含める。対象0件でもコマンド自体は正常成立し、`selected_action=forge` を確定する。表示文言だけ未確定としてログに `affected_count=0` を残す。

### 12.5 `@ready`

対象は現在参加中のCAMPメンバー。

- `ready_at is null` なら現在時刻を設定
- すでにREADYなら状態を変えずduplicateとして返す
- READY取消しコマンドは作らない
- キャンプ行動未選択でもREADY可能
- READY成立後、現在参加者全員がREADYか同じトランザクション内で判定
- 全員READYなら即座にCAMP終了

### 12.6 `@logout`

対象が現在参加中なら即時に次を行う。

```text
is_participating = false
run_camp_members.left_at = now
```

アイテム・Lv・HP・MP・精霊情報は削除しない。

logout後の参加者集合で全員READYになった場合は、同じトランザクション内でCAMPを終了する。参加者0人になった場合もCAMP終了条件の「全員READY」を満たすものとして即時終了し、RETIREへ遷移させる。

### 12.7 `@move`

引数は現在所持する全slot番号を、希望順に連結したASCII数字列とする。

例:

```text
現在5件: slot 1,2,3,4,5
入力: @move 31425
結果: 旧3,旧1,旧4,旧2,旧5の順で新slot 1～5
```

検証:

```text
文字数 = 所持数
使用文字 = 現在存在するslot番号の集合
重複なし
欠落なし
余分な引数なし
```

更新時は一時slotへ退避してUnique制約違反を避けるか、単一SQLのCASE更新を使う。検証失敗時は1件も更新しない。

### 12.8 `@status` / `@bag` / Spellコマンド

今回の最低限のレスポンスは構造化データとする。

`@status`:

```text
hp / max_hp
mp / max_mp
10属性最終値
spirit display_name
is_ready
```

`@bag`:

```text
slot
item_id
display_name
attribute
current_level
最終補正
付与Spell
```

CAMP中に所持Spellコマンドが入力された場合は発動せず、Spell詳細を返す。MP消費・クールダウン設定・Effect実行は行わない。

---

## 13. CAMP終了

### 13.1 終了処理の冪等性

`run_camps.ended_at` が非nullなら何もしない。run行とcamp行をロックし、同じCAMPを二重終了させない。

### 13.2 時間切れ

`now >= deadline_at` の場合、現在参加中かつ未READYのメンバーすべてへ `ready_at=now` を設定する。

本人READYと強制READYを将来区別できるよう、実装上は任意で `ready_reason = manual | timeout` を持たせてよい。ゲーム上のREADY判定は同一に扱う。

### 13.3 参加者0人

```text
camp.ended_at = now
run.state = RETIRE
run.ended_at = now
```

敵生成・MP回復・次フロア開始は行わない。

### 13.4 参加者あり

現在参加中の全冒険者について、所持品込みの最大MPを再計算し、現在MPを最大MPへ設定する。HPは変更しない。

その後、`features/floor/start.py` の現行仕様用Use Caseで、参加中冒険者を引き継いで次フロアを作る。旧 `FloorService` やpending join処理を分割・再利用しない。

```text
camp.ended_at = now
↓
参加中冒険者MP全回復
↓
current_floor + 1の敵を生成
↓
run.state = BATTLE
↓
floor_startログ
```

一連の処理は同一トランザクションとする。敵生成に失敗した場合、CAMPだけ終了済みにしない。

---

## 14. フロア補正

敵生成の純粋関数を現行仕様へ変更する。

```text
敵最大HP
= floor(
    基礎最大HP
    * (1 + 0.25 * (フロア数 - 1))
  )
```

敵の各10属性値:

```text
敵の各10属性値
= 各基礎属性値
 + 5 * (フロア数 - 1)
```

フロア補正で増加させるのは最大HPと10属性値だけであり、参加人数による補正はない。

最大MP、MP回復速度、Spell基本威力、MP消費、Weak、Break、Chainにはフロア補正を掛けない。

---

## 15. コマンドパーサー

`ParsedCommand` を次へ拡張する。

```text
login
logout
select(value: 1..4)
ready
status
bag
move(order: str)
spell(command, raw_argument)
unknown
```

構文エラーと状態エラーを分ける。

推奨reason code:

```text
invalid_syntax
not_in_camp
not_in_battle
not_joined
already_joined
dead_in_this_run
party_full
action_not_available
action_already_selected
inventory_full
already_ready
unknown_spell
spell_not_unlocked
camp_ended
```

旧 `yes` / `no` の新規処理は追加しない。

---

## 16. API状態表現

`GET /api/v1/runs/{run_id}/state` にCAMP中だけ次を追加する。

```json
{
  "camp": {
    "floor": 1,
    "started_at": "...",
    "deadline_at": "...",
    "candidate_a": {"item_id": "...", "display_name": "..."},
    "candidate_b": {"item_id": "...", "display_name": "..."},
    "members": [
      {
        "run_adventurer_id": "...",
        "can_select_action": true,
        "selected_action": null,
        "is_ready": false,
        "is_participating": true
      }
    ]
  }
}
```

候補は共有なので、冒険者ごとに複製しない。

状態取得時にもCAMP期限を評価する。現在のヘッドレス版では、コマンド受付または状態ポーリングで期限到達を検知して終了処理を行う。常駐スケジューラ導入は別フェーズとする。

---

## 17. トランザクションと競合制御

以下では必ずrun行を `SELECT ... FOR UPDATE` でロックする。

- CAMP開始
- `@login`
- `@logout`
- `@select`
- `@ready`
- CAMP時間切れ終了

アイテム取得・Lv上昇・並べ替えでは、対象冒険者の所持行もロックする。

transaction境界はUse Caseの外周に1回だけ置く。query関数や純粋計算はcommitしない。旧Service/Repository方針の維持を目的にせず、この規則を新構成で直接実装する。

外部コメントの重複配信に備え、`processed_commands` の一意制約によって同じ入力を二重適用しない。

---

## 18. ログイベント

最低限、次を記録する。

| event_type | 主なbody |
|---|---|
| `camp_started` | floor, spirit, candidate_a, candidate_b, deadline_at |
| `camp_action_selected` | adventurer, action, item, level_before/after, affected_count |
| `camp_action_failed` | adventurer, action, reason |
| `adventurer_login` | adventurer, spirit, blessing_item, pool_item |
| `adventurer_logout` | adventurer |
| `adventurer_ready` | adventurer, reason |
| `inventory_moved` | adventurer, old_order, new_order |
| `camp_ended` | floor, reason, participant_count |
| `run_retired` | floor |

表示文言はログへ固定せず、構造化bodyを正とする。

---

## 19. Docker設計

### 19.1 Compose services

```text
api       FastAPIアプリ
postgres  PostgreSQL
redis     Redis
```

常駐workerが実際に必要になるまでは追加しない。CAMP期限はコマンド受信時と状態取得時に評価する。

### 19.2 Docker内で行う操作

READMEにはDocker経由の手順だけを記載する。

```bash
docker compose up --build
docker compose run --rm api pytest
docker compose run --rm api ruff check .
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m yt_live_dungeon.persistence.seed.load development
```

ホストに必須とするものはGit、Docker EngineまたはDocker Desktop、Docker Composeだけとする。Python、パッケージマネージャー、PostgreSQL、Redis、Node.jsをホストへ導入させない。

### 19.3 Imageと設定

- lockfileを使用する
- multi-stage buildを使用する
- production stageへtest/lint依存を含めない
- rootユーザーでAPIを実行しない
- source mountがなくてもproduction imageが起動する
- `.venv`、cache、DBデータをリポジトリへ生成しない
- `config.py` が環境変数を一度だけ読み、型付き設定へ変換する
- 各機能が直接 `os.environ` を読まない
- secretをcompose.yaml、seed、ログ、Gitへ保存しない

---

## 20. テスト用仮データ

最終コンテンツと混同しないよう、テストfixtureまたは明示的なdevelopment seedへ置く。

最低限:

```text
active精霊 2体以上
各精霊の代表属性
各精霊の加護 1件
各加護が付与するSpell 1件
各加護の固定10属性補正
各精霊の通常アイテムプール 2件以上
```

仮の名称・数値はテストの期待値を簡単に計算できるものにする。最終仕様としてREADMEへ記載しない。

---

## 21. 必須テスト

### 21.1 純粋関数

- Lv1で `base + per_level * 1`
- 負補正を正しく合算
- 複数アイテムを全ステータスへ合算
- 同一Spellを集合として重複排除
- HPフロア補正の1F・10F・100F
- 属性補正の1F・10F・100F（参加人数による補正は行わない）
- アイテム候補が常に異なる2件
- 固定乱数で敵 `random_v1` の結果を再現
- EnemyPolicyへ合法候補だけが渡る
- 不正Intent、例外、timeoutでfallbackし、状態を部分更新しない

### 21.2 inventory

- 新規取得はLv1・最小空きslot
- 重複取得は枠を増やさずLv+5
- 8件時の未所持取得は失敗し、選択未確定
- 8件時でも重複取得は成功
- 鍛冶で属性一致全件がLv+1
- 加護も鍛冶対象
- `@move`正常系
- 重複・欠落・存在しないslotの `@move` は全体無効

### 21.3 login/logout

- CAMP以外のlogin拒否
- 7人からのlogin成功、8人からのlogin拒否
- 同時loginでも9人にならない
- 待機列へ保存しない
- 現在参加中の同一ユーザーの重複login拒否
- `@logout`済みユーザーの同一runへのlogin拒否
- 戦死済みユーザーの同一runへのlogin拒否
- 上記いずれの拒否でも乱数を消費せず、冒険者・所持品・`left_at`・CAMPメンバー・eventを変化させない
- login冒険者は `can_select_action=false`
- logout直後に参加枠が空き、その枠へは別の新規ユーザーがloginできる

### 21.4 CAMP

- マスター撃破で `CAMP` へ遷移
- ミニオン撃破では遷移しない
- 候補を1回だけ生成
- CAMP開始時メンバーだけ `can_select_action=true`
- 休憩は最大HPを超えない
- 正常選択後の再選択拒否
- inventory_full時だけ再選択可能
- 行動未選択でもREADY可能
- 全員READYで即終了
- logoutでREADY待ち対象から外れる
- 参加者0人でRETIRE
- 5分未満では終了しない
- 5分ちょうどで未READYを強制READYにして終了
- 二重終了しない
- 次フロアでMP全回復・HP引継ぎ

### 21.5 API

- CAMP stateに共有候補・期限・メンバー状態が出る
- `@status` がアイテム込み最終値を返す
- `@bag` がslot順・Lv・Spellを返す
- CAMP中のSpell入力は詳細表示のみでMPを消費しない
- `source_message_id` が同じコマンドを二重適用しない
- Unity・YouTube固有SDKへ依存しない
- ORM modelをHTTPへ露出しない
- `/events?after=` が単調増加sequenceで差分を返す

### 21.6 Docker・DB

- migrationを空DBへ適用できる
- seedを再実行しても重複しない
- testはDocker内PostgreSQLを使い、SQLiteで差異を隠さない
- host Pythonなしでtest・lint・migration・seedを実行できる
- 新アプリから旧コードへのimportがない

---

## 22. コミット分割

### Commit 1: 新アプリ骨格とDocker

目的:

```text
旧構成に依存しない新しい実行基盤を作る
```

やること:

- `src/yt_live_dungeon/` の最小骨格
- FastAPI health endpoint
- 型付きconfig
- Dockerfile / compose.yaml
- PostgreSQL / Redis接続確認
- pytest / ruffをDocker内で実行
- 新アプリが旧コードをimportしていないことを確認

やらないこと:

- ゲーム機能
- 旧API互換
- 旧コードの新ディレクトリへのコピー

想定コミット:

```text
build: create clean headless api foundation
```

### Commit 2: 現行仕様のDB基盤とseed

目的:

```text
現行仕様だけを表すmaster・runtime schemaを作る
```

やること:

- migration
- Spell・item・spirit・enemy・enemy policy設定のmaster table
- run・adventurer・inventory・camp・event・processed commandのruntime table
- development/test seed
- DB制約とseed冪等テスト

やらないこと:

- 旧カラム・旧状態
- 旧DB移行互換
- ゲームUse Case

想定コミット:

```text
feat: add current-spec game data model
```

### Commit 3: アイテム・ステータス機能

目的:

```text
加護を含む全アイテムを同じ規則で集計・成長する
```

やること:

- 純粋なステータス集計
- 使用可能Spell集合
- acquire / forge / reorder
- HP/MP clamp
- unit tests

やらないこと:

- コマンド配線
- CAMP
- Spell Effect汎用化

想定コミット:

```text
feat: implement item-driven adventurer stats
```

### Commit 4: 公開コマンド・状態API

目的:

```text
UnityとYouTube Live Adapterから疎結合に利用できるAPI契約を作る
```

やること:

- command DTO / parser / dispatcher骨格
- `source_message_id` の冪等性
- run state DTO
- run events API
- OpenAPI test
- Unity・YouTube固有SDK依存がないことを確認

やらないこと:

- 個別ゲームコマンドのUse Case
- Unity / YouTube Live実接続

想定コミット:

```text
feat: expose decoupled command and state APIs
```

### Commit 5: CAMP開始・行動

目的:

```text
マスター撃破からCAMPを開始し、既存参加者の行動を実装する
```

やること:

- マスター撃破からCAMP開始
- 候補2件抽選
- `@select 1..4`
- `@move`
- `@status` / `@bag`
- CAMP中Spell詳細
- events / tests

やらないこと:

- UI文言確定

想定コミット:

```text
feat: implement camp start and actions
```

### Commit 6: CAMP参加・終了

目的:

```text
CAMP中の参加変更と終了・次フロア遷移を実装する
```

やること:

- login / logout
- 8人上限と排他
- READY判定
- 強制READY
- 冪等なCAMP終了
- MP全回復・HP引継ぎ
- 参加者0人RETIRE
- 現行仕様用の次フロア開始Use Case
- state取得時の期限評価
- tests

想定コミット:

```text
feat: complete camp participation and transition
```

### Commit 7: 敵AI Policy境界

目的:

```text
敵AI方式をBattle Engineや公開APIから独立させる
```

やること:

- `EnemyDecisionContext` / `EnemyIntent`
- `EnemyPolicy` Protocol
- policy registry
- `random_v1`
- Battle EngineによるIntent再検証
- fallback
- 敵master dataのpolicy設定
- unit / integration tests

やらないこと:

- 最終的なAI方式
- 外部AIサービス

想定コミット:

```text
feat: add replaceable enemy decision policy
```

### Commit 8: 新アプリへの切替と旧コード削除

目的:

```text
新アプリを唯一の実装として完成させ、旧構成を残さない
```

やること:

- entrypointを新アプリだけへ切替
- 旧API・旧model・旧service・旧testを削除
- `legacy` / `compat` / `v2`を残さない
- READMEをDocker・公開API・現行仕様へ同期
- 全test / lint / migration

想定コミット:

```text
refactor: replace obsolete game implementation
```

---

## 23. Claude Codeへの実行指示

以下をClaude Codeへの依頼本文として使用する。

```text
ushinonaruki/yt-live-dungeon を変更してください。

正本は ushinonaruki/obsidian-vault の
ゲーム/YTL100ダンジョン/ 配下です。
実装開始前に、詳細設計書の「参照する正本」に列挙されたMarkdownを読み直してください。
Obsidian側は変更しないでください。

添付の「yt-live-dungeon 現行仕様ベース再構築・CAMP基盤 詳細設計／Claude Code実装指示」に従い、
まず Commit 1 だけを実装してください。

最優先要件:
- 旧コードの構造・DB・API・命名・テストを新設計の基準にしない
- 旧コードは環境把握、テスト観点発見、削除対象特定にだけ参照する
- 現行仕様から最も単純な構成を引き直す
- 新コードから旧コードをimportしない
- legacy、v2、compat、旧仕様互換分岐を恒久的に作らない
- ゲーム機能単位で責任が分かるファイルへ分ける
- 巨大なservices.py、models.py、utils.pyを作らない
- UnityとYouTube Live連携は公開HTTP API以外へ接続させない
- 精霊、アイテム、Spell、敵、敵AI設定などのデータはDB管理する
- test、lint、migration、seedをDocker Compose内で完結させる
- ホストへのPython、PostgreSQL、Redis等の導入を要求しない
- 仕様にないゲームルールを追加しない
- 1コミットにCommit 1以外の振る舞いを混ぜない
- 既存テストの失敗が新仕様との衝突なら、勝手に仕様を戻さず理由を報告する

敵AIについて:
- 最終方式は未確定
- Battle EngineとEnemyPolicyを分離する
- Policyは読み取り専用ContextからIntentを選ぶだけにする
- 合法判定、Effect、MP消費、状態更新、永続化はBattle Engineが行う
- Policy方式を変えてもBattle Engineや公開APIを変更しない
- DBのai_policy_keyとconfigでPolicyを選択する
- Battle EngineへPolicy別分岐を追加しない

Commit 1の完了条件:
- src/yt_live_dungeon を唯一の新アプリルートとして作成
- FastAPI health endpointがDocker内で起動
- PostgreSQLとRedisへDocker内部名で接続
- pytestとruffがDocker内で成功
- 新アプリが旧コードをimportしていない
- ゲーム機能や旧API互換はまだ実装しない

完了報告に必ず含めるもの:
1. 変更ファイル一覧と各ファイルの単一責任
2. 新コードが旧構成へ依存していない根拠
3. Docker内で実行したコマンドと結果
4. ホストに追加で必要なソフトウェア
5. 詳細設計から変更した点と理由
6. 未実装として残した次コミットの範囲
7. 想定コミットメッセージ

コミットはまだ行わず、差分とテスト結果を提示してください。
```

Commit 1のレビュー完了後、依頼文中の `Commit 1` を次の番号へ変更して、1コミットずつ進める。

---

## 24. 実装中に判断を止める条件

以下に遭遇した場合は、Claude Codeが独断で仕様を追加せず報告する。

- 正本の更新によって本詳細設計と矛盾した
- 最大HP・最大MPが0以下になる実データが必要になった
- 精霊プール、マスター、敵の対応関係が現行仕様から決められない
- 初回参加受付の未確定部分が対象Commitを妨げる
- 5分期限評価に常駐ワーカーが必須になった
- 外部AI Policyのtimeout・fallbackが実際の仕様判断を必要とする
- 既存DBデータを保持する必要があるが、移行仕様がない
- 旧API互換を残さないと外部運用へ影響することが判明した

次は停止理由にならない。

- 旧テストが旧仕様を期待して失敗する
- 旧クラスや旧APIを削除すると旧コードだけが動かなくなる
- 新構成が旧ディレクトリ構造と一致しない

これらは旧仕様へ戻す理由にせず、対象Commitの範囲内で旧テスト・旧コードを置換または削除する。
