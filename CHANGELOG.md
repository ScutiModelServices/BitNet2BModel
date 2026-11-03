# Changelog

## Unreleased

- First version: Microsoft BitNet b1.58 2B4T served on the CPU with `transformers`, with the admin page, project
  tokens (scope, rate limit, expiry), metrics, Settings card, update checks and weight downloads shared with
  `MiniCPM52BModel` and `LayaModel`.
- `POST /v1/chat` takes `messages`, `project`, `temperature` and `max_tokens`. Tools, schemas and thinking are refused
  with 422.
- Project models are checkpoint folders loaded in process (LRU).
