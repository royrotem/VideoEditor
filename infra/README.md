# Infrastructure

Local-development infrastructure for the AI Video Editor.

## Services

| Service  | Port(s)        | Purpose                                           |
| -------- | -------------- | ------------------------------------------------- |
| Postgres | 5432           | Relational database                               |
| Redis    | 6379           | Cache + Celery broker / result backend            |
| MinIO    | 9000 (S3 API), 9001 (web console) | S3-compatible object storage    |

The same MinIO image and the same `boto3`-based client code are used in
production - we never swap the storage layer for "local mode."

## Usage

```bash
# Start everything in the background
docker compose -f infra/docker-compose.yml up -d

# Tail logs of a single service
docker compose -f infra/docker-compose.yml logs -f minio

# Tear down (keep data volumes)
docker compose -f infra/docker-compose.yml down

# Tear down and wipe data
docker compose -f infra/docker-compose.yml down -v
```

After the first boot, MinIO will have two buckets ready: `assets` and
`renders`. The buckets are created by the `minio-bootstrap` one-shot
service.

## Configuration

Copy `infra/.env.example` to `.env` at the repo root. Both the docker
compose file and the backend pick up the same environment variables.

## MinIO console

Open <http://localhost:9001> and log in with the `S3_ACCESS_KEY` /
`S3_SECRET_KEY` values from your `.env`.
