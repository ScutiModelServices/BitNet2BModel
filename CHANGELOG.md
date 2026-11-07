# Changelog

## Unreleased

- `SERVICE_MODELS_DIR` sets where a local (no Docker) run keeps downloaded model weights: `settings.apply_models_dir()` maps it to `HF_HOME` and `OLLAMA_MODELS` at start.
- Docs: `docs/guide-cli.md`, a PowerShell-only way to test the service.

### Breaking: common service environment variables

Service-owned environment variables now use `SERVICE_*`. Old names are no longer read.
Rename old names once in your real `.env`, Compose `environment:` block, and CI/secret settings.

| Old name | New name |
|---|---|
| `BITNET_ADMIN_PASSWORD` | `SERVICE_ADMIN_PASSWORD` |
| `BITNET_CACHE_SIZE` | `SERVICE_CACHE_SIZE` |
| `BITNET_DTYPE` | `SERVICE_DTYPE` |
| `BITNET_HOST` | `SERVICE_HOST` |
| `BITNET_MAX_INFLIGHT` | `SERVICE_MAX_INFLIGHT` |
| `BITNET_MAX_PROJECT_MODELS` | `SERVICE_MAX_PROJECT_MODELS` |
| `BITNET_MEM_LIMIT` | `SERVICE_MEM_LIMIT` |
| `BITNET_MODEL` | `SERVICE_MODEL` |
| `BITNET_NUM_THREAD` | `SERVICE_NUM_THREAD` |
| `BITNET_PORT` | `SERVICE_PORT` |
| `BITNET_PROJECT_MODELS_DIR` | `SERVICE_PROJECT_MODELS_DIR` |
| `BITNET_REPLICAS` | `SERVICE_REPLICAS` |
| `BITNET_TOKENS_FILE` | `SERVICE_TOKENS_FILE` |
| `BITNET_UPDATE_CHECK_HOURS` | `SERVICE_UPDATE_CHECK_HOURS` |
| `BITNET_WARM` | `SERVICE_WARM` |
| `BITNET_WEB_DIR` | `SERVICE_WEB_DIR` |
| `BITNET_WEIGHTS_MARKER` | `SERVICE_WEIGHTS_MARKER` |

- Default HTTP port moves from 9140 to 29201. Update explicit old ports in your real `.env`, saved tool-service `backends.json` connections, and browser/MCP client configurations once. Compose now uses 29201 inside API replicas and nginx; deployments using the old Compose default must recreate containers. A custom host-port override stays in effect until you change it; container ports still move to 29201.

- Renamed `BitNet2BModel` to `CNV_BitNet2B_Model`; Docker project, API image, services, load balancer and volumes now use `cnv_bitnet2b_model` names. Callers on `citadel_core` connect to `cnv_bitnet2b_model_lb` at the existing port.
- Docker volume migration: existing volumes with old names are orphaned; renaming does not move data. Stop the old stack before copying; never use `down -v`. The commands below assume the previous default Compose project name; substitute actual volume names if `-p` or `COMPOSE_PROJECT_NAME` overrode it.
  - `bitnet_models` → `cnv_bitnet2b_model_models`: `docker volume inspect bitnet_models && docker volume create cnv_bitnet2b_model_models && docker run --rm -v bitnet_models:/from:ro -v cnv_bitnet2b_model_models:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
  - `bitnet_tokens` → `cnv_bitnet2b_model_data`: `docker volume inspect bitnet_tokens && docker volume create cnv_bitnet2b_model_data && docker run --rm -v bitnet_tokens:/from:ro -v cnv_bitnet2b_model_data:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
- To retain an old volume instead, set its top-level volume definition to `external: true` and `name: <old-volume-name>` in a local Compose override. Rollback: stop the renamed stack, restore the previous checkout and folder name, and restart the old stack with its original volumes; copy back newer data first if the renamed stack accepted writes.

- `run.bat` loads `.env` from the service folder for a local run: it passes `--dotenv`, the service prints which variable names it loaded (never the values), and a real environment variable still wins. A plain `python src/app.py` and Docker never read `.env`.
- Untracked folders now start with `.` or `_`: `zip_versions/` is `_zip_versions/`. A local `voices`, `tem_code` or `zip_versions` folder from an older checkout needs renaming by hand.
- `run.bat` is now a menu (run the service, deploy, build the release ZIP) and `run.bat run|deploy|zip` skips it. `tools/deploy.bat`, `tools/make_zip.bat` and `tools/deploy.local.example.bat` are gone; the local deploy target is `tools/deploy.local.ini` (copy `tools/deploy.local.example.ini`).
- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.

- `run.bat`: runs `uv sync` directly; `python -m uv` failed when uv was installed only as a program (winget).
- Docker: `.dockerignore` keeps `.git`, `.venv`, tests and local state out of the build context (the same file in every model service).
- Compose: `stop_grace_period: 90s`, so a restart lets a running answer finish instead of cutting it off after Docker's default 10 s.
- Docs: set CPU threads to the number of physical cores, not logical CPUs.
- `/metrics` also returns `bitnet_request_seconds`, a histogram of how long `/v1` calls took on that replica.
- Compose: optional `SERVICE_MEM_LIMIT` caps the container's RAM (default no cap).

- Answer cache (`SERVICE_CACHE_SIZE`, default 256, 0 = off; `X-Cache` header): the last answers to identical `temperature` 0 requests are sent again without generating.
- `POST /v1/chat` accepts `"stream": true`: the answer arrives as JSON lines (`content` pieces, then `done`).

- First version: Microsoft BitNet b1.58 2B4T served on the CPU with `transformers`, with the admin page, project
  tokens (scope, rate limit, expiry), metrics, Settings card, update checks and weight downloads shared with
  `CNV_MiniCPM52B_Model` and `DSC_Laya_Model`.
- `POST /v1/chat` takes `messages`, `project`, `temperature` and `max_tokens`. Tools, schemas and thinking are refused
  with 422.
- Project models are checkpoint folders loaded in process (LRU).
