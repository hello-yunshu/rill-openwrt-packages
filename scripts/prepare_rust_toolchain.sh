#!/usr/bin/env bash
set -euo pipefail

# OpenWrt's released SDKs carry an older feed rustc.  The generic Rill Stable
# runtime deliberately keeps its declared MSRV and default WASM feature, so
# package qualification installs the supported compiler while retaining the
# OpenWrt rust-package.mk helper for cross flags, linker, and staging.
: "${RUST_TOOLCHAIN:=1.94.0}"
: "${RUST_TARGET:=x86_64-unknown-linux-musl}"
: "${RUSTUP_HOME:=/builder/rustup}"
: "${CARGO_HOME:=/builder/cargo}"
: "${RUST_STAGING_DIR:=}"

mkdir -p "$RUSTUP_HOME" "$CARGO_HOME/bin"
export RUSTUP_HOME CARGO_HOME

if [[ ! -x "$CARGO_HOME/bin/rustup" ]]; then
    curl --fail --silent --show-error --location --retry 3 \
        https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init \
        -o "$CARGO_HOME/rustup-init"
    chmod 0755 "$CARGO_HOME/rustup-init"
    "$CARGO_HOME/rustup-init" -y --no-modify-path --default-toolchain none
fi

export PATH="$CARGO_HOME/bin:$PATH"
rustup toolchain install "$RUST_TOOLCHAIN" --profile minimal --target "$RUST_TARGET" --no-self-update
rustc_path="$(rustup which rustc --toolchain "$RUST_TOOLCHAIN")"
cargo_path="$(rustup which cargo --toolchain "$RUST_TOOLCHAIN")"
[[ "$("$rustc_path" --version)" == rustc\ "$RUST_TOOLCHAIN"* ]]

if [[ -n "$RUST_STAGING_DIR" ]]; then
    install -d "$RUST_STAGING_DIR/bin"
    install -m 0755 "$rustc_path" "$RUST_STAGING_DIR/bin/rustc"
    install -m 0755 "$cargo_path" "$RUST_STAGING_DIR/bin/cargo"
fi

echo "prepared Rust toolchain: $("$rustc_path" --version)"
echo "target: $RUST_TARGET"
