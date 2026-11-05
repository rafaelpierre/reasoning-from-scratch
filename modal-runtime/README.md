# CUDA + VS Code image

From the **repository root**, using a Lima instance with containerd, nerdctl,
and BuildKit installed (replace `default` with your instance name):

```sh
limactl shell default nerdctl build --platform linux/amd64 \
  -f modal-runtime/Dockerfile -t reasoning-vscode:latest .
limactl shell default nerdctl run -d --name reasoning-vscode \
  -p 127.0.0.1:3001:3001 --shm-size=1g \
  -e PUID=1000 -e PGID=1000 \
  -v reasoning-vscode-config:/config reasoning-vscode:latest
```

Open <https://localhost:3001> (the image uses a self-signed certificate).
The container uses LinuxServer's original startup services and persistent
`/config` directory. Select `/opt/venv/bin/python` as the VS Code interpreter.
Mount your source code at `/workspace` when needed; source code is not baked in.

The build installs only `[project].dependencies` from the **root**
`pyproject.toml` with uv, using Python 3.13. It does not install workspace
members, development groups, optional extras, or the root package. The workspace
lockfile is not used, so dependency versions are resolved during each uncached
build. Pin the image build arguments to digests for stable base images.

CUDA 13.0 runtime libraries are assembled in a `debian:bookworm-slim` stage.
The final image inherits `lscr.io/linuxserver/vscode:latest`, which includes a
Debian desktop streamed to the browser; the final image is therefore not slim.
This is the requested VS Code desktop image, not LinuxServer's `code-server`
image. CUDA compiler tools (`nvcc`) and host drivers are not included.

The image targets `linux/amd64`, as required by this VS Code image. An ARM Mac
needs x86 emulation to build or run it. Lima on macOS does not provide an NVIDIA
GPU for CUDA execution. GPU validation must run on a Linux NVIDIA host with the
NVIDIA Container Toolkit configured for its container runtime; add `--gpus all`
to the run command there. The build checks Python imports and CUDA-enabled Torch,
but cannot check GPU availability during the build.

On that GPU host, verify with:

```sh
nerdctl exec reasoning-vscode python -c \
  'import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))'
```

References: [LinuxServer VS Code](https://docs.linuxserver.io/images/docker-vscode/),
[uv in containers](https://docs.astral.sh/uv/guides/integration/docker/), and
[NVIDIA Debian packages](https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/).
