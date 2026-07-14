# Paper 目录整理记录

## 整理日期

2026-06-01

## 整理前问题

- 缺少统一的日报目录、Gaussian fitting 方法目录和项目方法建议目录。
- 旧的主题目录可继续保留，但缺少统一自动化入口。

## 执行的操作

- 新增 daily_recommendations、02_methods_gaussian_fitting、08_project_method_notes、scripts、tests、config、data。
- 保留原有 PDF、旧 README 和主题目录，不执行危险迁移。

## 移动文件列表

| 原路径 | 新路径 | 原因 |
|---|---|---|
| 无 | 无 | 本次为非破坏性整理，仅新增目录和索引 |

## 未处理文件

- 旧主题目录暂不迁移，避免影响现有引用路径。

## 风险说明

- 未删除 PDF、原始数据、科研输出或核心算法文件。
- 若后续要做编号目录迁移，必须先复核所有引用路径和脚本。

## 后续建议

- 以后以 daily_recommendations、paper_master_index.* 和 02_methods_gaussian_fitting 作为主入口。