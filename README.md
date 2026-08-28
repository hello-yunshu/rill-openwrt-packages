# Rill OpenWrt Packages

This repository is the independent OpenWrt distribution owner for the generic
`rill-runtime` package. It is intentionally separate from the RillML upstream
runtime source repository and from consumer product repositories.

The package is built from an immutable RillML Stable release archive, installs
only `/usr/bin/rill-runtime`, and never installs `rill-pack`, product-specific
configuration, UCI code, or host-mutation helpers. Consumers must pin this
repository to an immutable commit and must record the package and SDK evidence
for the OpenWrt release they qualify.

The qualification workflow covers x86_64 IPK on OpenWrt 24.10.5 and x86_64 APK
on OpenWrt 25.12.0. Other targets require separate real package evidence.
`scripts/check_upstream_version.py` is the fail-closed drift guard, while
`scripts/update_rill_version.py` updates only an immutable Stable tag archive.
