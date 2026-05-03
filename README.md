# yt-live-dungeon

YouTube Live コメントを使ったリアルタイムダンジョンゲームのバックエンド。

## 開発段階

- **phase1**: 手動API入力による参加予約の実装

## ディレクトリ構成

```text
.
├── backend/          # FastAPI アプリケーション (Python)
├── database/         # DB マイグレーション (Alembic)
│   ├── alembic.ini
│   └── migrations/
│       └── versions/
├── docker/           # Dockerfile 群
│   ├── postgres/
│   └── redis/
├── compose.yaml       # Docker Compose
└── .env              # 環境変数 (Docker + Python 共通)
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

# 差分確認
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

| Method | Path                         | 概要 |
| ------ | ---------------------------- | ---- |
| POST   | `/runs`                      | ラン作成 |
| GET    | `/runs/{run_id}`             | ラン取得 |
| GET    | `/runs/{run_id}/state`       | ランの現在状態取得 |
| GET    | `/runs/{run_id}/logs`        | ランのログ取得 |
| POST   | `/runs/{run_id}/commands`    | コマンド受付 (`@join` など) |

## 動作確認

Swagger UI を開く。

```text
http://localhost:8000/docs
```

以下の順に実行する。

1. `POST /runs`
2. `POST /runs/{run_id}/commands` に `@join` を送信
3. 同じ `youtube_id` で再度 `@join` を送信し、`duplicate` になることを確認
4. `GET /runs/{run_id}/state` で `pending_join_count = 1` を確認
5. `GET /runs/{run_id}/logs` で `join_pending` / `join_duplicate` を確認

`POST /runs/{run_id}/commands` の例。

```json
{
  "source": "manual",
  "external_message_id": "debug-001",
  "youtube_id": "yt-user-001",
  "display_name": "テスト太郎",
  "text": "@join"
}
```
