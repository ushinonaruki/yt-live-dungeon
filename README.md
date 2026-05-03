# yt-live-dungeon

YouTube Live コメントを使ったリアルタイムダンジョンゲームのバックエンド。

## 開発段階

| フェーズ | 内容 | 状態 |
| -------- | ---- | ---- |
| Phase 1 | 基盤構築（Docker, FastAPI, Alembic） | ✅ |
| Phase 2 | 最小 API（ラン作成・状態取得・ログ取得） | ✅ |
| Phase 3 | `@join` 処理・参加予約 | ✅ |
| Phase 4 | フロア開始（冒険者生成・敵生成） | ✅ |
| Phase 5 | 最小戦闘（`@hinokinofuta` 処理・ダメージ計算） | 🔜 |
| Phase 6 | リザルト（`@yes` / `@no`・アイテム選択） | 🔜 |
| Phase 7 | 状態確認（`@status`） | 🔜 |
| Phase 8 | YouTube / Unity 接続 | 🔜 |

## ディレクトリ構成

```text
.
├── compose.yaml                  # Docker Compose（postgres + redis）
├── .env                          # 環境変数（Docker + Python 共通）
├── .env.example                  # 環境変数テンプレート
│
├── backend/
│   ├── pyproject.toml            # 依存パッケージ定義
│   └── app/
│       ├── main.py               # FastAPI エントリーポイント、/health
│       ├── config.py             # 環境変数管理
│       ├── db/                   # DB セッション
│       ├── redis/                # Redis クライアント（将来用）
│       ├── models/               # SQLAlchemy ORM モデル
│       ├── schemas/              # Pydantic 入出力スキーマ
│       ├── repositories/         # DB アクセス層（flush のみ）
│       ├── services/             # ビジネスロジック層（commit はここ）
│       ├── core/                 # 純粋関数（DB 不使用）
│       └── api/routes/           # REST API エンドポイント
│
├── database/
│   ├── alembic.ini               # Alembic 設定
│   └── migrations/
│       ├── env.py
│       └── versions/
│           ├── 0001_initial_schema.py             # 全テーブル作成
│           ├── 0002_seed_data.py                  # 初期データ投入
│           ├── 0003_add_nickname_word_unique.py    # nickname_words.word に UNIQUE 制約
│           ├── 0004_add_enemy_role.py              # run_enemies に role カラム追加
│           ├── 0005_spec_alignment.py              # pending_joins に oshi_name、run_adventurers に faith を追加
│           ├── 0006_drop_attr_indigo.py            # run_adventurers から attr_indigo を削除
│           └── 0007_drop_barrier_columns.py        # enemies / run_enemies から barrier 系カラムを削除
│
└── docker/
    ├── postgres/Dockerfile        # PostgreSQL 16
    └── redis/Dockerfile           # Redis 7 Alpine
```

## セットアップ

### 1. 環境変数

```bash
cp .env.example .env
```

### 2. Docker 起動

```bash
docker compose up -d
```

### 3. 依存パッケージインストール

```bash
cd backend
uv sync
```

### 4. マイグレーション実行

`backend/` ディレクトリから実行する（`uv` の venv と `app.*` モジュールを解決するため）。

```bash
cd backend
uv run alembic -c ../database/alembic.ini upgrade head
```

#### その他の Alembic コマンド

```bash
# 現在のリビジョン確認
uv run alembic -c ../database/alembic.ini current

# 履歴確認
uv run alembic -c ../database/alembic.ini history

# ロールバック
uv run alembic -c ../database/alembic.ini downgrade -1

# 新しいマイグレーション生成
uv run alembic -c ../database/alembic.ini revision --autogenerate -m "description"
```

### 5. 開発サーバー起動

```bash
cd backend
uv run uvicorn app.main:app --reload
```

## API

| Method | Path | 概要 |
| ------ | ---- | ---- |
| GET | `/health` | ヘルスチェック |
| POST | `/runs` | ラン作成 |
| GET | `/runs/{run_id}` | ラン取得 |
| GET | `/runs/{run_id}/state` | ランの現在状態取得（冒険者・敵を含む） |
| GET | `/runs/{run_id}/logs` | ランのログ取得 |
| POST | `/runs/{run_id}/commands` | コマンド受付（`@join` など） |
| POST | `/runs/{run_id}/start-floor` | フロア開始（冒険者生成・敵生成） |

## 動作確認

Swagger UI を開く。

```text
http://localhost:8000/docs
```

### フロア開始までの流れ

1. `POST /runs` でランを作成
2. `POST /runs/{run_id}/commands` に `@join` を複数ユーザーで送信
3. `GET /runs/{run_id}/state` で `pending_join_count` が増えていることを確認
4. `POST /runs/{run_id}/start-floor` でフロアを開始
5. `GET /runs/{run_id}/state` で `adventurers` と `enemies` が生成されたことを確認
6. `GET /runs/{run_id}/logs` で各種ログを確認

`POST /runs/{run_id}/commands` の例。

```json
{
  "source": "manual",
  "external_message_id": "debug-join-001",
  "youtube_id": "yt-user-001",
  "display_name": "テスト太郎",
  "text": "@join"
}
```

推し名を指定する場合。

```json
{
  "source": "manual",
  "external_message_id": "debug-join-002",
  "youtube_id": "yt-user-002",
  "display_name": "テスト花子",
  "text": "@join 推し名"
}
```

## フロア開始の仕様

### 冒険者

- 参加予約者（最大 9 名）を冒険者に変換する
- 全員 HP 255 固定
- STR / DEX / CON / INT / WIS / CHA をランダム生成（各 1〜20、合計 72）
- 属性値（赤・青・黄・緑・紫・橙）は初期値 0
- 信仰値（faith）は `@join 推し名` で指定した推し名に紐づく登録値で決定（未指定・未登録は 0）
- スロット 1 には「ひのきのフタ」が初期配布される（`@hinokinofuta` 呪文が使用可能）

### 敵（マスター＋ミニオン）

- **マスター**: 必ず 1 体出現。撃破するとフロア突破
- **ミニオン**: 0〜8 体出現。マスターの取り巻き・護衛役
- 合計最大 9 体
- HP はテンプレートの `base_hp` に階層倍率を乗じて決定（10 階ごとに ×1.5、端数切り捨て）

### ログ

| イベント | 内容 |
| -------- | ---- |
| `floor_start` | 冒険者・敵の一覧（各敵に `run_enemy_id` / `position` / `role` を含む） |
| `enemy_greeting` | マスターのあいさつ |
| `minion_deployed` | ミニオンが 1 体以上いる場合、一括で出力（各ミニオンに `run_enemy_id` / `position` / `role` を含む） |

### ゲーム状態

| 状態 | 説明 |
| ---- | ---- |
| `waiting` | ラン開始前、または参加受付中 |
| `battle` | フロア進行中（`start-floor` 後） |
| `floor_transition` | フロアクリア後の移行中 |
| `result` | アイテム取得選択中 |
| `game_over` | ゲームオーバー |
