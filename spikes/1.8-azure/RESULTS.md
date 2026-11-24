# Spike 1.8 — Azure hello-world (local notes, not committed)

## Setup done (no cloud writes yet)
- Azure CLI 2.93.0 installed as an isolated uv tool (`uv tool install --python 3.12 azure-cli`), `az login` done, subscription "Azure subscription 1" Enabled, budget alert created by the user.
- Providers `Microsoft.App`, `Microsoft.OperationalInsights`, `Microsoft.ContainerRegistry` are NotRegistered (must be registered before creating anything).
- Container Apps regions include Brazil South and Chile Central (closest to Argentina).
- Image: `spikes/1.8-azure/Dockerfile` (python:3.14-slim pinned by digest, fastmcp 3.x, non-root user), 336 MB, linux/amd64.

## Local container test (docker run, stateless_http=True)
- Tools listed, whoami OK, sleep_progress(5): 5 progress events received, 5.03 s.
- ctx.session_id: a NEW uuid on every call, even within the same client connection (2 consecutive calls -> 2 different ids); request_id increments.
  => in stateless mode the session id carries no state and must never be used as a key (matches the project decision: Opik threads use run_id/draft_id).
