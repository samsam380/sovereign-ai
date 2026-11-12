#!/usr/bin/env python3
"""Download verified GGUF files and start the local Sovereign AI server."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
from importlib.util import find_spec
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
PROFILES = ("original", "abliterated")
MODELS = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))


def verify_file(path: Path, asset: dict) -> None:
    if path.stat().st_size != asset["size"]:
        raise ValueError(f"Unexpected file size for {path}.")
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != asset["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {path}. Move the file aside and retry.")


def download(folder: Path, asset: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / asset["filename"]
    partial = final.with_suffix(".gguf.part")
    lock = final.with_suffix(".gguf.lock")
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if final.exists():
            verify_file(final, asset)
        else:
            size = partial.stat().st_size if partial.exists() else 0
            if size < asset["size"]:
                url = (
                    f'https://huggingface.co/{asset["repository"]}/resolve/'
                    f'{asset["revision"]}/{asset["filename"]}'
                )
                subprocess.run(
                    [
                        "curl", "--disable", "--fail", "--location",
                        "--proto", "=https", "--proto-redir", "=https",
                        "--connect-timeout", "20", "--retry", "3",
                        "--continue-at", "-", "--output", str(partial), url,
                    ],
                    check=True,
                )
            verify_file(partial, asset)
            partial.replace(final)
    print(f"{final.name}: SHA-256 OK", flush=True)


def file_path(path: Path, description: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{description} is missing at {path}.")
    return path


def web_config(port: int) -> Path:
    if any(find_spec(package) is None for package in ("bs4", "ddgs", "mcp")):
        raise ValueError("Install requirements-web.txt in a virtual environment first.")

    state = ROOT / ".local"
    state.mkdir(mode=0o700, exist_ok=True)
    target = state / f"mcp-web-{port}.json"
    config = {
        "mcpServers": {
            "web": {
                "command": sys.executable,
                "args": [str(ROOT / "web_tools.py")],
                "timeout_ms": 90000,
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=state, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(config, handle)
            handle.close()
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def serve(args: argparse.Namespace, folder: Path) -> None:
    server = file_path(args.server, "llama-server")
    model = file_path(args.model_file or folder / MODELS[args.profile]["filename"], "Model")
    command = [
        str(server), "--model", str(model),
        "--alias", f"sovereign-ai-{args.profile}",
        "--host", "127.0.0.1", "--port", str(args.port),
        "--ctx-size", str(args.ctx_size), "--parallel", "1",
        "--batch-size", "128", "--ubatch-size", "128",
        "--n-gpu-layers", args.gpu_layers,
        "--jinja", "--reasoning", "off", "--no-reasoning-preserve",
    ]
    if args.devices:
        command.extend(["--device", args.devices])
    if args.tensor_split:
        command.extend(["--split-mode", "layer", "--tensor-split", args.tensor_split])
    if args.ui_dir:
        index = file_path(args.ui_dir / "index.html", "Built WebUI")
        command.extend(["--path", str(index.parent)])
    if args.vision or args.mmproj:
        projector = file_path(args.mmproj or folder / MODELS["vision"]["filename"], "Vision projector")
        command.extend(["--mmproj", str(projector), "--no-mmproj-offload", "--image-max-tokens", "1024"])
    if args.web:
        command.extend(["--mcp-servers-config", str(web_config(args.port))])
    print(f"Starting {args.profile} on http://127.0.0.1:{args.port}/", flush=True)
    os.execv(server, command)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    for action in ("download", "verify", "serve"):
        subcommand = subcommands.add_parser(action)
        subcommand.add_argument("profile", choices=PROFILES)
        subcommand.add_argument("--model-dir", type=Path, default=ROOT / "models")
        subcommand.add_argument("--vision", action="store_true", help="Include the pinned vision projector.")

    serve_parser = subcommands.choices["serve"]
    serve_parser.add_argument("--server", type=Path, default=ROOT / "llama.cpp/build/bin/llama-server")
    serve_parser.add_argument("--model-file", type=Path, help="Use an existing GGUF file.")
    serve_parser.add_argument("--mmproj", type=Path, help="Use an existing vision projector.")
    serve_parser.add_argument("--ui-dir", type=Path, help="Serve a built WebUI directory.")
    serve_parser.add_argument("--port", type=int, default=8080)
    serve_parser.add_argument("--ctx-size", type=int, default=4096)
    serve_parser.add_argument("--gpu-layers", default="0", help="Number of layers to offload, or all.")
    serve_parser.add_argument("--devices", help="llama.cpp devices, for example CUDA0,CUDA1.")
    serve_parser.add_argument("--tensor-split", help="Layer split ratios, for example 1,1.")
    serve_parser.add_argument("--web", action="store_true", help="Enable optional web search and page reading.")
    args = parser.parse_args()
    if args.action == "serve":
        if not 1 <= args.port <= 65535 or args.ctx_size <= 0:
            parser.error("Use a valid TCP port and a positive context size.")
        if args.vision and args.mmproj:
            parser.error("Choose either --vision or --mmproj.")
    return args


def main() -> None:
    args = arguments()
    folder = args.model_dir.expanduser().resolve()
    if args.action == "serve":
        serve(args, folder)
        return
    profiles = [args.profile, "vision"] if args.vision else [args.profile]
    for profile in profiles:
        asset = MODELS[profile]
        if args.action == "download":
            download(folder, asset)
        else:
            verify_file(folder / asset["filename"], asset)
            print(f'{asset["filename"]}: SHA-256 OK')


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"Sovereign AI: {error}")

