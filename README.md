# Rill OpenWrt Packages

面向 OpenWrt 的 Rill 通用 Runtime 打包仓库。这里负责将
[RillML](https://github.com/hello-yunshu/rill-ml) 的已发布 Stable 版本制作成
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
| 包名 | <code>rill-runtime</code> |
| 安装路径 | <code>/usr/bin/rill-runtime</code> |
| 上游来源 | RillML 已发布的 Stable tag archive |
| 当前来源版本 | <code>v1.5.6</code> |
| 当前上游 commit | <code>b990cd7043d313b0ff29c9693f091a94a5bdaf47</code> |
| 包许可证 | MIT |
| 包维护者 | Rill OpenWrt Packages maintainers |
| 分发 Release | [rill-runtime releases](https://github.com/hello-yunshu/rill-openwrt-packages/releases) |

它只分发通用 Runtime 可执行文件，不把 OpenWrt 产品逻辑塞进 Rill：

- 不安装 <code>rill-pack</code> 开发工具；
- 不包含 UCI、ubus、procd、firewall 或具体产品配置；
- 不直接修改宿主系统状态；
- 不替下游应用承担回滚、权限、服务编排和设备适配责任。

下游项目应固定本仓库的不可变 commit，并同时保存对应的
<code>qualification-evidence</code>；不能仅使用可移动的 <code>main</code> 或“最新
Release”作为运行时身份。

## OpenWrt Qualification 矩阵

GitHub Actions 的 canonical qualification workflow 当前覆盖以下组合：

| OpenWrt SDK | 架构 | 包格式 |
| --- | --- | --- |
| <code>24.10.8</code> | <code>x86_64</code> / <code>aarch64_generic</code> / <code>aarch64_cortex-a53</code> | IPK |
| <code>25.12.5</code> | <code>x86_64</code> / <code>aarch64_generic</code> / <code>aarch64_cortex-a53</code> | APK |

这张表只描述仓库实际执行过的 qualification 矩阵。其他架构、其他 OpenWrt
版本和真实设备必须单独构建、安装、运行并保存证据；当前矩阵只证明
x86_64、aarch64_generic 与 aarch64_cortex-a53 的包级 qualification，不能从存在 Rust target
或能够交叉编译推导出 MIPS、ARMv7 或其他设备架构已支持。

## 快速开始

### 在 OpenWrt SDK 中构建

请使用与目标 OpenWrt 版本匹配的 SDK，并先安装 Rust feed：

    ./scripts/feeds update packages
    ./scripts/feeds install rust
    cp -a /path/to/rill-openwrt-packages/package/rill-runtime package/rill-runtime
    echo 'CONFIG_PACKAGE_rill-runtime=y' >> .config
    make defconfig
    make package/rill-runtime/compile V=s

生成的 IPK 或 APK 位于 SDK 的 <code>bin/</code> 目录下。Release 发布后，实际生产使用时
应以本仓库的 immutable Release 及其中同一 qualification run 的
<code>qualification.json</code> 和 <code>SHA256SUMS</code> 为准；Actions artifact
不是长期软件源。

### 安装已构建的软件包

IPK 示例：

    opkg install ./rill-runtime_1.5.6-1_x86_64.ipk

APK 示例：

    apk add --allow-untrusted ./rill-runtime-1.5.6-r1.apk

安装后可检查：

    /usr/bin/rill-runtime --version

包的安装内容必须保持为 Runtime 主程序；不要把本地构建目录中的
<code>rill-pack</code> 或其他开发产物复制进设备。

## 版本与来源完整性

版本真相位于：

- <code>package/rill-runtime/Makefile</code>：包版本、release、上游 archive hash；
- <code>metadata/rill-runtime.json</code>：上游 tag、commit、archive SHA-256 和包身份；
- <code>scripts/check_upstream_version.py</code>：检查本仓库是否跟随已发布 Stable；
- <code>scripts/update_rill_version.py</code>：根据已发布 Stable 更新包版本和来源 hash。

本仓库不把动态 qualification 状态写进长期 metadata。qualification 状态属于
具体的 GitHub Actions run 和 artifact，避免“旧 metadata 看起来仍然通过”。

本地检查当前版本是否与上游 Stable 一致：

    python3 scripts/check_upstream_version.py --json

版本同步工作流支持定时运行、<code>repository_dispatch</code> 和手动触发。发现新 Stable
版本时，它会生成只修改包版本与来源元数据的自动 PR；同一 Stable SemVer 如果 tag
commit 或 archive hash 发生变化，检查和更新脚本会以 <code>MUTATED_STABLE</code>
失败，禁止静默改写来源身份。

架构能力与证据分层记录在 <code>metadata/architecture-capability.json</code>：package
保留 OpenWrt/Rust helper 的 all-arch build capability，当前 Actions 矩阵只是已验证
targets，设备运行证据仍单独记录。下游可使用 <code>scripts/verify_qualification.py</code> 校验 schema v1/v2 evidence，按
package commit、upstream identity、target identity、qualification state 和 release
eligibility 验证，不依赖固定 artifact 数量。

## Qualification 做什么

<code>.github/workflows/qualify.yml</code> 会：

1. 校验上游最新公开 Stable tag；
2. 使用官方 OpenWrt SDK 构建 IPK 和 APK；
3. 通过显式、可缓存且版本固定的 qualification toolchain contract（包括
   rustup-init SHA-256）准备 Rust host 工具链，不改变默认 Runtime feature；
4. 保留 OpenWrt <code>rust-package.mk</code> 的交叉编译、链接器和 staging 规则；
5. 检查包元数据、架构、版本和最终 payload；
6. 确认 payload 包含 <code>/usr/bin/rill-runtime</code>，且不包含 <code>rill-pack</code>；
7. 上传带包 SHA-256、上游 commit、来源 archive hash 和 run ID 的证据；成功的
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
4. 校验 artifact 中的包 SHA-256、版本、release、上游 commit 和 archive hash；
5. 再将包放入下游 SDK、镜像或设备发布流程。

包本身只提供通用 Runtime。宿主产品仍需自行验证其 RPC/LuCI/服务生命周期、
权限 ACL、配置迁移、回滚和真实硬件行为。

## OpenWrt feed

同一批已通过 qualification 的包也会按目录发布为独立 feed：

    https://hello-yunshu.github.io/rill-openwrt-packages/feed/<openwrt-version>/<target>/<subtarget>/<package-arch>/

OpenWrt 24.10 IPK 可将对应目录加入 customfeeds.conf 后运行 opkg update；
OpenWrt 25.12 APK 可将对应目录加入 APK repositories 后运行 apk update。
当前索引明确标记为 unsigned，manifest.json 中的 signing 状态不会伪造可信签名；
生产环境应在发布并分发受信任 repository key 后再启用强制签名校验。

Feed 由同一 qualification run 的包构建，部署前执行目录、索引和哈希校验；
只包含当前 6 个已验证 target，不构成对 package 更广泛 OpenWrt/Rust 架构能力的收窄。

## 目录说明

    package/rill-runtime/             canonical OpenWrt package recipe
    metadata/rill-runtime.json       immutable upstream/package provenance
    scripts/check_upstream_version.py Stable drift guard
    scripts/update_rill_version.py   Stable version update helper
    scripts/verify_qualification.py consumer qualification evidence verifier
    tests/test_upstream_guard.py  Stable provenance mutation tests
    scripts/verify_feed.py         feed layout and index verifier
    .github/workflows/qualify.yml    IPK/APK qualification and evidence
    .github/workflows/release.yml    exact-run Release promotion
    .github/workflows/feed.yml       GitHub Pages feed publication
    .github/workflows/sync-rill-version.yml
                                      scheduled/manual Stable drift PR

## 参与贡献

提交包或工作流修改时，请：

    git diff --check
    actionlint .github/workflows/qualify.yml
    actionlint .github/workflows/sync-rill-version.yml
    bash -n scripts/*.sh
    python3 -m py_compile scripts/*.py

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
