#!/usr/bin/env python3
"""Build the Sovereign AI theme in a temporary copy of llama.cpp's WebUI."""

import argparse
import json
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent


def replace_once(source: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, source)
    if count != 1:
        raise ValueError("Unexpected llama.cpp WebUI layout. Use the revision in the README.")
    return updated


def apply_theme(ui: Path) -> None:
    logo = ui / "src/lib/assets/logo.svg"
    shutil.copyfile(ROOT / "sovereign-logo.svg", logo)

    constants = ui / "src/lib/constants/pwa.constants.ts"
    content = constants.read_text(encoding="utf-8")
    start = content.index("export const FAVICON_COLORS")
    end = content.index("} as const;", start)
    colors = content[start:end]
    colors = replace_once(colors, r"(DARK:\s*)['\"][^'\"]*['\"]", r"\g<1>'#ffffff'")
    colors = replace_once(colors, r"(LIGHT:\s*)['\"][^'\"]*['\"]", r"\g<1>'#000000'")
    content = replace_once(
        content[:start] + colors + content[end:],
        r"(\bFAVICON_PADDING:\s*)[0-9.]+", r"\g<1>0",
    )
    constants.write_text(content, encoding="utf-8")

    package = ui / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    scripts = data["scripts"]
    scripts["build-pwa-assets"] = replace_once(
        scripts["build-pwa-assets"],
        r"node scripts/make-icons-circular\.js(?:\s+--scale-pct\s+\d+)?",
        "node scripts/make-icons-circular.js --scale-pct 100",
    )
    package.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")


def validate_ui(output: Path) -> None:
    if not (output / "index.html").is_file():
        raise ValueError("The WebUI build did not produce index.html.")
    manifest = json.loads((output / "manifest.webmanifest").read_text(encoding="utf-8"))
    if any(manifest.get(key) != "Sovereign AI" for key in ("name", "short_name")):
        raise ValueError("The generated manifest does not have the Sovereign AI name.")
    for filename in ("favicon.svg", "favicon-dark.svg"):
        svg = ET.parse(output / filename)
        if len(svg.findall(".//{http://www.w3.org/2000/svg}path")) != 4:
            raise ValueError(f"The generated {filename} does not have four stripes.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-dir", type=Path, default=ROOT / "llama.cpp")
    parser.add_argument("--out", type=Path, default=ROOT / ".local/ui")
    args = parser.parse_args()
    source = args.llama_dir.expanduser().resolve() / "tools/ui"
    destination = args.out.expanduser().resolve()
    if not (source / "package-lock.json").is_file():
        parser.error(f"Missing llama.cpp WebUI source at {source}.")
    if destination.exists():
        parser.error(f"{destination} already exists. Choose a new --out directory.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns(
        ".git", "node_modules", ".svelte-kit", "build", "dist", ".env", ".env.*", ".npmrc",
    )
    try:
        with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
            stage = Path(directory)
            ui = stage / "source"
            output = stage / "built"
            shutil.copytree(source, ui, ignore=ignore)
            apply_theme(ui)
            env = os.environ | {
                "VITE_PUBLIC_APP_NAME": "Sovereign AI",
                "LLAMA_UI_OUT_DIR": str(output),
                "LLAMA_BUILD_NUMBER": "b11674",
            }
            subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=ui, check=True)
            subprocess.run(["npm", "run", "build"], cwd=ui, env=env, check=True)
            validate_ui(output)
            output.rename(destination)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Branding build failed: {error}\n")
    print(f"WebUI ready at {destination}")


if __name__ == "__main__":
    main()

