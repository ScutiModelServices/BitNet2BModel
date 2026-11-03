# Changelog

## Unreleased

- Answer cache (`BITNET_CACHE_SIZE`, default 256, 0 = off; `X-Cache` header): the last answers to identical `temperature` 0 requests are sent again without generating.
- `POST /v1/chat` accepts `"stream": true`: the answer arrives as JSON lines (`content` pieces, then `done`).

- First version: Microsoft BitNet b1.58 2B4T served on the CPU with `transformers`, with the admin page, project
  tokens (scope, rate limit, expiry), metrics, Settings card, update checks and weight downloads shared with
  `MiniCPM52BModel` and `LayaModel`.
- `POST /v1/chat` takes `messages`, `project`, `temperature` and `max_tokens`. Tools, schemas and thinking are refused
  with 422.
- Project models are checkpoint folders loaded in process (LRU).
