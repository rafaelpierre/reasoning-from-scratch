import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import modal

app = modal.App("code-server-a100")

# Resolve the build manifest locally; the deployed module has a different path.
runtime_project_dir = str(Path(__file__).resolve().parents[2]) if modal.is_local() else "/.uv"

image = (
    modal.Image.debian_slim(python_version="3.13")
    # Install browser-based code-server and launch it explicitly below.
    .apt_install("curl", "ca-certificates")
    .run_commands(
        "curl -fsSL https://code-server.dev/install.sh -o /tmp/install-code-server.sh",
        "sh /tmp/install-code-server.sh --method=standalone --prefix=/usr/local",
        "/usr/local/bin/code-server --version",
    )
    # Use published packages even if uv add recreates a local workspace source.
    .uv_sync(runtime_project_dir, groups=["remote"], extra_options="--no-sources")
    .env({"VIRTUAL_ENV": "/.uv/.venv"})
    .run_commands(
        '/.uv/.venv/bin/python -c "import torch; print(torch.__version__)"',
        "/.uv/.venv/bin/python -m ipykernel install --prefix=/usr/local "
        '--name=modal-remote --display-name="Python (Modal remote / PyTorch)"',
    )
)

# Stage outside /workspace, which is covered by the persistent Volume at runtime.
# Modal imports this module from /root/code_server.py inside the container.
# Only the deployment machine has the repository layout and local sources.
if modal.is_local():
    repository_root = Path(__file__).resolve().parents[3]
    for chapter in sorted(repository_root.glob("ch*")):
        if chapter.is_dir():
            image = image.add_local_dir(
                chapter,
                remote_path=f"/opt/chapters/{chapter.name}",
                copy=True,
                ignore=["**/__pycache__/**", "**/*.pyc", "**/.ipynb_checkpoints/**"],
            )

workspace = modal.Volume.from_name(
    "code-server-workspace",
    create_if_missing=True,
)


def seed_chapters(source: Path, destination: Path):
    """Add bundled chapter files without overwriting existing workspace files."""
    for item in source.rglob("*"):
        target = destination / item.relative_to(source)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


@app.function(
    image=image,
    gpu="A100",
    cpu=4,
    memory=16384,  # System RAM in MiB; separate from GPU memory.
    volumes={"/workspace": workspace},
    secrets=[modal.Secret.from_name("custom-secret")],
    max_containers=1,
    scaledown_window=600,
    timeout=1800,
)
@modal.concurrent(max_inputs=100)
@modal.web_server(8080, startup_timeout=120)
def serve():
    if not (os.environ.get("PASSWORD") or os.environ.get("HASHED_PASSWORD")):
        raise RuntimeError(
            "Set PASSWORD or HASHED_PASSWORD in the Modal secret 'custom-secret'."
        )

    for directory in ("projects", "user-data", "extensions"):
        Path(f"/workspace/{directory}").mkdir(parents=True, exist_ok=True)

    seed_chapters(Path("/opt/chapters"), Path("/workspace/projects"))

    process = subprocess.Popen(
        [
            "/usr/local/bin/code-server",
            "--bind-addr", "0.0.0.0:8080",
            "--auth", "password",
            "--cert", "false",  # Modal terminates HTTPS at its proxy.
            # Modal's WebSocket proxy does not support permessage-deflate.
            "--vscode-option", "disable-websocket-compression",
            # Unix sockets must live on the container filesystem, not the Volume.
            "--session-socket", "/tmp/code-server-ipc.sock",
            "--user-data-dir", "/workspace/user-data",
            "--extensions-dir", "/workspace/extensions",
            "/workspace/projects",
        ],
    )
    # Keep stdout/stderr in Modal logs and report an early crash directly.
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"code-server exited with status {process.returncode}; see logs above."
            )
        try:
            with socket.create_connection(("127.0.0.1", 8080), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    process.terminate()
    raise TimeoutError("code-server did not listen on port 8080 within 100 seconds.")
