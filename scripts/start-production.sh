#!/bin/sh
set -eu

# Run migrations from the new image before it can become healthy and receive
# traffic. Alembic upgrades are idempotent, so normal container restarts are
# safe. A failed migration exits the container and leaves the old deployment
# serving traffic.
alembic upgrade head
alembic check

exec uvicorn main:app --host 0.0.0.0 --port 8080
