# Rill OpenWrt Packages

This repository packages the generic
[RillML](https://github.com/hello-yunshu/rill-ml) Runtime for OpenWrt. The
Chinese [README](README.md) is the primary documentation; this file is a
short English overview.

[![OpenWrt package qualification](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml/badge.svg?branch=main)](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Scope

The canonical Stable package is <code>rill-runtime</code>. It is built from an immutable,
published RillML Stable archive and installs only:

    /usr/bin/rill-runtime

Cloudflare IP's Preview consumer uses the separately named
<code>rill-runtime-preview</code> package in this same repository. It is pinned
to the exact upstream commit in its metadata, installs the same binary path,
conflicts with Stable, and is built and checked for every registered target.
Consumer integration executes the binary extracted from that Preview artifact.

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

### Preview package (`rill-runtime-preview`)

The Preview channel is a separate package, `rill-runtime-preview`, which conflicts
with Stable `rill-runtime` (`CONFLICTS:=rill-runtime`, exposed as
`!rill-runtime>=0` in APK metadata). Preview builds ship through two channels: a
dedicated signed preview feed and GitHub Release assets. Because the Release tag is
derived from the Stable package release number, a preview build may live under a
Stable tag (for example `v1.5.6-r4`) while its own version is `1.5.6-r6`.

**Signed preview feed (recommended).** `qualify.yml` generates a per-target preview
index and uploads `rill-preview-feed-*` artifacts; `feed.yml` signs them when the
production signing keys are provisioned and publishes them to a separate
`preview/` channel that never writes to the production `feed/` channel:

    https://hello-yunshu.github.io/rill-openwrt-packages/preview/<openwrt-version>/<target>/<subtarget>/<package-arch>/

For OpenWrt 25.12.5 / x86_64:

    echo 'https://hello-yunshu.github.io/rill-openwrt-packages/preview/25.12.5/x86/64/x86_64/packages.adb' > /etc/apk/repositories.d/rill-preview.list
    apk update
    apk add rill-runtime-preview

It uses the same trust root as the production feed (`keys/`), so
`--allow-untrusted` is not needed. `preview/manifest.json` has `channel` set to
`preview` and `productionFeedEligible` permanently `false`.

**Release assets (one-off).** Release assets are qualification build outputs without
a feed index signature; `apk verify` reports `UNTRUSTED signature`. Installation
therefore requires accepting that trust gap explicitly:

    curl -fLO https://github.com/hello-yunshu/rill-openwrt-packages/releases/download/v1.5.6-r4/rill-runtime-preview-v25.12.5-x86_64.apk
    sha256sum rill-runtime-preview-v25.12.5-x86_64.apk
    # 544b113af904dfbe89fc5662b690d78a91828fecb5e130c37869f53ca9a8e10e
    apk add --allow-untrusted ./rill-runtime-preview-v25.12.5-x86_64.apk

This is a reproducible one-off installation path, not a long-term software source.

Installing the package does not enable the Rill integration. `/etc/config/cf_ip`
from `luci-app-cloudflare-ip` has no `rill` section by default (`mode=off`), so
the `rill-diagnostics` ubus call still reports `disabled`. This is a configuration
switch, not a missing package; enable Rill explicitly in the LuCI UI.

Rollback: `apk del rill-runtime-preview`.

## License

The package recipes, scripts, and workflows in this repository are released
under the [MIT License](LICENSE). Upstream RillML source and dependencies
remain subject to their own license declarations.

See the [Chinese README](README.md) for the full documentation.
