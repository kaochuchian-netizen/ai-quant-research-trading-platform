#!/usr/bin/env python3
"""Install the governed open-source CJK capture font in user scope."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

URL = "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
SHA256 = "dce08bd4fd91aa8aa76ed8fea4b694c2dfb8550f67871e326843212ddbeb88b4"
ROOT = Path.home() / ".cache/stock-ai-fonts/noto-cjk-tc"
FONT = ROOT / "NotoSansCJKtc-Regular.otf"
CONFIG = ROOT / "fonts.conf"


def install(root: Path = ROOT) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    font = root / FONT.name
    config = root / CONFIG.name
    if not font.is_file() or hashlib.sha256(font.read_bytes()).hexdigest() != SHA256:
        temporary = font.with_suffix(".download")
        with urllib.request.urlopen(URL, timeout=60) as response:
            temporary.write_bytes(response.read())
        actual = hashlib.sha256(temporary.read_bytes()).hexdigest()
        if actual != SHA256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"CJK_FONT_HASH_MISMATCH:{actual}")
        temporary.replace(font)
    config.write_text(
        "<?xml version='1.0'?>\n<!DOCTYPE fontconfig SYSTEM 'fonts.dtd'>\n"
        f"<fontconfig><dir>{root}</dir><alias><family>sans-serif</family>"
        "<prefer><family>Noto Sans CJK TC</family></prefer></alias></fontconfig>\n",
        encoding="utf-8",
    )
    return {
        "status": "READY", "contract_version": "cjk_capture_font_runtime_v1",
        "font_family": "Noto Sans CJK TC", "font_path": str(font),
        "font_sha256": hashlib.sha256(font.read_bytes()).hexdigest(),
        "font_size": font.stat().st_size, "fontconfig_file": str(config),
        "license": "SIL Open Font License 1.1", "source": URL,
        "system_packages_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = install(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
