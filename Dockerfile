# syntax=docker/dockerfile:1
# Build from the repository root (the parent of modal-runtime).
ARG UV_IMAGE=ghcr.io/astral-sh/uv:latest
ARG VSCODE_IMAGE=lscr.io/linuxserver/vscode:latest

FROM ${UV_IMAGE} AS uv

# Assemble CUDA on Debian Slim without installing a host NVIDIA driver.
FROM debian:bookworm-slim AS cuda
ARG TARGETARCH
RUN test "$TARGETARCH" = amd64
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb -o /tmp/cuda-keyring.deb \
    && dpkg -i /tmp/cuda-keyring.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends cuda-libraries-13-0 \
    && rm -rf /var/lib/apt/lists/* /tmp/cuda-keyring.deb

FROM debian:bookworm-slim AS python-deps
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_LINK_MODE=copy \
    UV_NO_CONFIG=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN uv python install 3.13 && uv venv --python 3.13 /opt/venv
# Only the root manifest's project.dependencies; no workspace members, groups,
# extras, or installation of the root package itself.
COPY pyproject.toml /build/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python --no-sources -r /build/pyproject.toml \
    && uv pip check --python /opt/venv/bin/python

# Preserve LinuxServer's complete desktop stack and inherited /init entrypoint.
FROM ${VSCODE_IMAGE} AS runtime
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=cuda /usr/local/cuda-13.0/ /usr/local/cuda-13.0/
COPY --from=python-deps /opt/python/ /opt/python/
COPY --from=python-deps /opt/venv/ /opt/venv/
COPY --from=uv /uv /uvx /usr/local/bin/
RUN ln -sfn /usr/local/cuda-13.0 /usr/local/cuda \
    && printf '%s\n' /usr/local/cuda/targets/x86_64-linux/lib > /etc/ld.so.conf.d/cuda.conf \
    && ldconfig \
    && /opt/venv/bin/python -c "import torch, jupyterlab, tokenizers, nbformat, sympy, matplotlib; assert torch.version.cuda, 'Expected a CUDA-enabled torch wheel'"
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/cuda/bin:${PATH} \
    CUDA_HOME=/usr/local/cuda \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility
WORKDIR /workspace
EXPOSE 3001
