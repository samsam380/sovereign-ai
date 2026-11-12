# Sovereign AI

Local chat, image input, and optional web search using the llama.cpp server and WebUI. Choose the original Qwen model or the Huihui abliterated variant at startup.

| Profile | Model | Download |
| --- | --- | ---: |
| `original` | Qwen3.8-27B Q4_K_M | 19.0 GB |
| `abliterated` | Huihui-Qwen3.8-27B-abliterated Q4_K | 16.8 GB |

The downloader fetches GGUF files from their publishers on Hugging Face. [models.json](models.json) pins each upstream revision, file size, and SHA-256 digest. The optional vision projector adds about 0.93 GB.

## Build llama.cpp

Use Linux, Python 3.11 or later, curl, and a recent C++ toolchain. On Debian, install the build dependencies and check out the revision used with the Sovereign AI theme.

```bash
sudo apt-get install git curl cmake build-essential libcurl4-openssl-dev python3 python3-venv
git clone https://github.com/samsam380/sovereign-ai.git
cd sovereign-ai
git clone https://github.com/ggml-org/llama.cpp.git
git -C llama.cpp checkout --detach 59d5fad7c111d30a547d690b69235ed9e05c035d
cmake -S llama.cpp -B llama.cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build llama.cpp/build --config Release --target llama-server -j 4
```

For an NVIDIA build, install a compatible NVIDIA driver and CUDA toolkit, then add `-DGGML_CUDA=ON` to the CMake configure command. You can also point the launcher at an existing compatible binary with `--server /path/to/llama-server`. See the [llama.cpp build guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md).

## Download and run

```bash
python3 sovereign.py download original
python3 sovereign.py serve original
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) and start a chat. To use the other profile, stop the running server with Ctrl+C and run these commands.

```bash
python3 sovereign.py download abliterated
python3 sovereign.py serve abliterated
```

Rerun an interrupted download to resume it. The launcher moves a complete download into place after verification. Run `python3 sovereign.py verify original` or `python3 sovereign.py verify abliterated` to check an existing managed file. Use `--model-dir /path/to/models` for a different download directory, or `serve PROFILE --model-file /path/to/model.gguf` for a GGUF you already have.

The default startup uses CPU inference and a 4,096-token context. Start with one model and allow additional RAM or VRAM for the context cache. For two CUDA GPUs with similar free memory, this example splits the model across them.

```bash
python3 sovereign.py serve original \
  --devices CUDA0,CUDA1 --tensor-split 1,1 --gpu-layers all
```

Run `python3 sovereign.py serve --help` for context size, port, and runtime options.

### Access a remote server

The server listens on loopback. From your own computer, keep this SSH command running and open [http://127.0.0.1:18080/](http://127.0.0.1:18080/).

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:18080:127.0.0.1:8080 user@server.example
```

Once loading finishes, `curl --fail --silent --show-error http://127.0.0.1:8080/health` on the server returns `{"status":"ok"}`. Check `/v1/models` for the active profile alias.

## Optional features

### Image input

```bash
python3 sovereign.py download original --vision
python3 sovereign.py serve original --vision
```

Attach an image in the chat and ask a question about it. Both profiles use the same pinned BF16 projector. Use `--mmproj /path/to/projector.gguf` for an existing compatible projector. The projector uses system RAM by default.

### Sovereign AI theme

With Node.js 22.12+ or 24+ and npm available, build the four-stripe theme from the pinned llama.cpp checkout.

```bash
python3 build-branding.py
python3 sovereign.py serve original --ui-dir .local/ui
```

### Web search and page reading

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-web.txt
.venv/bin/python sovereign.py serve original --web
```

In the WebUI, open **MCP** and enable the web tools for the chat. Ask for a recent public fact with source URLs. The search provider receives search queries, and the page reader sends requests to public HTTPS sites. Leave `--web` off for offline inference after setup.

The `--vision`, `--ui-dir`, and `--web` options can be combined with either profile.

## Upstream projects

The model weights, vision projector, runtime, and optional Python packages come from their respective projects. See [third-party notices](THIRD_PARTY_NOTICES.md) for sources and licenses.

