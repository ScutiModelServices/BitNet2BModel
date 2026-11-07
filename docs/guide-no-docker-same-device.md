# BitNet2BModel: without Docker, on Windows

Run Microsoft BitNet b1.58 2B4T on the CPU directly with Python: one process, no load balancer, listening on `127.0.0.1:9140`.

## Requirements
- Windows with Python 3.11 or newer and uv (`winget install astral-sh.uv`).
- Internet on the first start (about 1.2 GB of weights).
- RAM for the model (one copy).

## Start
Double-click `run.bat`, or run it in a terminal from `BitNet2BModel\`. Choose **1 Run the service** in the menu, or run `run.bat run` to skip the menu. It runs `uv sync` to create or update `.venv`, then starts
`python src/app.py`. The first start downloads about 1.2 GB of weights.

Linux or macOS:
```bash
cd BitNet2BModel
uv sync
uv run python src/app.py
```

## Settings
`run.bat` loads `.env` in this folder (copy `.env.example`); a real environment variable wins over it. Set variables in `.env` or in the environment before starting:

| Variable | Default | Effect |
|---|---|---|
| `BITNET_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` only if other devices must reach it. |
| `BITNET_PORT` | `9140` | Port. |
| `BITNET_ADMIN_PASSWORD` | empty | Unlocks `/admin/` and requires tokens on every call but `/health`. Empty = no auth. |
| `BITNET_WARM` | `1` | Load the model at start; with `0` the first request pays the load time. |
| `BITNET_NUM_THREAD` | the library decides | CPU threads. Set it to the number of **physical** cores. |

PowerShell: `$env:BITNET_ADMIN_PASSWORD = "secret"; .\run.bat`
Bash: `BITNET_ADMIN_PASSWORD=secret uv run python src/app.py`

## Check
```bash
curl http://127.0.0.1:9140/health
```
`ready` is `false` until the model has loaded. Then open `http://127.0.0.1:9140/admin/` (see [guide-web-ui.md](guide-web-ui.md)),
make a token, and try a call:
```bash
curl -X POST http://127.0.0.1:9140/v1/chat -H "Content-Type: application/json" -H "X-Internal-Token: bitnet_..." -d '{"messages":[{"role":"user","content":"Say hello in one sentence."}]}'
```

## Stop
Ctrl+C in the terminal. Do not run this and the Docker stack together: both use port 9140.

## Tests
`uv run pytest`.
