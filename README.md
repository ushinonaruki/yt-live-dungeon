# yt-live-dungeon

YouTube Live のコメントを参加コマンドとして扱う、リアルタイムダンジョンゲームのヘッドレスバックエンド。YouTube Live Adapter と Unity Client は、このリポジトリが公開するHTTP APIだけを経由して利用する。

- FastAPI / PostgreSQL / Redis / SQLAlchemy（非同期） / Alembic
- ゲーム仕様の正本はObsidian（`obsidian/YTL100ダンジョン/` はGit未追跡の参照コピー）であり、本READMEは利用・開発手順と、現時点で実装済みの公開境界だけを説明する

## ディレクトリ構成

```text
.
├── compose.yaml                # Docker Compose（api + postgres + redis + pgadmin）
├── alembic.ini                 # Alembic設定（src/yt_live_dungeon/migrations を参照）
├── pyproject.toml / uv.lock    # 依存パッケージ定義（唯一のPython package root）
├── .env.example                # 環境変数テンプレート
│
├── src/yt_live_dungeon/
│   ├── app.py                  # FastAPIエントリーポイント（yt_live_dungeon.app:app）
│   ├── config.py                # 環境変数管理
│   ├── api/                    # HTTPルーティング・入出力DTO変換だけ
│   ├── features/                # ゲーム機能単位のUse Case・純粋計算
│   ├── domain/                  # 複数機能が共有する小さな型・契約
│   ├── persistence/              # ORM model・DB query・seed
│   ├── cache/                    # Redisクライアント
│   └── migrations/                # Alembicマイグレーション
│
├── tests/                      # unit / integration / api
│
└── docker/
    ├── api/Dockerfile            # apiサービス用マルチステージビルド
    ├── postgres/Dockerfile       # PostgreSQL
    ├── redis/Dockerfile          # Redis
    └── pgadmin/Dockerfile        # pgAdmin 4（PostgreSQL管理GUI）
```

## セットアップ（Dockerだけで完結）

ホストへPython、uv、PostgreSQL、Redisを導入する必要はない。必要なのはGitとDockerだけ。

```bash
cp .env.example .env
docker compose build
docker compose up -d postgres redis
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m yt_live_dungeon.persistence.seed.load development
docker compose up -d api
```

`docker compose up --build` でもまとめて起動できる。

停止する場合は次を使う。データvolumeは残る。

```bash
docker compose down
```

## 開発・検証コマンド

すべてDocker Compose経由で実行する。

```bash
docker compose run --rm api pytest -q
docker compose run --rm api ruff check .
docker compose run --rm api alembic current
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m yt_live_dungeon.persistence.seed.load development
```

## 動作確認

```text
http://localhost:8000/docs
```

```bash
docker compose exec -T api python -c "import json, urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')))"
```

## pgAdmin（PostgreSQL管理GUI）

`docker compose up -d` で pgAdmin もあわせて常設起動する。DB本体ではなく、既存PostgreSQLコンテナへ接続するための管理クライアントであり、`.env`に`PGADMIN_DEFAULT_EMAIL`・`PGADMIN_DEFAULT_PASSWORD`・`PGADMIN_PORT_HOST`が必要となる。

```text
http://localhost:${PGADMIN_PORT_HOST}
```

ログインには`.env`の`PGADMIN_DEFAULT_EMAIL`・`PGADMIN_DEFAULT_PASSWORD`を使う。ログイン後、PostgreSQLサーバーを新規登録する（Host名はComposeのサービス名`postgres`、Portは`POSTGRES_PORT_CONTAINER`、DB名・ユーザー名・パスワードは`.env`のPostgreSQL設定を使用）。登録した接続情報は`pgadmin_data` volumeへ永続化され、pgAdminコンテナを再作成しても保持される。

ER図はpgAdminのERD Tool（対象スキーマを右クリック → ERD For Schema）から確認できる。将来PostgreSQLをRDSへ移行した場合も、同じpgAdminから接続先を切り替えるだけで利用を継続できる。

## 現時点で実装済みの公開HTTP API

| Method | Path | 概要 |
| ------ | ---- | ---- |
| GET | `/health` | ヘルスチェック（`{"status": "ok", "database": "ok", "redis": "ok"}`） |
| POST | `/api/v1/runs/{run_id}/commands` | コマンド受付（`@login` / `@logout` / `@select` / `@ready` / `@move` / `@status` / `@bag` / Spellコマンドなど） |
| GET | `/api/v1/runs/{run_id}/state` | ランの現在状態取得（冒険者・敵・CAMP状態を含む） |
| GET | `/api/v1/runs/{run_id}/events?after={sequence}` | 単調増加するsequence以降の差分イベント取得 |

runそのものを作成する公開APIは現時点で存在しない。

`POST /api/v1/runs/{run_id}/commands` の入力例:

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

`received_at` はtimezone付きでなければならない。

## 現時点の実装範囲

実装済み:

- CAMP中の参加変更（`@login` / `@logout`）と8人上限
- 所持アイテム・Lv・鍛冶・候補選択を含むCAMP行動
- CAMP終了（全員READYまたは5分経過）と次フロアへの遷移
- 敵group（マスター＋ミニオン）の永続化とcurrent/next groupの抽選・引き継ぎ
- `RunEnemy` runtime、floor補正、参加人数に応じた敵MP自然回復
- `EnemyPolicy` 境界（Context/Intent/registry/random_v1/fallback）とBattle Engineによる合法候補生成・Intent再検証
- マスター撃破判定とCAMP開始・100F最終結果への接続
- `GET .../state` / `GET .../events` によるポーリング

未実装・対象外（現時点）:

- runを作成する公開API、初回参加受付フロー
- 冒険者から敵への攻撃Use Case
- Weak / Chain / Break / Intercept
- YouTube Live Adapterの実接続
- Unity Clientの実接続
- 敵AIの最終方式（差し替え可能な内部インターフェースまでが実装範囲）

ゲームルールの詳細仕様はObsidian（`obsidian/YTL100ダンジョン/`）を正本とする。実装方針の詳細は `yt-live-dungeon_claude-code_detail-design_camp.md` を参照。
