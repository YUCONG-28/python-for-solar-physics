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

- `00_local_documents/`：本地 PDF、Word 手稿和博士论文归档；PDF/DOCX 通过 Git LFS 跟踪。
- `02_methods_gaussian_fitting/`：Gaussian fitting、radio source centroid、source size 和 uncertainty 方法库。
- `08_project_method_notes/`：面向当前 DART / DRAT 分析代码的方法建议。
- `daily_recommendations/`：每日文献检索日报。
- `paper_master_index.csv` / `paper_master_index.md`：全局文献索引。
- `data/seed_papers.json`：可重复生成索引和日报的核心文献种子库。
- `scripts/`：日报生成脚本和 Windows 任务计划配置脚本。
- `tests/`：Pester 单元测试。
- `type_III_radio_bursts/`、`solar_radio_spikes/`、`AIA_observations/`、`DART_methods/`、`review_background/`：历史主题目录和背景入口。

## Git LFS

本仓库使用 Git LFS 跟踪：

```text
*.pdf
*.docx
```

首次克隆后建议运行：

```powershell
git lfs install
git lfs pull
```

## 手动运行

在 PowerShell 中执行。默认情况下，脚本会在生成日报后自动提交生成文件并推送到 `origin/main`：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\paper_daily_recommendation.ps1
```

如果只想先用内置种子库离线生成文件，不访问在线 API，但仍自动提交和推送：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\paper_daily_recommendation.ps1 -SkipLiveSearch
```

如果只想本地生成文件，不提交也不推送：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\paper_daily_recommendation.ps1 -SkipLiveSearch -SkipGitPush
```

默认 Git 推送参数为：

```text
GitRemote = origin
GitBranch = main
```

可按需覆盖：

```powershell
.\scripts\paper_daily_recommendation.ps1 -GitRemote origin -GitBranch main
```

## 自动检索说明

- 当前脚本会优先读取 `data\seed_papers.json` 中的核心文献。
- 若本地网络可用，且未加 `-SkipLiveSearch`，脚本会尝试访问 arXiv 和 Crossref。
- 若某个 API 请求失败，脚本会保留已有种子库并继续生成日报，不会删除已有索引。
- 若未加 `-SkipGitPush`，脚本会要求运行前工作区干净；生成后若有变化，会自动 `git add -A`、提交 `Update paper recommendations for YYYY-MM-DD`，并推送到远端。
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
- 如果你获得了 NASA ADS API token，可以后续把 ADS 检索接到 `paper_daily_recommendation.ps1` 中。
- 如果后续要整理旧目录到编号目录，请先查看 `organization_log_YYYY-MM-DD.md`，不要直接移动历史 PDF、DOCX 或原始数据。
