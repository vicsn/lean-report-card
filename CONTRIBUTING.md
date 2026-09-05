# Contributing

Keep analyzer output versioned and machine-readable. New checks must explain their evidence, confidence, scoring effect, resource budget and failure behavior. Do not classify a missing or incompatible optional tool as a repository defect.

Before opening a change, run:

```sh
ruff check .
pytest
docker build .
docker build -f runner/Dockerfile .
terraform -chdir=deploy/gcp fmt -check -recursive
terraform -chdir=deploy/gcp validate
```
