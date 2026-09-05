#!/usr/bin/env sh
set -eu
base="${1:-http://localhost}"
curl --fail --silent --show-error "$base/healthz"
printf '\n'
curl --fail --silent --show-error "$base/readyz"
printf '\n'
