# Deploying BitNet2BModel

BitNet2BModel is one HTTP service (port 9140). It runs as `bitnet` replicas behind an nginx load balancer,
`bitnet_lb`. Callers use `http://<host>:9140`; they never reach a replica directly.

## Requirements

- Docker with Compose v2.
- About 5 GB of RAM **per replica** (each replica holds the unpacked model), plus the same again for every loaded
  project model.
- Network access on the first start to download the weights (about 1.2 GB) from Hugging Face.
- CPU only. The Dockerfile installs the CPU build of torch and fails the build if a CUDA or ROCm build is found.

## Settings

In `.env` next to `docker-compose.yml`:

| Variable | Default | Effect |
|---|---|---|
| `BITNET_REPLICAS` | `1` | Number of `bitnet` containers. Read by Compose. |
| `BITNET_PORT` | `9140` | Host port `bitnet_lb` publishes. |
| `BITNET_ADMIN_PASSWORD` | empty | Password for `/admin/`. When set, every call except `/health` must send a project token as `X-Internal-Token`. Empty = no auth. |
| `BITNET_NUM_THREAD` | torch decides | Starting value for the CPU threads card; a value saved on `/admin/` wins. |

On the **Settings** card of `/admin/` (saved in `settings.json` beside the tokens, shared by all replicas; a saved
value beats the environment variable named in brackets): update check hours (`BITNET_UPDATE_CHECK_HOURS`, 6),
in-flight cap (`BITNET_MAX_INFLIGHT`, 0 = 4), project models loaded per replica (`BITNET_MAX_PROJECT_MODELS`, 2),
project models folder (`BITNET_PROJECT_MODELS_DIR`, empty = off; in Docker use `/models/projects`), base model
(`BITNET_MODEL`, restart) and load at start (`BITNET_WARM`, restart). Compose does not pass these; add the variable
under `environment:` of `bitnet` to use one as a starting value.

## Start

```bash
docker compose up -d --build
curl http://127.0.0.1:9140/health
```

Expect `"ready": true` once a replica has loaded the model. The first start downloads the weights into the `models`
volume, so `bitnet_lb` can take a few minutes to appear (the health check allows 120 s before failures count; run
`docker compose ps` and wait).

## Scaling

```bash
BITNET_REPLICAS=3 docker compose up -d --build
docker compose restart bitnet_lb
```

The restart is needed because nginx resolves replica addresses once at start.

## Project models

Copy a complete checkpoint folder into the shared volume and set the **Project models folder** on the Settings card
to `/models/projects`:

```bash
docker compose exec bitnet mkdir -p /models/projects
docker compose cp ./garrison bitnet:/models/projects/garrison
```

Call `/v1/chat` with `"project": "garrison"`. Restart replicas after replacing an already loaded checkpoint.

## Updating the weights

The **Updates** card compares the downloaded revision of the Hugging Face repository with its newest one. **Download
new weights** fetches it into the models volume; every replica drops its old copy within a few seconds and loads the
new one on its next request (it needs RAM for both for a moment). The download is the repository's current `main`.
Updating the service itself: `docker compose up -d --build`, then `docker compose restart bitnet_lb`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `bitnet_lb` never starts | No replica is healthy yet (first download, or out of memory). `docker compose logs bitnet`. |
| Replicas restart in a loop | Out of RAM. Lower `BITNET_REPLICAS`. |
| 401 "Invalid token" | The caller sends no project token, or a revoked one. |
| 422 on `tools`, `schema` or `thinking` | Not supported by this service. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| Slow answers | `transformers` has no BitNet kernels; this is the expected CPU speed. Raise CPU threads on `/admin/`. |
| nginx 502 after scaling | `bitnet_lb` not restarted after the replica count changed. |

## Releasing

A plain publish (`tools\deploy.bat` option 1) only updates the `live` branch. For a release set `VERSION` (and
`pyproject.toml` to the same number), commit, then run `tools\deploy.bat` option R or
`py tools\publish_live.py --release`. `tools\make_zip.bat` then builds `zip_versions\BitNet2BModel-<VERSION>.zip`.
