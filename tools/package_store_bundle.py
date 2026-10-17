#!/usr/bin/env python3
"""Build an *experimental* JB Store integration ZIP for JAILBREAK ME.

This is NOT a PS5 fPKG/PKG and not yet a drop-in stock JB Store ZIP:
the WebKit shortcut has no eboot.bin, and the browser cache requires
one-time installation. The package carries the real files and helper
ELF for a future JB Store handler. Never mislabel as 'fpkg'.
"""
from pathlib import Path
import argparse
import json
import hashlib
import zipfile

TITLE_ID = "WKAG00001"
VERSION = "0.4.0"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def package(upstream: Path, installer: Path, output: Path):
    assets = upstream / "assets"
    dist = upstream / "frontend/dist"
    required = {
        f"{TITLE_ID}/sce_sys/param.json": assets/"param.json",
        f"{TITLE_ID}/sce_sys/icon0.png": assets/"icon0.png",
        f"{TITLE_ID}/sce_sys/snd0.at9": assets/"snd0.at9",
        f"{TITLE_ID}/sce_sys/pic0.dds": assets/"pic0.dds",
        f"{TITLE_ID}/sce_sys/pic1.dds": assets/"pic1.dds",
        f"{TITLE_ID}/icon0.png": assets/"icon0.png",
        "installer/JAILBREAK-ME-CYBER-FASTBOOT_v0.4.0.elf": installer,
    }
    if not installer.is_file():
        raise FileNotFoundError(installer)
    if not dist.is_dir():
        raise FileNotFoundError(f"Missing staged offline web files: {dist}")
    for file in required.values():
        if not file.is_file() or not file.stat().st_size:
            raise FileNotFoundError(f"Missing required item: {file}")
    staged = sorted(p for p in dist.rglob("*") if p.is_file())
    if not any(p.name == "index.html" for p in staged):
        raise ValueError("Staged web cache resources contain no index.html")
    param = json.loads((assets/"param.json").read_text())
    if param.get("titleId") != TITLE_ID or param.get("applicationCategoryType") != 0:
        raise ValueError("Refusing bundle for unexpected title/category")

    manifest = {
        "schema": "jailbreak-me-store-bundle-v1",
        "name": "JAILBREAK ME",
        "version": VERSION,
        "title_id": TITLE_ID,
        "category": "game",
        "format": "zip",
        "packaging": "offline-browser-shortcut",
        "is_fake_pkg": False,
        "has_eboot_bin": False,
        "direct_install_supported_by_stock_jb_store": False,
        "requires_one_time_webkit_cache": True,
        "installer_elf": "installer/JAILBREAK-ME-CYBER-FASTBOOT_v0.4.0.elf",
        "future_store_install_steps": [
            "Run bundled installer helper in a jailbreak-capable context or implement the equivalent native privileged installer",
            "Register WKAG00001 title and its appmeta database rows",
            "Open http://127.0.0.1:18181/ using a one-time local server and cache all bundled offline resources",
            "Verify Game tile, background sound, icon, and WebKit launcher after reboot",
        ],
        "source": "https://github.com/Yahballon/JB_AUTOLOADER",
        "based_on": "itsPLK/ps5-webkit-autoloader v0.4.0, GPL-3.0",
        "files": {k: {"bytes": v.stat().st_size, "sha256": sha(v)}
                  for k, v in required.items()},
        "cache_file_count": len(staged)
    }
    guidance = f"""JAILBREAK ME v{VERSION} — EXPERIMENTAL JB STORE BUNDLE

This is a ZIP containing an offline WebKit shortcut payload and installer.
It is NOT an actual fPKG/PKG and is NOT directly installable by the
currently documented generic ZIP-to-eboot installer path.

Includes:
- {TITLE_ID}/sce_sys : title metadata, icon, sound, Game Hub artwork
- offline/*          : all compiled WebKit assets for one-time caching
- installer/*        : the tested PS5 installer ELF
- store/manifest.json: metadata for future store integration

Use the standalone .elf release for normal installation now.
A future JB Store integration must run the install helper internally,
or implement native game shortcut registration plus WebKit AppCache
population. A ZIP extraction alone does NOT perform these operations.

Never manually copy this package into /system_data or edit app.db.
Do not rename installer.elf to eboot.bin and claim it is a valid game.
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, p in required.items():
            z.write(p, name)
        for p in staged:
            z.write(p, "offline/" + p.relative_to(dist).as_posix())
        z.writestr("store/manifest.json", json.dumps(manifest, indent=2) + "\n")
        z.writestr("README-INSTALLATION.txt", guidance)
    with zipfile.ZipFile(output, "r") as z:
        bad = z.testzip()
        if bad:
            raise IOError(f"ZIP CRC mismatch for {bad}")
        assert f"{TITLE_ID}/sce_sys/param.json" in z.namelist()
        assert "store/manifest.json" in z.namelist()
    print(f"Created experimental store bundle: {output} ({output.stat().st_size:,} bytes), offline resources={len(staged)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    opt = parser.parse_args()
    package(opt.upstream, opt.installer, opt.output)
