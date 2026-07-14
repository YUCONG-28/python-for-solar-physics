# Paper Daily Recommendation Workflow

这个仓库包含一个可本地执行的太阳射电文献检索、方法整理和论文项目资料库，服务于 `spikes topping type III`、`type III radio burst`、`Gaussian fitting / radio source centroid` 和 `AIA / radio` 联合分析。

## 当前主入口

- 每日运行脚本：`scripts\paper_daily_recommendation.ps1`
- 每日报告目录：`daily_recommendations\`
- 总索引：`paper_master_index.csv` 和 `paper_master_index.md`
- Gaussian 方法库：`02_methods_gaussian_fitting\`
- 项目方法建议：`08_project_method_notes\`
- 本地 PDF / 手稿归档：`00_local_documents\`

## 项目结构

- `00_local_documents/`：仅本地保存的 PDF、Word 手稿和博士论文归档；该目录不进入公开 Git 仓库。
- `02_methods_gaussian_fitting/`：Gaussian fitting、radio source centroid、source size 和 uncertainty 方法库。
- `08_project_method_notes/`：面向当前 DART / DRAT 分析代码的方法建议。
- `daily_recommendations/`：每日文献检索日报。
- `paper_master_index.csv` / `paper_master_index.md`：全局文献索引。
- `data/seed_papers.json`：可重复生成索引和日报的核心文献种子库。
- `scripts/`：日报生成脚本和 Windows 任务计划配置脚本。
- `tests/`：Pester 单元测试。
- `type_III_radio_bursts/`、`solar_radio_spikes/`、`AIA_observations/`、`DART_methods/`、`review_background/`：历史主题目录和背景入口。

## 本地资料边界

`00_local_documents/` 和 `.paper_recommendation_state.json` 只保存在本地，不是生成器的公开输入，也不会由发布流程暂存。可公开复现的源数据位于 `data/seed_papers.json` 和 `config/paper_search_config.json`；索引、日报和方法记录由脚本从这些源数据生成。

## 手动运行

在 PowerShell 中执行。默认只生成和验证本地文件，不提交、不推送：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\paper_daily_recommendation.ps1
```

若只使用内置种子库离线生成，不访问在线 API：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\paper_daily_recommendation.ps1 -SkipLiveSearch
```

只有在已经检查生成结果并明确要求发布时，才添加 `-CommitAndPush`：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\paper_daily_recommendation.ps1 -SkipLiveSearch -CommitAndPush
```

默认 Git 推送参数为：

```text
GitRemote = origin
GitBranch = main
```

可按需覆盖：

```powershell
.\scripts\paper_daily_recommendation.ps1 -CommitAndPush -GitRemote origin -GitBranch main
```

旧参数 `-SkipGitPush` 仅作为弃用兼容参数保留；由于默认已经是本地生成，它不会触发 Git 操作，也不应与 `-CommitAndPush` 同时使用。

## 自动检索说明

- 当前脚本会优先读取 `data\seed_papers.json` 中的核心文献。
- 若本地网络可用，且未加 `-SkipLiveSearch`，脚本会尝试访问 arXiv 和 Crossref。
- 若某个 API 请求失败，脚本会保留已有种子库并继续生成日报，不会删除已有索引。
- 默认生成模式不读取或修改 Git 索引。
- `-CommitAndPush` 会在生成前后检查统一仓库：任何已暂存内容或 `Paper/` 之外的变更都会终止发布。
- 发布只暂存 `data/seed_papers.json`、搜索配置以及日报、索引、Gaussian 方法记录和项目方法记录等明确白名单路径；不会使用 `git add -A`，不会执行 Git LFS push。
- 白名单路径没有实际变化时，不创建提交，也不执行 push。`Paper/` 内其他未列入白名单的修改会保留在本地，不会被提交。
- 当前实现没有声称已经在此环境中“每日后台运行”；若需要每日执行，请用下面的 Windows 任务计划配置。

## Windows 任务计划

1. 在管理员或当前用户 PowerShell 中运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_daily_task.ps1 -TaskName PaperDailyRecommendation -RunTime 08:30
```

2. 如果你更喜欢手动导入任务，可在任务计划程序中导入：

`scripts\paper_daily_recommendation_task.xml`

3. 导入后建议先手动运行一次任务，确认：

- `daily_recommendations\YYYY-MM-DD_paper_recommendations.md` 已生成；
- `paper_master_index.csv` 已更新；
- `02_methods_gaussian_fitting` 下的索引和方法文档已更新。

## 测试

当前提供了 Pester 单元测试：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Invoke-Pester .\tests\PaperRecommendation.Tests.ps1
```

## 维护建议

- 如果新增了确认可靠的核心论文，优先补进 `data\seed_papers.json`。
- 不要直接编辑可由生成器重建的总索引；先修改种子或搜索配置，再运行脚本并执行 Pester。
- 如果你获得了 NASA ADS API token，可以后续把 ADS 检索接到 `paper_daily_recommendation.ps1` 中。
- 如果后续要整理旧目录到编号目录，请先查看 `organization_log_YYYY-MM-DD.md`，不要直接移动历史 PDF、DOCX 或原始数据。
