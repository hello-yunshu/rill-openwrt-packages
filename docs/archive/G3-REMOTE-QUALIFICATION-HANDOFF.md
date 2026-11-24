# G3 剩余资格门禁与远端操作审批范围

G3 未完成。本地资格不能替代 hosted 精确提交/run/attempt，也不能用旧资格 run 更新新代码的消费锁。

## 已有本地证据

- 六个 registry 目标 × Stable/Preview，共十二个真实 SDK 包；包/二进制/ELF/source lock/compiler/features/audit 身份已逐项检查。
- 十二份实际保留源树通过 immutable Git + 两补丁逐文件比较及额外输入拒绝检查。
- 六目标实际 SDK loader 执行消费者协议、反馈/持久化与 WASM trust/tamper 检查。
- 六目标隔离 opkg/apk Runtime owner 安装顺序、卸载重装与显式切换通过；x86_64 实包签名/index/package 负向及历史升级通过。
- PM Full 使用相同 Stable payload；五包实际 metadata 与六种 Full/split/Stable/Preview 安装组合通过。
- RP 52 项、PM 181 项测试通过；RP/CF/PM actionlint 通过。mock 测试中的合成 verdict 不作为真实资格。
- 证据索引：`docs/audits/g3-local-evidence/final-candidate/current-evidence-index.json`；PM 独立索引在其 `docs/audits/g3-runtime-package-evidence/index.json`。

## 当前真实源码边界

|仓库|当前 HEAD（另有未提交改动）|
|---|---|
|rill-ml|da8389fec7f879b826d8d17cbc6bb98c03ef8462|
|rill-openwrt-packages|64ee22f978ed8f8ed19bb675700678f57eec19e3|
|luci-app-cloudflare-ip|75f5a2d11c13c5d9aa46dfb8159259b2c94c73c5|
|luci-app-performance-manager|09e5f0f3fd3f18b4eaa153896a6b76895d9a78b5|

本地 qualification 标记 releaseEligible=false，发布验证器按预期拒绝 runId/runAttempt。CF 仍锁旧 Preview r2/run 33735123909，PM 仍锁旧 Stable r1/run 33479147529；没有伪造新身份。

## 需要另行授权的最小远端范围

1. 将经 diff 审查的本轮及其必要 G1/G2 前置改动按仓库提交到隔离候选分支并推送，不直接推 main、不 force push。保存精确 SHA。
2. 在候选分支创建 draft PR 供审查；PM 使用既定支持基线，不把其领先 main 的 84 个提交合并到 main，不恢复 read-only sync 的自动 PR。
3. 对新 package 候选 SHA 触发 `qualify.yml`，取得真正完成的双渠道十二包成功 run/attempt 与 manifest；检查该 run 的所有必需 job。失败则修复并重跑，不沿用本地或旧 run PASS。
4. 成功后用 canonical 同步器更新 CF Preview 与 PM Stable 的 owned lock 字段，保留 migration/未知字段；下载该 run 的实际 qualified bytes 执行对应消费者 CI。必要的候选分支推送、draft PR 更新与非发布 CI dispatch 同属此范围。
5. 本范围不包括 merge、tag、Release/feed 发布、权限/凭证变更、生产设备安装或代理配置写入。任何这类操作仍需单独授权。

原始 planning prompt 明确禁止 push、实际 PR 和远端工作流，因此当前只保存此可审查交接，不执行这些远端写入。远端资格及消费锁门禁保持 OPEN；G3 不标记完成。
