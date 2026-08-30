# Rill OpenWrt feed signing key

The production repository keys are intentionally provisioned outside Git. The
private keys belong only in the GitHub Environment secrets
`RILL_OPENWRT_IPK_SIGNING_KEY` and `RILL_OPENWRT_APK_SIGNING_KEY`; they must
never be committed, uploaded, or printed by Actions.

After the owner chooses the trust root, place the matching public key at
`keys/rill-openwrt-feed-usign.pub` and
`keys/rill-openwrt-feed-apk.pub`. The production workflow checks that each
secret matches its public key before signing. The files are published under
`/keys/` on Pages and are copied into `/etc/opkg/keys/` for OpenWrt 24.10 or
`/etc/apk/keys/` for OpenWrt 25.12.

For rotation, publish the replacement public key and fingerprint in a reviewed
commit, keep the old key only while all supported feeds are still signed by it,
then remove the old key after the documented overlap window. A missing or
mismatched key blocks production promotion; clients must not use
`--allow-untrusted` as a workaround.
