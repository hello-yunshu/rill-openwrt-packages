include $(TOPDIR)/rules.mk

PKG_NAME:=rill-runtime-preview
PKG_VERSION:=1.5.6
PKG_RELEASE:=2
PKG_LICENSE:=MIT
PKG_MAINTAINER:=Rill OpenWrt Packages maintainers
PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/hello-yunshu/rill-ml.git
PKG_SOURCE_VERSION:=da8389fec7f879b826d8d17cbc6bb98c03ef8462
PKG_SOURCE_SUBDIR:=rill-ml-$(PKG_SOURCE_VERSION)
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_SOURCE_SUBDIR)
RUST_PKG_LOCKED:=1
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/rust/rust-package.mk

define Package/rill-runtime-preview
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Rill generic local Preview runtime
  URL:=https://github.com/hello-yunshu/rill-ml
  DEPENDS:=+libc
  CONFLICTS:=rill-runtime
endef

define Package/rill-runtime-preview/description
Exact Preview Rill Runtime for qualified Cloudflare IP consumers. This package
is intentionally separate from the Stable rill-runtime package and installs
only the generic runtime executable.
endef

define Build/Compile
	$(call Build/Compile/Cargo,crates/rill-runtime,--bin rill-runtime)
endef

define Package/rill-runtime-preview/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/bin/rill-runtime $(1)/usr/bin/rill-runtime
endef

$(eval $(call BuildPackage,rill-runtime-preview))
