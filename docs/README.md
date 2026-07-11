# Documentation Index / 文档索引

Use the maintained architecture documents below for current behavior. Earlier
plans, audits, and phase reports are preserved under `history/` and are not the
current source of truth.

当前行为以以下维护文档为准。旧计划、审计和阶段报告统一保存在 `history/`，不再作为当前
架构依据。

## Current guidance / 当前指南

| Document | Purpose / 用途 |
| --- | --- |
| `../README.md` | Public overview, installation, and recommended commands. / 项目概览、安装与推荐命令。 |
| `../CODE_ORGANIZATION_MANIFEST.md` | Authoritative dependency and compatibility boundary. / 权威依赖与兼容边界。 |
| `FUNCTION_MAP.md` | Canonical implementation, CLI, and alias mapping. / 规范实现、CLI 与别名映射。 |
| `script_index.md` | Thin source-checkout entrypoints and installed commands. / 源码薄入口与安装命令。 |
| `quickstart.md` | Beginner-safe environment and smoke-test workflow. / 面向初学者的环境与冒烟流程。 |
| `MAIN_FILES.md` | Compact maintainer file map. / 维护者文件速查。 |
| `path_configuration.md` | Local path configuration without committed personal paths. / 不提交个人路径的本地配置方法。 |
| `validation/astropy_sunpy_reorg_parity.md` | Real-data structural parity evidence and exact exclusions. / 真实数据结构等价证据与未覆盖项。 |
| `README.zh-CN.md` | Additional Chinese overview. / 中文补充说明。 |

## History / 历史资料

- `history/general/`: earlier repository-wide plans, inventories, and refactor
  reports.
- `history/radio/`: earlier Radio phase reports, migration notes, and entrypoint
  snapshots.
- `data_download/event_20250124_inventory.md`: dated event-data inventory.

历史文件用于追溯决策，不应用来判断当前模块位置或推荐入口；遇到冲突时，以
`CODE_ORGANIZATION_MANIFEST.md` 与 `FUNCTION_MAP.md` 为准。

## Assets / 文档资源

- `assets/README.md`: reviewed asset policy.
- `assets/images/`: small reviewed documentation images.
- `assets/videos/`: small reviewed documentation videos.

Raw observations, bulk generated products, local spreadsheets, and personal
path configurations remain outside Git unless separately reviewed.

原始观测、大批量生成结果、本地表格和个人路径配置默认不进入 Git。
