# Rill OpenWrt Packages

This repository packages the generic [RillML](https://github.com/hello-yunshu/rill-ml) Runtime for OpenWrt. The Chinese [README](README.md) is the primary documentation.

## Scope

The only current package channel is Stable `rill-runtime`, which installs `/usr/bin/rill-runtime`. It does not install `rill-pack`, UCI/ubus/procd integration, product configuration, firewall helpers, or host-mutation logic.

| Field | Value |
| --- | --- |
| Upstream Runtime version | `1.5.6` |
| Pinned upstream commit | `1e962a82443088229714877eee98617f1596eee8` |
| OpenWrt package version | `1.5.6-r10` |
| Rust toolchain | `1.96.0` |

Older devices may still have the retired `rill-runtime-preview` package installed. It shares the Runtime binary path and conflicts with `rill-runtime`; the Runtime manager detects it as a legacy migration state. New qualification, feed, and Release artifacts contain only `rill-runtime`.

## Qualification

The canonical target matrix comes from [`metadata/openwrt-targets.json`](metadata/openwrt-targets.json). It covers the registered OpenWrt 24.10.8 IPK and 25.12.6 APK targets. A registry entry is a required build target, not a claim that an untested device architecture is supported.

Build with a matching OpenWrt SDK and Rust feed:

    ./scripts/feeds update packages
    ./scripts/feeds install rust
    cp -a /path/to/rill-openwrt-packages/package/rill-runtime package/rill-runtime
    echo 'CONFIG_PACKAGE_rill-runtime=y' >> .config
    make defconfig
    make package/rill-runtime/compile V=s

Qualification evidence uses schema 4 and contains one `package`, top-level `upstream` and `build` provenance, and top-level `targets`. Release qualification builds and inspects only the canonical Stable package.

Check whether the exact pinned source commit still matches upstream main:

    python3 scripts/check_upstream_version.py --json

If upstream main advances, review and pin its exact commit, increment the OpenWrt package release, then qualify that package before promotion.

## Installation

New installations should use the signed unified Yun feed at:

    https://hello-yunshu.github.io/yun-openwrt-packages/<openwrt-version>/<package-arch>/

For example, with the feed and trust key already configured:

    opkg install rill-runtime
    # or on APK-based OpenWrt:
    apk add rill-runtime

The Runtime manager does not add feed sources, download keys, or bypass signature checks. Remove retired Rill `/feed/` or `/preview/` repository entries before managing packages through the unified source.

## License

Package recipes, scripts, and workflows are licensed under [MIT](LICENSE). Upstream RillML source and dependencies retain their own license terms.
