#!/usr/bin/env bash
set -euo pipefail

# OpenWrt released SDKs may carry an older feed rustc. The generic Rill Stable
# runtime keeps its MSRV and default WASM feature, so qualification installs the
# exact compiler while retaining rust-package.mk for cross flags and staging.
: "${RUST_TOOLCHAIN:=1.94.0}"
: "${RUSTUP_VERSION:=1.28.2}"
: "${RUSTUP_INIT_SHA256:=20a06e644b0d9bd2fbdbfd52d42540bdde820ea7df86e92e533c073da0cdd43c}"
: "${RUST_TARGET:=x86_64-unknown-linux-musl}"
: "${RUSTUP_HOME:=/builder/rustup}"
: "${CARGO_HOME:=/builder/cargo}"
: "${RUST_STAGING_DIR:=}"

mkdir -p "$RUSTUP_HOME" "$CARGO_HOME/bin"
export RUSTUP_HOME CARGO_HOME

if [[ ! -x "$CARGO_HOME/bin/rustup" ]]; then
    curl --fail --silent --show-error --location --retry 3 \
        "https://static.rust-lang.org/rustup/archive/${RUSTUP_VERSION}/x86_64-unknown-linux-gnu/rustup-init" \
        -o "$CARGO_HOME/rustup-init"
    printf '%s *%s\n' "$RUSTUP_INIT_SHA256" "$CARGO_HOME/rustup-init" | sha256sum -c -
    chmod 0755 "$CARGO_HOME/rustup-init"
    "$CARGO_HOME/rustup-init" -y --no-modify-path --default-toolchain none
fi

export PATH="$CARGO_HOME/bin:$PATH"
rustup toolchain install "$RUST_TOOLCHAIN" --profile minimal --target "$RUST_TARGET" --no-self-update
if [[ -n "$RUST_STAGING_DIR" ]]; then
    RUST_TOOLCHAIN="$RUST_TOOLCHAIN" RUST_STAGING_DIR="$RUST_STAGING_DIR" \
        "$GITHUB_WORKSPACE/scripts/stage_rust_toolchain.sh"
fi

rustc_path="$(rustup which rustc --toolchain "$RUST_TOOLCHAIN")"
echo "prepared Rust toolchain: $("$rustc_path" --version)"
echo "target: $RUST_TARGET"
