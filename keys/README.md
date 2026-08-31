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

Current trust-root fingerprints:

- IPK/usign key ID: `952ac39212b3d7a0`
- IPK public-file SHA-256: `9a83a98365255a0e1b811c05e2b635a1c515ab2a850754a3235bc80520139688`
- APK public-file SHA-256: `f4b6d57dfad00cb8d4cc482e1d7c426acc6ca610876f1782593a2eee87cace1b`

Before trusting a production feed, compare these values with the checked-in
public files and verify the HTTPS repository URL. The private key material is
not recoverable from these fingerprints.

For rotation, publish the replacement public key and fingerprint in a reviewed
commit, keep the old key only while all supported feeds are still signed by it,
then remove the old key after the documented overlap window. A missing or
mismatched key blocks production promotion; clients must not use
`--allow-untrusted` as a workaround.
