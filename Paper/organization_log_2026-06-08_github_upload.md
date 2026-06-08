# Paper 目录整理记录

## 整理日期

2026-06-08

## 整理前问题

- 根目录同时包含文献 PDF、博士论文、Word 手稿、日报、索引和自动化脚本，上传 GitHub 后不利于快速判断项目入口。
- 当前最大 PDF 约 93 MB，接近 GitHub 普通 Git 单文件 100 MB 限制，需要 Git LFS 管理。
- 现有科研脚本、索引和日报结构已经可用，不需要大规模重构。

## 执行的操作

- 新建 `00_local_documents/papers_pdf/`、`00_local_documents/manuscripts/`、`00_local_documents/thesis/`。
- 将根目录 PDF 和 DOCX 按用途移动到 `00_local_documents/` 下。
- 新增 `.gitattributes`，用 Git LFS 跟踪 PDF 和 DOCX。
- 新增 `.gitignore`，忽略系统缓存和临时文件。
- 更新 README 和 INDEX，使项目入口、每日检索流程、大文件归档位置更清晰。

## 移动文件列表

| 原路径 | 新路径 | 原因 |
|---|---|---|
| `D:\solarphysics\Paper\1982A&A...109..305B.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\1982A&A...109..305B.pdf` | 文献 PDF 归档 |
| `D:\solarphysics\Paper\1996A&A...309..291B.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\1996A&A...309..291B.pdf` | 文献 PDF 归档 |
| `D:\solarphysics\Paper\2101.07543v1.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\2101.07543v1.pdf` | 文献 PDF 归档 |
| `D:\solarphysics\Paper\2604.13590v1.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\2604.13590v1.pdf` | 文献 PDF 归档 |
| `D:\solarphysics\Paper\aa1142.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\aa1142.pdf` | 文献 PDF 归档 |
| `D:\solarphysics\Paper\Errors in Elliptical Gaussian Fits.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\Errors in Elliptical Gaussian Fits.pdf` | Gaussian fitting 方法文献归档 |
| `D:\solarphysics\Paper\The_Source_Regions_of_Impulsive_Solar_El.pdf` | `D:\solarphysics\Paper\00_local_documents\papers_pdf\The_Source_Regions_of_Impulsive_Solar_El.pdf` | 文献 PDF 归档 |
| `D:\solarphysics\Paper\Type-III Solar Radio Bursts with Spike-like Toppings_V14.docx` | `D:\solarphysics\Paper\00_local_documents\manuscripts\Type-III Solar Radio Bursts with Spike-like Toppings_V14.docx` | Word 手稿归档 |
| `D:\solarphysics\Paper\Type-III Solar Radio Bursts with Spike-like Toppings_V16.docx` | `D:\solarphysics\Paper\00_local_documents\manuscripts\Type-III Solar Radio Bursts with Spike-like Toppings_V16.docx` | Word 手稿归档 |
| `D:\solarphysics\Paper\博士论文-太阳射电爆发物理过程研究-李传洋.pdf` | `D:\solarphysics\Paper\00_local_documents\thesis\博士论文-太阳射电爆发物理过程研究-李传洋.pdf` | 大型博士论文背景材料归档 |

## 未处理文件

- 旧主题目录 `type_III_radio_bursts/`、`solar_radio_spikes/`、`AIA_observations/`、`DART_methods/`、`review_background/` 暂不迁移，避免破坏历史引用。
- 核心文献自动化脚本和测试保持原路径。

## 风险说明

- 本次未删除 PDF、DOCX、日报、索引或科研输出。
- 本次未修改 Gaussian fitting、Newkirk、drift-rate 等核心科研算法。
- PDF/DOCX 进入 Git LFS 后，克隆仓库时需要安装 Git LFS 才能自动拉取真实文件内容。

## 后续建议

- 如果后续要把旧主题目录迁入编号结构，应先统一更新 README、INDEX 和历史推荐文件中的链接。
- 如果新增本地 PDF 或 DOCX，应继续放入 `00_local_documents/` 并保持 Git LFS 跟踪。
