include $(TOPDIR)/rules.mk

PKG_NAME:=rill-runtime
RILL_RECIPE_DIR:=$(dir $(realpath $(lastword $(MAKEFILE_LIST))))
RILL_SOURCE_VERSION_FILE:=$(if $(wildcard $(RILL_RECIPE_DIR)../../metadata/rill-runtime.json),$(RILL_RECIPE_DIR)../../VERSION)
RILL_VERSION_FILE:=$(firstword $(wildcard $(RILL_RECIPE_DIR)VERSION $(RILL_SOURCE_VERSION_FILE)))
PKG_VERSION:=$(strip $(shell cat "$(or $(RILL_VERSION_FILE),$(error Missing rill-runtime VERSION))"))
ifeq ($(PKG_VERSION),)
  $(error Empty rill-runtime VERSION)
endif
PKG_RELEASE:=11
PKG_LICENSE:=MIT
PKG_MAINTAINER:=Rill OpenWrt Packages maintainers
PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/hello-yunshu/rill-ml.git
PKG_SOURCE_VERSION:=50175cd54fce3a8b1cac77ec851dc468719181e8
PKG_SOURCE_SUBDIR:=rill-ml-$(PKG_SOURCE_VERSION)
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_SOURCE_SUBDIR)
RUST_PKG_LOCKED:=1
RILL_RUNTIME_LEGACY_PACKAGE:=rill-runtime-preview
# Allow the OpenWrt jobserver to share a bounded amount of Cargo parallelism.
# The qualification workflow starts GNU Make with nproc+1 jobs so the OpenWrt
# jobserver can share bounded parallelism with Cargo.
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/rust/rust-package.mk

define Build/Compile
	$(call Build/Compile/Cargo,crates/rill-runtime,--bin rill-runtime)
endef

define Package/rill-runtime
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Rill generic local runtime
  URL:=https://github.com/hello-yunshu/rill-ml
  DEPENDS:=+libc
  CONFLICTS:=$(RILL_RUNTIME_LEGACY_PACKAGE)
  EXTRA_DEPENDS:=$(if $(CONFIG_USE_APK),!$(RILL_RUNTIME_LEGACY_PACKAGE) (>=0))
  PROVIDES:=rill-runtime
endef

define Package/rill-runtime/description
Generic Rill Runtime packaged for OpenWrt. This distribution recipe installs
only the runtime executable from an immutable upstream Git commit promoted to
the Stable package channel.
It does not add OpenWrt product semantics or host mutation and does not install
the rill-pack development binary.
endef

define Package/rill-runtime/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/usr/share/rill
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/bin/rill-runtime $(1)/usr/bin/rill-runtime
	$(INSTALL_DATA) ./files/runtime-channel $(1)/usr/share/rill/runtime-channel
endef

define Package/rill-runtime/preinst
#!/bin/sh
# Preserve a Runtime binary unless the currently installed owner is Stable.
[ -n "$${IPKG_INSTROOT}" ] && exit 0
[ "$${PKG_UPGRADE:-0}" = 1 ] && exit 0
if [ -e /usr/bin/rill-runtime ] || [ -L /usr/bin/rill-runtime ]; then
	if command -v apk >/dev/null 2>&1; then
		apk info -e rill-runtime >/dev/null 2>&1 && exit 0
	elif command -v opkg >/dev/null 2>&1; then
		opkg status rill-runtime 2>/dev/null | grep -q '^Status:.*installed' && exit 0
	fi
	echo "rill-runtime: refusing to overwrite /usr/bin/rill-runtime with an unknown package owner" >&2
	exit 1
fi
exit 0
endef

$(eval $(call BuildPackage,rill-runtime))
