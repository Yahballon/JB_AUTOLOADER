#!/usr/bin/env python3
"""Populate the standalone native JAILBREAK ME package build from trusted sources.

Called by experimental GitHub Actions job after cloning the PINNED DevBridge
native-app boilerplate and after downloading/verifying the latest known-good
JAILBREAK ME experimental ZIP. Writes to the local CI workspace only.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import zipfile
import shutil
import struct

TITLE_ID = "PPSA99767"
CONTENT_ID = "UP9000-PPSA99767_00-JAILBREAKMEPKG01"
assert len(CONTENT_ID) == 36


def install_stage(bridge: Path, this_repo: Path, bundle: Path):
    app = bridge / "app"
    target_main = app / "jbm-src/main.cpp"
    source_main = this_repo / "native-pkg/src/main.cpp"
    if not (app / "src/main.cpp").is_file() or not source_main.is_file():
        raise FileNotFoundError("Pinned DevBridge app source or new launcher source missing")
    source = source_main.read_text()
    for check in ("sceSystemServiceLaunchWebBrowser", "sceNetAccept", "/app0/assets/web", "BROWSER_LAUNCH"):
        if check not in source:
            raise ValueError("Missing launcher safety/feature check: " + check)
    target_main.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_main, target_main)
    shutil.copyfile(app/"src/startup.cpp", app/"jbm-src/startup.cpp")

    metadata_path = app / "sce_sys/param.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["titleId"] = TITLE_ID
    metadata["conceptId"] = TITLE_ID[-5:]
    metadata["contentId"] = CONTENT_ID
    metadata["contentVersion"] = "01.000.004"
    metadata["localizedParameters"]["en-US"]["titleName"] = "JAILBREAK ME"
    metadata["applicationCategoryType"] = 0
    metadata["contentBadgeType"] = 1
    metadata["applicationDrmType"] = "free"
    metadata.setdefault("gameIntent", {"permittedIntents":[{"intentType":"launchActivity"}]})
    metadata_path.write_text(json.dumps(metadata, indent=2)+"\n")

    shutil.copyfile(this_repo/"homebrew/ps5-webkit-autoloader-game/icon.png",
                    app/"sce_sys/icon0.png")
    assets = app / "assets/web"
    assets.mkdir(parents=True, exist_ok=True)
    count=0
    with zipfile.ZipFile(bundle) as z:
        if z.testzip() is not None:
            raise ValueError("Store asset ZIP failed CRC")
        manifest = json.loads(z.read("store/manifest.json"))
        if manifest["title_id"] != "WKAG00001" or manifest["version"] != "0.4.0":
            raise ValueError("Unexpected WebKit asset bundle title/version")
        if not manifest.get("cache_file_count"):
            raise ValueError("No offline files in bundle")
        # Keep all HTTP resources, but store them as ONE random-access file.
        # PS5 PKG NAPS layout has a limited 8-bit compression index.
        # Hundreds of individual WebKit files exceed that limit.
        # Each indexed path is served from web.dat by the native eboot.
        index_lines = []
        offset = 0
        with (app/"assets/web.dat").open("wb") as packed:
            for name in sorted(z.namelist()):
                if not name.startswith("offline/") or name.endswith("/"):
                    continue
                relative = name.removeprefix("offline/")
                if not relative or ".." in Path(relative).parts or "\t" in relative or "\n" in relative:
                    raise ValueError("Unsafe offline path: "+name)
                data = z.read(name)
                packed.write(data)
                index_lines.append(f"/{relative}\t{offset}\t{len(data)}\n")
                offset += len(data)
                count += 1
        (app/"assets/web-index.tsv").write_text("".join(index_lines), encoding="utf-8")
        print(f"Indexed {count} offline resources in {offset} bytes")
        if count != manifest["cache_file_count"]:
            raise ValueError(f"Offline files mismatch ({count} vs {manifest['cache_file_count']})")
        # Copy the artwork and audio from the EXACT tested store bundle.
        # This does not modify the original working WKAG00001 shortcut.
        # The previous shortcut's DDS is not in the exact native-app
        # validation profile. Preserve its ART by using the source PNG in
        # the PKG finalization stage, where the packager can emit BC7.
        (app/"sce_sys/snd0.at9").write_bytes(
            z.read("WKAG00001/sce_sys/snd0.at9"))
    paths=[line.split("\t", 1)[0] for line in (app/"assets/web-index.tsv").read_text().splitlines()]
    if "/app/index.html" not in paths or "/cache.appcache" not in paths:
        raise ValueError("Missing WebKit pointer/AppCache entrypoints")
    if not any(p.startswith("/app/") and p.endswith("/app.js") for p in paths):
        raise ValueError("No versioned WebKit app.js")
    print(f"Staged native prototype {TITLE_ID} with {count} offline browser files")
    print("Native browser API + server are UNTESTED on console; this ZIP is for test builds only")


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--bridge",type=Path,required=True)
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--bundle",type=Path,required=True)
    args=p.parse_args()
    install_stage(args.bridge.resolve(),args.repo.resolve(),args.bundle.resolve())
