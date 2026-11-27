PKG_MAKEFILE_DIR:=$(dir $(abspath $(lastword $(MAKEFILE_LIST))))
include $(TOPDIR)/rules.mk

PKG_NAME:=rill-runtime-manager
include $(PKG_MAKEFILE_DIR)package-version.mk
PKG_RELEASE:=4
PKG_LICENSE:=MIT
PKG_MAINTAINER:=Rill OpenWrt Packages maintainers
include $(INCLUDE_DIR)/package.mk

define Package/rill-runtime-manager
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=Manage the shared Rill Runtime and consumer packages
  DEPENDS:=+libubox +jsonfilter +usign
  PKGARCH:=all
endef

define Package/rill-runtime-manager/description
Noarch rpcd service used by LuCI consumers to inspect and manage packages
from the preconfigured Yun OpenWrt feed. It never downloads keys, configures
repositories, executes arbitrary package names, or owns /usr/bin/rill-runtime.
endef

define Build/Compile
	:
endef

define Package/rill-runtime-manager/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/libexec
	$(INSTALL_BIN) ./files/usr/libexec/rpcd/rill-runtime-manager $(1)/usr/libexec/rpcd/
	$(INSTALL_BIN) ./files/usr/libexec/rill-runtime-manager $(1)/usr/libexec/
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d $(1)/usr/share/rill-runtime-manager
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/rill-runtime-manager.json $(1)/usr/share/rpcd/acl.d/
	$(INSTALL_DATA) ./files/usr/share/rill-runtime-manager/consumer-compatibility.schema.json $(1)/usr/share/rill-runtime-manager/
endef

$(eval $(call BuildPackage,rill-runtime-manager))
