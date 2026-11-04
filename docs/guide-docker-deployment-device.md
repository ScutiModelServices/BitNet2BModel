# BitNet2BModel: Docker on a deployment machine

Run Microsoft BitNet b1.58 2B4T on the CPU on a separate always-on machine (default `lex@scutiserver1.local`, folder
`/media/ZimaOS-HD/Apps/BitNet2BModel`). Callers reach it over the published port.

## Requirements on the machine
- Docker + Compose v2, and ssh access (root over ssh is refused; use the normal user).
- Enough RAM for the model times `BITNET_REPLICAS`.

## 1. Publish the code (from your PC)
Run `BitNet2BModel\tools\deploy.bat`. Menu:

| Option | Does |
|---|---|
| 1 | Publish code to the `live` branch |
| 2 | Copy your `.env` to the server (one ssh/tar session, one password prompt) |
| 3 | Both |
| 4, 5 | Dry runs of 1 and 2 |
| 6 | chown helper, if option 2 says `Permission denied` |
| R | Release: publish, then tag `VERSION` |

Keep your own target in the git-ignored `tools\deploy.local.bat` (copy `tools\deploy.local.example.bat`), or set
`DEPLOY_HOST`, `DEPLOY_DIR` and `DEPLOY_WEB_PORT` before running. Commit `main` first: publish reads committed `main`.

## 2. First-time setup on the machine
```bash
mkdir -p /media/ZimaOS-HD/Apps
git clone -b live <your-repo-url> /media/ZimaOS-HD/Apps/BitNet2BModel
cd /media/ZimaOS-HD/Apps/BitNet2BModel
```
Create `.env` (deploy option 2 copies yours, or `cp .env.example .env` and edit):
- `BITNET_ADMIN_PASSWORD`: a real password.
- `BITNET_REPLICAS=1` unless you have the memory for more.
- `BITNET_PORT=9140` (published on all interfaces; firewall it if the LAN should not reach it, or bind it to
  `127.0.0.1` in the `ports:` line of `bitnet_lb` when only callers on the machine need it).

## 3. Start
```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:9140/health
```
The first start downloads about 1.2 GB of weights into the `models` volume; `bitnet_lb` waits for a healthy service
(up to 300 s grace).

## 4. Connect callers
1. Open `http://<machine-ip>:9140/admin/`, sign in with the admin password and create one token per caller
   (see [guide-web-ui.md](guide-web-ui.md)).
2. The caller holds the URL and token:
   - Caller on another machine: `http://<machine-ip>:9140`.
   - Caller in a Docker stack on the same machine: `http://host.docker.internal:9140`.
3. Try a call from the machine:
   ```bash
   curl -X POST http://127.0.0.1:9140/v1/chat -H "Content-Type: application/json" -H "X-Internal-Token: bitnet_..." -d '{"messages":[{"role":"user","content":"Say hello in one sentence."}]}'
   ```

## Updating
```bash
cd /media/ZimaOS-HD/Apps/BitNet2BModel
git pull
docker compose up -d --build
docker compose restart bitnet_lb
```

## Problems
| Symptom | Fix |
|---|---|
| Caller cannot reach the service | Check the caller's URL and token, and that `curl http://<machine-ip>:9140/health` works. |
| nginx 502 after an update | `docker compose restart bitnet_lb`. |
| Permission denied on push | deploy.bat option 6. |
| Port 9140 in use | Another stack on the machine already publishes it. |
