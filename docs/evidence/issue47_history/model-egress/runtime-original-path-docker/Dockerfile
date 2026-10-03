# syntax=docker/dockerfile:1
FROM python:3.12.14-slim
RUN --mount=type=secret,id=system_ca,required=true \
    apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=system_ca,required=true \
    PIP_CERT=/run/secrets/system_ca pip install --no-cache-dir PyYAML==6.0.3 pandas==2.2.3 numpy==2.3.5 lxml==6.1.1
COPY requirements-continuous-context.txt /tmp/requirements-continuous-context.txt
RUN --mount=type=secret,id=system_ca,required=true \
    PIP_CERT=/run/secrets/system_ca pip install --no-cache-dir --no-deps --require-hashes -r /tmp/requirements-continuous-context.txt
WORKDIR /workspace/work/issue47-model-run-verified
USER 0
CMD ["sleep", "infinity"]
