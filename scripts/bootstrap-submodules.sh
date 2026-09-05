#!/usr/bin/env sh
set -eu

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Run this command inside a Git checkout." >&2
  exit 1
fi

git submodule sync --recursive
git submodule update --init --recursive
git submodule status --recursive
