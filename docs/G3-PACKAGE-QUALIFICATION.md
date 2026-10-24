# G3 包资格与跨仓库同步（执行中）

本轮尚未完成；不得把以下代码检查或历史包解析当成新候选包资格。

## 当前输入边界

- 包仓库基线：`64ee22f978ed8f8ed19bb675700678f57eec19e3`。
- G2 Preview 基线：`da8389fec7f879b826d8d17cbc6bb98c03ef8462` 加 G2 证据中绑定的本地改动。
- Stable 历史基线：`b990cd7043d313b0ff29c9693f091a94a5bdaf47` 加 G2 已验证的依赖安全补丁。
- 两个 recipe 保持各自既有不可变 upstream commit/archive pin，并依序应用 `patches/010-wasm-engine-security.patch` 与 `patches/020-archive-dependency.patch`。前者保持 G2 Wasmtime 修复字节，后者替换已撤回 ZIP 依赖并适配文件名 API；metadata 绑定各补丁摘要、base commit 和整个 patch set 应用后的最终 lock 摘要。不能声称旧 upstream tag 本身已修复。
- 当前 SDK 构建使用上述 canonical recipe，而非早期另存的 dirty-source 归档。资格收集器逐文件比较实际保留的 SDK 源码与 immutable Git tree 加声明补丁，另记录 patched tree 摘要。临时 dirty-source 归档不参与最终资格。
- 本地资格保持 `releaseEligible:false`；没有远端 run ID。后续新 package commit、真实资格 run/attempt 和消费端 lock 仍须单独取得证据。
- 禁止复用旧资格 run 为新源码或新二进制背书。本轮没有 push、PR、远端 dispatch、tag、Release、feed 发布或设备写入。

## 已复现及修改的缺口

1. Stable 同步的 no-op 会重置 package release；更新会丢失 metadata 扩展。保留了失败复现，现改为字节不变 no-op、owned 字段更新和双文件准备/失败回滚；故障注入覆盖第二次 replace 失败。
2. schema 2 Preview 汇总可缺少每目标包/二进制身份却通过 reader。schema 3 要求双渠道完整 registry 集合、真实包 metadata、包和 payload 摘要、ELF 身份、source lock、实际编译器与默认 WASM 特性、新鲜安全审计。
3. 产物命名只绑定 run、不绑定 attempt。生成与消费端均增加 attempt；旧 attempt 不能混入重跑资格。
4. 两个同步工作流缺少作者信息、分支/PR 幂等；CF base 指向旧开发分支。改为本地 bot author、有效 main、内容身份分支、已有分支/PR 检查，不 force push；关闭未合并 PR 要求人工复核。
5. CF 同版本集成使用当前 consumer job 重建的 Preview bytes。改为指定上游 run/attempt 的 qualified 包，先验证 manifest、package、binary 再使用。
6. 完整 Runtime 工具链仍固定 1.94。集中到 `metadata/build-toolchain.json` 的 1.96，保留默认 WASM；cache key 包含该身份。
7. Stable 与 Preview 共用 `/usr/bin/rill-runtime`，G2 证明 PM Stable wire 与 Preview 不可直接互换。两包明确互斥，候选 package release 分别递增为 Stable r2、Preview r3，避免覆盖既有不可变包身份。PM 保持兼容 Stable，不擅自切换 Preview 或合并其他开发分支。

## 证据与未完成门禁

临时执行根：`/tmp/cfip-g3`。完成后应整理可长期复核的证据索引。

- SDK：registry 的六个目标均已下载，并与官方 sha256sums 对照通过。下载镜像只提供传输；身份以官方摘要为准。
- 历史真实 IPK：新检查器已读取元数据、独立包/二进制摘要、ELF 架构与 interpreter；仅作为 parser 回归，不是新候选资格。
- 包仓库 Python 合同、本地 Git + stub gh 的幂等/权限失败/closed PR 测试已运行；最终数量以最后日志为准。
- CF artifact transport 单测及 G1 字段保留回归已运行。stub 网络/资格数据只证明校验器，不冒称真实 GitHub run。
- SDK 新候选双渠道十二包：真实编译、metadata、摘要、ELF、新鲜安全审计和 loader 运行通过；六目标均通过 Runtime owner 与切换。IPK/APK 签名正负向在 x86_64 实包执行。
- 已生成 x86_64 与 aarch64_generic 的 IPK 双渠道记录（四个包）。后续新鲜索引检查发现 `zip 2.4.2` yanked；这些记录现仅保留为旧候选的构建/身份/回归证据，不计入最终包资格，不能覆盖新的源码输入。
- 新不可变源码 + package commit + 成功 run/attempt + 消费端新 lock：OPEN。
- 相同 bytes 的 Runtime 集成、双渠道真实包管理器冲突与回退：本地通过。Release/feed schema 3 的远端精确提交/run/attempt 绑定仍 OPEN。
- 真实设备/持续运行：仍是后续阶段独立门禁。

## 本地运行与包管理器增量证据

可保留证据位于 `docs/audits/g3-local-evidence/partial-evidence-index.json`，包含各文件 SHA-256。该索引明确 `complete:false`、`releaseEligible:false`，不是可发布 qualification manifest。

- x86_64 实包解出的 Stable binary 通过 PM v3 handshake/health/decide/feedback、重复拒绝和重启持久化；Preview binary 通过 CF 反馈、完整生命周期、重启、inspect、延迟反馈与 context 隔离。通过 SDK musl loader 在隔离 Linux 容器执行，不冒称路由器验证。
- 两渠道均执行了带受信模型和 WASM handler 的真实 invoke；错误模型 key、错误 handler key、篡改 handler 各自拒绝，共六项负向。密钥仅为公开测试 fixture。
- Native 缺 Runtime、禁用不执行、不健康、状态超时与资源压力回退回归通过。这些是脚本集成检查，其模拟范围以原测试为准。
- 真实 opkg 对两种安装顺序拒绝另一个 owner，原 payload 摘要和独立用户状态保持；卸载/重装以及明确切换后返回也通过。`scripts/verify_ipk_ownership.py` 已进入资格工作流，对 registry 的 IPK 目标逐个执行。libc installed-DB 条目明确属于 dependency fixture，不代表 libc 或真实代理安装资格。
- 保留初次失败：Preview 已安装时尝试 Stable，opkg 文件冲突拒绝后会保留 `not-installed` 期望记录。此时卸载 Preview 后直接装回可能被该记录阻止，单纯 `opkg remove` 未安装包也不能清掉。已验证的无强制覆盖恢复是：移除当前 owner → 完成另一个包的显式安装 → 移除该包 → 安装原包。包脚本不递归调用包管理器，也不自动修改用户 DB。
- 使用实际新 Stable IPK 和 SDK 官方 opkg/usign 执行当前工作流的签名仓库事务：正确临时 key 可安装和卸载；缺 key、错 key、篡改 Packages、篡改 Packages.gz 均拒绝。libc 空包仅作依赖 fixture。APK 同类检查也通过，包含实际包损坏拒绝；均为隔离测试仓库，不代表正式签名或设备资格。

## 新鲜索引复查与尚在验证的依赖修复

- Filogic 双渠道编译完成，但收集器因 `warnings.yanked` 拒绝资格；原始报告见 `audit-full-diagnosis.json`。RustSec DB 为 `edb58f5974b83eb8302332821cb6d389777aa351`，漏洞数零并不代表可以忽略 registry 撤回警告。
- 原收集器使用全局 Cargo home，可能不能完整检查 SDK 锁文件在 crates.io 中的撤回状态。现改用 SDK 对应 Cargo home，保留原始 JSON/stderr，并将“无法检查索引”的 stderr error 也设为失败；历史四条摘要不能证明这一新增门禁已通过。
- crates.io API 的此次快照显示 `zip 2.x` 均已 yanked，唯一未撤回版本为 `9.0.3`（MSRV 1.88、MIT；上游 tag manifest 已复核）。该快照不是未来自动使用 latest 的授权。隔离候选升级只调整 ZIP 依赖及 `entry.name()?` 文件名 API 适配，Stable/Preview 仍分别保留原协议和状态语义。
- 隔离候选的新鲜审计为零漏洞、零警告、零 ignore；Runtime 的 Rust 1.96 默认 WASM 测试 Stable 114 项、Preview 119 项通过。更广的 workspace（明确排除 Python 扩展）Stable 1225 项、Preview 1230 项通过。未排除的首次 workspace 测试遇到 macOS Python 扩展链接失败，保留失败日志；不将其报告为整个 workspace 通过。
- 新候选已通过第二个独立 canonical patch 纳入两渠道，原 Wasmtime 补丁字节不变。最终 lock 为 `e6285fe82e14cc72d4257592a6e8bb1a3b7b977588f48c4413615d26071a92de`；新源树逐文件验证通过。源级证据另保存在 Rill 仓库 `docs/audits/g3-archive-evidence/manifest.json`。
- 新十二包已在独立 `output-final/` 完成构建与本地资格记录；hosted 资格仍 OPEN。只有同 SDK、同渠道、原 source path 的 Cargo target 可在 clean/prepare 后恢复；不共享 Stable/Preview target。新包仍须验证实际 source/lock/compiler/features、新鲜安全审计及 package/binary 摘要，不能沿用旧包的 PASS。
- 历史 APK 实包回归确认 SDK 会携带 `lib/apk/packages/<本包名>.list`。检查器仅允许该精确路径且内容必须恰为 `/usr/bin/rill-runtime` 一行；错 owner、多余路径和额外文件仍拒绝。包仓库最终合同测试 52 项通过；这一历史 APK 仅为 parser 回归，未冒称新包资格。

## 当前十二包证据（本地，尚未发布资格化）

当前索引：`docs/audits/g3-local-evidence/final-candidate/current-evidence-index.json`。早期 partial 索引是 ZIP 2 候选的历史记录。

- 十二条记录已逐包验证实际字节；全部保留源树通过额外输入拒绝检查。仅精确允许 SDK 生成目录、stamp、`.dep_files` 和数字 `version.date`，额外 Cargo 配置仍拒绝。
- 六目标的 Stable PM wire、Preview CF 生命周期/反馈/context 隔离，以及签名 WASM invoke 与六项 trust/tamper 拒绝均通过。
- x86_64 历史 IPK/APK 升级与卸载重装保持用户状态；APK 另验证旧 Runtime 实际训练产生的 generation 2 状态可由新 Runtime 重开。包脚本未执行，服务和设备迁移未验证。
- 本地 manifest 的实际源码/包身份通过；发布验证器按预期拒绝 releaseEligible、runId、runAttempt 三项，不能伪造远端身份。
- PM Full SDK APK 已构建，内含精确 Stable 字节，五包 metadata 检查通过；Full/split 与 Stable/Preview 六种真实安装顺序均通过拒绝冲突、保持 world/installed/payload、卸载重装保留用户状态；依赖使用实际 SDK 包，包脚本未执行。
- 新不可变 package commit、hosted 成功 run/attempt、消费者新锁和正式 feed/Release 仍 OPEN。G3 未完成。
