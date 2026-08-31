# Rill OpenWrt Packages

This repository packages the generic
[RillML](https://github.com/hello-yunshu/rill-ml) Runtime for OpenWrt. The
Chinese [README](README.md) is the primary documentation; this file is a
short English overview.

[![OpenWrt package qualification](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml/badge.svg?branch=main)](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Scope

The canonical package is <code>rill-runtime</code>. It is built from an immutable,
published RillML Stable archive and installs only:

    /usr/bin/rill-runtime

It does not install <code>rill-pack</code>, UCI/ubus/procd integration, product
configuration, firewall helpers, or host-mutation logic. Those responsibilities
belong to the consuming OpenWrt product.

Current provenance:

| Field | Value |
| --- | --- |
| Stable tag | <code>v1.5.6</code> |
| Upstream commit | <code>b990cd7043d313b0ff29c9693f091a94a5bdaf47</code> |
| Package release | <code>1.5.6-1</code> |
| License | MIT |

## Qualification matrix

The canonical qualification workflow generates its matrix from
[`metadata/openwrt-targets.json`](metadata/openwrt-targets.json), the single source of
truth for OpenWrt target, package architecture, package format, and Rust target.

Other targets require their own real build, installation, runtime, and
artifact evidence. This matrix proves package-level qualification only for
x86_64, aarch64_generic, and aarch64_cortex-a53; a Rust target or a cross-compilation result is not,
by itself, a support claim for MIPS, ARMv7, or another device architecture.

## Build

Use a matching OpenWrt SDK:

    ./scripts/feeds update packages
    ./scripts/feeds install rust
    cp -a /path/to/rill-openwrt-packages/package/rill-runtime package/rill-runtime
    echo 'CONFIG_PACKAGE_rill-runtime=y' >> .config
    make defconfig
    make package/rill-runtime/compile V=s

The official qualification workflow builds both package formats, checks the
final payload, and uploads immutable provenance evidence. The canonical
qualification path uses an explicit, cached, version-pinned Rust toolchain
contract together with OpenWrt's <code>rust-package.mk</code> helper. Architecture
capability is broader than the current automated qualification matrix; see
<code>metadata/architecture-capability.json</code> for the separate states.
Per-SDK caches cover downloads, Cargo/Rust inputs, and safe Rust target output;
the package build uses bounded <code>-j4</code> jobserver parallelism.

Check Stable drift locally:

    python3 scripts/check_upstream_version.py --json

Downstream consumers should pin an immutable commit, require a successful
qualification run, and verify its <code>qualification-evidence</code> artifact before
shipping a package. Successful runs are promoted without rebuilding into the
repository's immutable package Release. Cache hits only improve build time;
they are not release identity or qualification evidence.

## OpenWrt feed

The same qualified package artifacts are published as a directory-layout feed:

    https://hello-yunshu.github.io/rill-openwrt-packages/feed/<openwrt-version>/<target>/<subtarget>/<package-arch>/

The feed uses native OpenWrt signing formats: `Packages.sig` with `usign` for
24.10 and an apk-tools v3 EC repository key inside `packages.adb` for 25.12.
Production signing is enabled. Current trust-root fingerprints are documented in
`keys/README.md`; unsigned or development output is never promoted as a
production feed.

Example OpenWrt 24.10 configuration:

    echo 'src/gz rill https://hello-yunshu.github.io/rill-openwrt-packages/feed/24.10.8/x86/64/x86_64/' >> /etc/opkg/customfeeds.conf
    opkg update
    opkg install rill-runtime

Example OpenWrt 25.12 configuration:

    echo 'https://hello-yunshu.github.io/rill-openwrt-packages/feed/25.12.5/x86/64/x86_64/packages.adb' > /etc/apk/repositories.d/rill.list
    apk update
    apk add rill-runtime

After manually checking the public-key fingerprints under the Pages `keys/`
directory, install the usign key in `/etc/opkg/keys/` for 24.10 and the APK key
in `/etc/apk/keys/` for 25.12. Missing/wrong keys, tampered indexes, and
tampered packages must fail. Pages keeps `manifest.json`, `qualification.json`,
and `SHA256SUMS` so the feed remains auditable after Actions artifacts expire.

The feed is assembled from the exact qualification run and independently
verified for layout, indexes, and package hashes before GitHub Pages deployment.
It contains only the currently registered and qualified targets and does not narrow the
package's broader OpenWrt/Rust architecture capability.

## License

The package recipes, scripts, and workflows in this repository are released
under the [MIT License](LICENSE). Upstream RillML source and dependencies
remain subject to their own license declarations.

See the [Chinese README](README.md) for the full documentation.
