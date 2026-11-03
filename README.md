# BitNet2BModel

The one place Microsoft's BitNet b1.58 2B4T is served. Projects send it chat turns over HTTP instead of loading the
model themselves. It has the same admin page, tokens, rate limits, metrics, settings and update checks as
`MiniCPM52BModel` and `LayaModel`.

BitNet is run in this process on the CPU with `transformers`. Ollama and stock llama.cpp cannot load Microsoft's GGUF
(`unsupported tensor "blk.0.ffn_down.weight" size overflows`), and bitnet.cpp's kernels are not used here. Expect the
small memory footprint, not the speed the model card shows for bitnet.cpp.

## API

| Call | Purpose |
|---|---|
| `POST /v1/chat` | `{"messages", "project", "temperature", "max_tokens"}` → `{"content", "finish_reason", "model", "fallback", "usage", "duration_ms"}`. |
| `GET /health` | `{"status": "ok", "model", "ready", "num_thread", "project_models"}`; `ready` is true once the base model is loaded. No token needed. |

`messages` use the roles `system`, `user` and `assistant`. `temperature` 0 (the default) is greedy. `max_tokens` is
at most 4096 and the whole conversation must fit the model's 4096-token window (422 otherwise).

**Not supported.** `tools`, `schema` and `thinking` are refused with 422, not ignored: the model has no tool-calling
or thinking mode and the service has no constrained decoding. Use `MiniCPM52BModel` for those.

**Project models.** Optional `"project": "my-project"` (`^[a-z0-9][a-z0-9_-]{0,47}$`) uses the checkpoint folder
`<project models folder>/my-project` when it holds a complete Hugging Face checkpoint of the same architecture
(`config.json`, weights, tokenizer). Up to *Project models loaded per replica* stay in memory, least recently used out
first. A missing or unloadable project uses the base model and returns `"fallback": true`. `model` names the model
that answered. Replacing the files of an already loaded project needs a replica restart.

## Admin page

`/admin/` (password `BITNET_ADMIN_PASSWORD`): per-project tokens with project scope, rate limit and expiry, usage
numbers, CPU threads, the Settings card (update check hours, in-flight cap, project models), and the Updates card
(**Check now** and **Download new weights** for the Hugging Face repository). New weights are downloaded once into
the shared models volume; the other replicas notice within a few seconds and load them on their next request.
`/metrics` (admin password) is Prometheus text per token.

## Run

```bash
docker compose up -d --build        # http://<host>:9140
```

Without Docker: `run.bat` (uv, listens on `127.0.0.1:9140`). The first start downloads about 1.2 GB. Each replica holds
the unpacked model in RAM (about 5 GB), so `BITNET_REPLICAS` multiplies memory use. See `deployment.md`.

## Tests

```bash
uv sync
uv run pytest
```

## Limits worth knowing

- One generation at a time per replica; extra calls wait, and more than the in-flight cap get 429.
- The rate limit is per replica.
- A generation stops after 120 s and returns what it has with `finish_reason: "length"`.
- `TORCHDYNAMO_DISABLE=1` is set by the service; unpacking the weights otherwise tries to compile C++ and fails on
  machines without a compiler.
