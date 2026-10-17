# JAILBREAK ME — Experimental Native PS5 Debug PKG

## Build status

The [experimental native PKG workflow](../.github/workflows/experimental-native-pkg.yml) successfully compiled a native PS5 `eboot.bin` using the proven toolchain in [PS5-DevBridge](https://github.com/Yahballon/PS5-DevBridge), built a genuine debug `.pkg` using pinned [LibProsperoPKG](https://github.com/SvenGDK/LibProsperoPKG), and verified that the output is a parseable `0x7F464948` (FIH) package.

**This is a prototype, not yet a console-tested or reliably auto-jailbreaking PS5 package.** It remains isolated on the `feature/native-pkg-autoboot-prototype` branch and does not change the previously working installer release or Game shortcut.

## Test artifact

[Download latest successful build](https://github.com/Yahballon/JB_AUTOLOADER/actions/runs/39027145194)

Under **Artifacts** download `EXPERIMENTAL-PS5-JAILBREAK-ME-NATIVE-PKG-UNTESTED`, unzip it, and use `JAILBREAK-ME-PPSA99767-EXPERIMENTAL.pkg`. The archive may also contain the PKG's original Content-ID-based filename, which is the same build.

- App title: **JAILBREAK ME**
- Prototype app Title ID: `PPSA99767`, separate from the existing tested WebKit launcher `WKAG00001`
- Content ID: `UP9000-PPSA99767_00-JAILBREAKMEPKG01`
- Browser URL: `http://127.0.0.1:18181/app/index.html`
- Offline asset bundle: `/app0/assets/web.dat` plus `/app0/assets/web-index.tsv` (306 WebKit resources)
- Diagnostic file (best effort): `/data/jailbreak-me-pkg/launch.log`

## Hardware test procedure

1. Use a **PS5 that already supports installing and launching debug/fake-signed homebrew packages**. This package cannot provide an initial jailbreak on an unmodified retail console; it is not official Sony software.
2. Download and install the experimental PKG using your existing supported PS5 package installer. Do not uninstall, replace or delete the already working `WKAG00001` shortcut.
3. Locate **JAILBREAK ME** under Games and launch it.
4. Observe whether the native local HTTP server binds to port `18181` and the platform service opens the PS5 browser automatically. If the WebKit page opens, observe whether the original offline exploit starts.
5. If the application hangs, refuses to install, opens no browser or does not start the exploit, share its console output and, if created, `/data/jailbreak-me-pkg/launch.log`. Relevant lines: `BOOT`, `SERVER_READY`, `BROWSER_LAUNCH`, `BROWSER_EXPORTS_UNAVAILABLE`, `USER_SERVICE_FAILED`, `SERVER_BIND_FAILED`.

**Known caveats:** DevBridge demonstrated `sceSystemServiceLaunchWebBrowser` from its privileged *payload service*. Direct invocation from a sandboxed `eboot.bin` is still unverified and may be denied. The PS5 may suspend a native app's local server when switching to the browser. Merely compiling a genuine debug PKG cannot guarantee browser navigation, memory exploit success, or cold-boot jailbreak operation. Future work should investigate these two runtime behaviors using PS5 logs before a stable release.

## Build from source

The native PS5 launcher source is in [`native-pkg/src/main.cpp`](../native-pkg/src/main.cpp), offline asset packer in [`native-pkg/tools/stage_native.py`](../native-pkg/tools/stage_native.py), and the .NET PKG build frontend in [`native-pkg/packager`](../native-pkg/packager/). The workflow pins the exact DevBridge and LibProsperoPKG revisions, verifies the published WebKit asset bundle via SHA256, builds a valid app, then packages it as a debug PS5 PKG.

The known-good ELF installer and its published `v0.4.0-cyber-fastboot` GitHub Release remain unchanged until this version passes real-hardware testing.
