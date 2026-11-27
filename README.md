# Rill OpenWrt Packages

面向 OpenWrt 的 Rill 通用 Runtime 打包仓库。这里负责将
[RillML](https://github.com/hello-yunshu/rill-ml) 的固定 Git commit 制作成
可审计、可复现、可供下游消费的 OpenWrt 软件包。

> 中文文档是本文档的主体；[English README](README.en.md) 提供简要英文说明。

[![OpenWrt package qualification](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml/badge.svg?branch=main)](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml)
[![Check Rill Stable package drift](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/sync-rill-version.yml/badge.svg?branch=main)](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/sync-rill-version.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 仓库定位

本仓库是独立的 OpenWrt distribution/package owner，与 RillML 上游源码仓库、
以及具体的宿主产品仓库分离。当前维护的 canonical package 是：

| 项目 | 内容 |
| --- | --- |
| Stable 包名 | <code>rill-runtime</code> |
| 安装路径 | <code>/usr/bin/rill-runtime</code> |
| 上游来源 | RillML upstream main 的 immutable commit |
| 当前来源版本 | <code>1.5.6</code> |
| 当前上游 commit | <code>50175cd54fce3a8b1cac77ec851dc468719181e8</code> |
| 当前包版本 | <code>1.5.6-r11</code> |
| 包许可证 | MIT |
| 包维护者 | Rill OpenWrt Packages maintainers |
| 分发 Release | [rill-runtime releases](https://github.com/hello-yunshu/rill-openwrt-packages/releases) |

当前只发布一个 canonical Stable 包 <code>rill-runtime</code>。它固定到上游 main commit
<code>50175cd54fce3a8b1cac77ec851dc468719181e8</code>，使用 Rust 1.96.0 构建。
旧设备上可能仍安装有历史 <code>rill-runtime-preview</code>；manager 会识别该包作为迁移状态。
新资格、feed 和 Release 均只包含 <code>rill-runtime</code>。

它只分发通用 Runtime 可执行文件，不把 OpenWrt 产品逻辑塞进 Rill：

- 不安装 <code>rill-pack</code> 开发工具；
- 不包含 UCI、ubus、procd、firewall 或具体产品配置；
- 不直接修改宿主系统状态；
- 不替下游应用承担回滚、权限、服务编排和设备适配责任。

下游项目应固定本仓库的不可变 commit，并同时保存对应的
<code>qualification-evidence</code>；不能仅使用可移动的 <code>main</code> 或“最新
Release”作为运行时身份。

## OpenWrt Qualification 矩阵

GitHub Actions 的 canonical qualification workflow 从
[`metadata/openwrt-targets.json`](metadata/openwrt-targets.json) 生成矩阵；该文件是
OpenWrt Runtime target、package arch、package format 和 Rust target 的唯一事实来源。

这张表只描述仓库实际执行过的 qualification 矩阵。其他架构、其他 OpenWrt
版本和真实设备必须单独构建、安装、运行并保存证据；当前矩阵覆盖
x86_64、aarch64_generic、aarch64_cortex-a53/a72/a76 和
arm_cortex-a7_neon-vfpv4，不能从存在 Rust target 或能够交叉编译推导出
其他设备架构已支持。

## 快速开始

### 在 OpenWrt SDK 中构建

请使用与目标 OpenWrt 版本匹配的 SDK，并先安装 Rust feed：

    ./scripts/feeds update packages
    ./scripts/feeds install rust
    cp -a /path/to/rill-openwrt-packages/package/rill-runtime package/rill-runtime
    cp /path/to/rill-openwrt-packages/VERSION package/rill-runtime/VERSION
    echo 'CONFIG_PACKAGE_rill-runtime=y' >> .config
    make defconfig
    make package/rill-runtime/compile V=s

仓库根目录的 `VERSION` 管理 Runtime 版本。管理器独立发布版本，由
`package/rill-runtime-manager/VERSION` 管理。两者的 OpenWrt 包修订号仍由各自的
`PKG_RELEASE` 管理。

生成的 IPK 或 APK 位于 SDK 的 <code>bin/</code> 目录下。Release 发布后，实际生产使用时
应以本仓库的 immutable Release 及其中同一 qualification run 的
<code>qualification.json</code> 和 <code>SHA256SUMS</code> 为准；Actions artifact
不是长期软件源。

### 安装已构建的软件包

IPK 示例：

    opkg install rill-runtime

APK 示例：

    apk add rill-runtime

生成的 IPK 文件名形如 `rill-runtime_1.5.6-8_x86_64.ipk`；Release 资产使用目标限定名。安装后可检查：

    /usr/bin/rill-runtime --version

包的安装内容必须保持为 Runtime 主程序；不要把本地构建目录中的
<code>rill-pack</code> 或其他开发产物复制进设备。

### 历史 Preview 包迁移

历史版本曾单独发布 <code>rill-runtime-preview</code>，并与 <code>rill-runtime</code>
共享二进制路径，因此两者互斥。当前已取消 Preview 包发布，唯一新包名是
<code>rill-runtime</code>。设备上若仍安装旧 Preview 包，manager 会显示 `legacy-runtime-migration-required` 并拒绝
自动替换；先显式卸载旧包，再安装 Stable。包管理器不会同时安装两个都声明拥有
<code>/usr/bin/rill-runtime</code> 的包。

Runtime 与 PM/CFI 消费包继续从已配置并验证的 Yun 统一 feed 安装或更新。

## 版本与来源完整性

版本真相位于：

- <code>package/rill-runtime/Makefile</code>：包版本、release、固定上游 Git commit；
- <code>metadata/rill-runtime.json</code>：上游 immutable commit、来源类型和包身份；
- <code>scripts/check_upstream_version.py</code>：检查本仓库是否跟随已发布 Stable；
- <code>scripts/update_rill_version.py</code>：用于历史 tag 版本同步（当前 stable-main pin 由人工审阅更新）。

本仓库不把动态 qualification 状态写进长期 metadata。qualification 状态属于
具体的 GitHub Actions run 和 artifact，避免“旧 metadata 看起来仍然通过”。

本地检查当前 pin 是否仍为上游 main：

    python3 scripts/check_upstream_version.py --json

来源检查会将 metadata 中固定的 commit 与当前 upstream main 对比。上游 main 前进时，
需要审阅精确 commit、包修订号和 qualification 后再更新 pin。

架构能力与证据分层记录在 <code>metadata/architecture-capability.json</code>：package
保留 OpenWrt/Rust helper 的构建能力；<code>metadata/openwrt-targets.json</code> 中的
12 个 release/architecture 组合是自动资格矩阵，不代表单凭列入 registry 就已有可发布
包。Release 资格要求唯一 Stable 包的每一项实际 SDK 包构建、ELF/ABI、元数据和
来源证据全部通过；设备运行资格仍单独记录。下游应使用
<code>scripts/verify_qualification.py</code> 校验 schema v4 的单 Stable 逐目标证据、实际包
字节和 release eligibility。

## Qualification 做什么

<code>.github/workflows/qualify.yml</code> 会：

1. 校验 metadata 固定的 upstream main commit；
2. 按 registry 为 OpenWrt 24.10.8 与 25.12.6 的每个 target 下载对应官方 SDK；24.10
   构建 IPK，25.12 构建 APK；
3. 通过显式、可缓存且版本固定的 qualification toolchain contract（包括
   rustup-init SHA-256）准备 Rust host 工具链，不改变默认 Runtime feature；
4. 保留 OpenWrt <code>rust-package.mk</code> 的交叉编译、链接器和 staging 规则；
5. 检查包元数据、ELF class/machine/ABI、musl interpreter、版本和最终 payload；
6. 确认 payload 包含 <code>/usr/bin/rill-runtime</code>，且不包含 <code>rill-pack</code>；
7. 上传带包 SHA-256、上游 commit 和 run ID 的证据；成功的
   qualification run 随后由独立 promotion workflow 原样提升为 package Release。

工作流会按 OpenWrt SDK 分支缓存可复用的下载内容、Cargo/Rust 输入以及安全范围内的
Rust target 编译结果，并通过 OpenWrt jobserver 以 <code>-j4</code> 运行包构建。cache
和并行编译只用于加速，不构成发布身份或 qualification 证据。cache miss、queued run
或 in-progress run 都不能被当作通过。

## 下游消费约定

建议下游按以下顺序消费：

1. 固定 <code>rill-openwrt-packages</code> 的完整 commit SHA；
2. 检查该 commit 的 OpenWrt qualification workflow 为 <code>completed/success</code>；
3. 下载同一 run 的 <code>qualification-evidence</code>；
4. 校验 artifact 中的包 SHA-256、版本、release 和上游 commit；
5. 再将包放入下游 SDK、镜像或设备发布流程。

包本身只提供通用 Runtime。宿主产品仍需自行验证其 RPC/LuCI/服务生命周期、
权限 ACL、配置迁移、回滚和真实硬件行为。

## OpenWrt feed

兼容期内，<code>feed.yml</code> 仍将同一批已通过 qualification 的包发布到 Rill
旧 feed。这个 feed 不再是新安装的推荐入口：

    https://hello-yunshu.github.io/rill-openwrt-packages/feed/<openwrt-version>/<target>/<subtarget>/<package-arch>/

OpenWrt 24.10 IPK 可将对应目录加入 customfeeds.conf 后运行 opkg update；
OpenWrt 25.12 APK 可将对应目录加入 APK repositories 后运行 apk update。
Feed 采用 OpenWrt 原生签名格式：24.10 的 `Packages.sig` 使用 `usign`，25.12
的 `packages.adb` 使用 apk-tools v3 的 EC repository key。Production signing
已启用；当前 trust-root fingerprint 位于 `keys/README.md`，unsigned 或
development output 永远不会被提升为 production feed。

**新安装使用 Yun 统一源**，不再添加 Rill 专属 source：

    # OpenWrt 24.10 / IPK
    echo 'src/gz yun-openwrt https://hello-yunshu.github.io/yun-openwrt-packages/24.10.8/x86_64/' >> /etc/opkg/customfeeds.conf
    opkg update
    opkg install rill-runtime

    # OpenWrt 25.12 / APK
    echo 'https://hello-yunshu.github.io/yun-openwrt-packages/25.12.6/x86_64/packages.adb' > /etc/apk/repositories.d/yun-openwrt.list
    apk update
    apk add rill-runtime

按 Yun feed 的信任引导说明安装并核验公钥：24.10 的 usign key 以 key ID 命名，位于
`/etc/opkg/keys/e58db45ab792599d`，25.12 的 APK key 位于
`/etc/apk/keys/yun-feed.rsa.pub`。Runtime manager 不会自动下载公钥、添加源或绕过签名校验。
旧 Rill Pages 保留独立签名和 provenance，仅供迁移中的既有配置使用。

Feed 由同一 qualification run 的包构建，部署前执行目录、索引和哈希校验；
只包含 `metadata/openwrt-targets.json` 中当前启用且已验证的 target，不构成对
package 更广泛 OpenWrt/Rust 架构能力的收窄。

## 目录说明

    package/rill-runtime/             canonical OpenWrt package recipe
    metadata/rill-runtime.json       immutable upstream/package provenance
    scripts/check_upstream_version.py Stable drift guard
    scripts/update_rill_version.py   Stable version update helper
    scripts/verify_qualification.py consumer qualification evidence verifier
    tests/test_upstream_guard.py  Stable provenance mutation tests
    scripts/verify_feed.py         feed layout, semantic index and signature verifier
    scripts/build_feed_manifest.py durable feed provenance generator
    scripts/sign_feed.py            exact qualified-byte signing helper
    scripts/release_identity.py     immutable Release identity comparator
    keys/README.md                  key lifecycle and provisioning contract
    .github/workflows/qualify.yml    IPK/APK qualification and evidence
    .github/workflows/release.yml    exact-run Release promotion
    .github/workflows/feed.yml       GitHub Pages feed publication
    .github/workflows/repository-contract.yml
                                      lightweight repository contract checks
    .github/workflows/sync-rill-version.yml
                                      scheduled/manual Stable drift PR

## 参与贡献

提交包或工作流修改时，请：

    git diff --check
    actionlint .github/workflows/qualify.yml
    actionlint .github/workflows/sync-rill-version.yml
    bash -n scripts/*.sh
    python3 -m py_compile scripts/*.py
    python3 -m unittest discover -s tests -v

涉及包内容、版本来源或 qualification 的修改，应在 PR 描述中说明：

- 修改的 OpenWrt 版本和架构；
- 上游 RillML tag/commit；
- 是否改变了最终 payload；
- 对应的本地检查和 GitHub Actions run。

## 许可证

本仓库的打包配方、脚本和工作流以 [MIT License](LICENSE) 发布。上游 RillML
源码及其依赖仍分别受各自仓库和 crate 声明的许可证约束。

## 相关链接

- [RillML 上游仓库](https://github.com/hello-yunshu/rill-ml)
- [RillML v1.5.6 Stable release](https://github.com/hello-yunshu/rill-ml/releases/tag/v1.5.6)
- [OpenWrt SDK](https://openwrt.org/docs/guide-developer/toolchain/install-buildsystem)
- [Actions qualification](https://github.com/hello-yunshu/rill-openwrt-packages/actions/workflows/qualify.yml)
- [English README](README.en.md)
