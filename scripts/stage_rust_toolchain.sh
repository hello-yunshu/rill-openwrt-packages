#!/usr/bin/env bash
set -euo pipefail

: "${RUST_TOOLCHAIN:=1.94.0}"
: "${RUST_STAGING_DIR:?RUST_STAGING_DIR is required}"

rustc_path="$(rustup which rustc --toolchain "$RUST_TOOLCHAIN")"
cargo_path="$(rustup which cargo --toolchain "$RUST_TOOLCHAIN")"
rustc_version="$("$rustc_path" --version)"
[[ "$rustc_version" == rustc\ "$RUST_TOOLCHAIN"* ]]

install -d "$RUST_STAGING_DIR/bin"

write_wrapper() {
    local destination="$1"
    local real_binary="$2"
    local quoted_binary
    printf -v quoted_binary '%q' "$real_binary"
    printf '#!/usr/bin/env bash\nexec %s "$@"\n' "$quoted_binary" > "$destination"
    chmod 0755 "$destination"
}

write_wrapper "$RUST_STAGING_DIR/bin/rustc" "$rustc_path"
write_wrapper "$RUST_STAGING_DIR/bin/cargo" "$cargo_path"

echo "staged Rust toolchain: $rustc_version"
