#!/usr/bin/env sh
set -eu
python -m lean_report_card.wait_for_db
exec uvicorn lean_report_card.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
