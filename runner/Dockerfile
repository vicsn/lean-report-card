FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    ELAN_HOME=/root/.elan \
    HOME=/root \
    PATH=/root/.elan/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash build-essential ca-certificates curl git graphviz jq time zstd \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -o /tmp/elan-init.sh \
    && sh /tmp/elan-init.sh -y --no-modify-path --default-toolchain none \
    && cp /root/.elan/bin/elan /usr/local/bin/elan \
    && for tool in lean leanc lake leanchecker; do ln -sf /usr/local/bin/elan "/usr/local/bin/$tool"; done \
    && rm -rf /tmp/elan-init.sh /root/.elan/toolchains

WORKDIR /opt/runner
COPY runner/analyze.py /opt/runner/analyze.py
COPY src/lean_report_card/scoring.py /opt/runner/scoring.py

RUN mkdir -p /workspace /output
CMD ["python", "/opt/runner/analyze.py"]
