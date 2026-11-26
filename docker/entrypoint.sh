#!/bin/sh
# Container start: migrations under the advisory lock, then the server.
# `exec` makes the server PID 1, so `docker stop` (SIGTERM) reaches it and it shuts down cleanly.
set -e
python -m src.db.startup
exec python -m src.main
