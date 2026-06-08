[CmdletBinding()]
param(
    [string]$AsOfDate = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$SkipLiveSearch,
    [string]$ConfigPath = (Join-Path $PSScriptRoot "..\config\paper_search_config.json"),
    [string]$SeedPath = (Join-Path $PSScriptRoot "..\data\seed_papers.json")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "PaperRecommendation\PaperRecommendation.psm1") -Force

function Write-Utf8BomFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $encoding = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-YearFromCrossrefItem {
    param($Item)

    foreach ($propertyName in @("published-print", "published-online", "issued", "created")) {
        $property = $Item.PSObject.Properties[$propertyName]
        if ($null -eq $property) {
            continue
        }

        $dateParts = $property.Value."date-parts"
        if ($dateParts -and $dateParts[0] -and $dateParts[0][0]) {
            return [string]$dateParts[0][0]
        }
    }

    return ""
}

function Invoke-ArxivSearch {
    param(
        [string[]]$Queries,
        [int]$MaxResults
    )

    $results = New-Object System.Collections.Generic.List[object]
    $headers = @{ "User-Agent" = "paper-daily-recommendation/1.0" }

    foreach ($query in $Queries) {
        try {
            $searchQuery = "all:$query"
            $uri = "https://export.arxiv.org/api/query?search_query=$([System.Uri]::EscapeDataString($searchQuery))&start=0&max_results=$MaxResults&sortBy=lastUpdatedDate&sortOrder=descending"
            $xmlContent = (Invoke-WebRequest -Uri $uri -Headers $headers -UseBasicParsing).Content
            $feed = [xml]$xmlContent
            $entries = @($feed.feed.entry)

            foreach ($entry in $entries) {
                $authors = @($entry.author | ForEach-Object { $_.name })
                $pdfLink = ""
                foreach ($link in @($entry.link)) {
                    if ($link.title -eq "pdf") {
                        $pdfLink = [string]$link.href
                        break
                    }
                }

                $identifier = [string]$entry.id
                $arxivId = if ($identifier) { ($identifier.TrimEnd('/') -split '/')[-1] } else { "" }
                $results.Add([pscustomobject]@{
                    title = ([string]$entry.title).Trim()
                    authors = $authors
                    year = ([string]$entry.published).Substring(0, 4)
                    journal = "arXiv preprint"
                    doi = ""
                    arxiv_id = $arxivId
                    ads_url = ""
                    pdf_url = $pdfLink
                    local_pdf_path = ""
                    summary = ([string]$entry.summary).Trim()
                    summary_cn = "待补充"
                    topic_tags = @("live search", "arXiv")
                    method_tags = @()
                    date_added = $AsOfDate
                    last_checked = $AsOfDate
                }) | Out-Null
            }
        }
        catch {
            Write-Warning "arXiv query failed for $query : $($_.Exception.Message)"
        }
    }

    return @($results)
}

function Invoke-CrossrefSearch {
    param(
        [string[]]$Queries,
        [int]$Rows
    )

    $results = New-Object System.Collections.Generic.List[object]
    $headers = @{ "User-Agent" = "paper-daily-recommendation/1.0" }

    foreach ($query in $Queries) {
        try {
            $uri = "https://api.crossref.org/works?query.title=$([System.Uri]::EscapeDataString($query))&rows=$Rows&sort=published&order=desc"
            $response = Invoke-RestMethod -Uri $uri -Headers $headers
            $items = @($response.message.items)

            foreach ($item in $items) {
                $title = if ($item.title) { [string]$item.title[0] } else { "" }
                if (-not $title) {
                    continue
                }

                $authors = @()
                foreach ($author in @($item.author)) {
                    $authorName = (($author.given, $author.family) -join " ").Trim()
                    if ($authorName) {
                        $authors += $authorName
                    }
                }

                $results.Add([pscustomobject]@{
                    title = $title
                    authors = $authors
                    year = (Get-YearFromCrossrefItem -Item $item)
                    journal = if ($item."container-title") { [string]$item."container-title"[0] } else { "Crossref result" }
                    doi = [string]$item.DOI
                    arxiv_id = ""
                    ads_url = ""
                    pdf_url = ""
                    local_pdf_path = ""
                    summary = ""
                    summary_cn = "待补充"
                    topic_tags = @("live search", "Crossref")
                    method_tags = @()
                    date_added = $AsOfDate
                    last_checked = $AsOfDate
                }) | Out-Null
            }
        }
        catch {
            Write-Warning "Crossref query failed for $query : $($_.Exception.Message)"
        }
    }

    return @($results)
}

function Get-LivePaperCandidates {
    param(
        $Config
    )

    $queries = New-Object System.Collections.Generic.List[string]
    foreach ($group in @($Config.keyword_groups)) {
        foreach ($query in @($group.queries)) {
            if ($query) {
                $queries.Add([string]$query) | Out-Null
            }
        }
    }

    $uniqueQueries = @($queries | Sort-Object -Unique)
    $arxivResults = Invoke-ArxivSearch -Queries $uniqueQueries -MaxResults ([int]$Config.search_settings.max_results_per_query)
    $crossrefResults = Invoke-CrossrefSearch -Queries $uniqueQueries -Rows ([int]$Config.search_settings.crossref_rows)

    return @($arxivResults + $crossrefResults)
}

function New-OrganizationLogContent {
    param(
        [string]$RunDate
    )

    return @"
# Paper 目录整理记录

## 整理日期

$RunDate

## 整理前问题

- 当前已具备统一的日报目录、Gaussian fitting 方法目录、项目方法建议目录、脚本、配置和测试入口。
- 根目录仍保留若干 PDF、docx 和旧主题目录；这些是可接受的历史科研材料，不应在自动化日报中移动或删除。

## 执行的操作

- 刷新 daily_recommendations、paper_master_index.*、02_methods_gaussian_fitting 和 08_project_method_notes 下的当日记录。
- 保留既有目录结构、PDF、docx、历史推荐和主题 README，不执行迁移。

## 移动文件列表

| 原路径 | 新路径 | 原因 |
|---|---|---|
| 无 | 无 | 本次为非破坏性刷新，仅更新索引、日报和方法记录 |

## 未处理文件

- 根目录 PDF/docx 与旧主题目录暂不迁移，避免影响既有引用路径和手工整理痕迹。

## 风险说明

- 未删除 PDF、原始数据、科研输出或核心算法文件。
- 当前未发现需要立即整理的高风险混乱。
- 若后续要做编号目录迁移，必须先复核所有引用路径、脚本和历史推荐文件。

## 后续建议

- 以后以 daily_recommendations、paper_master_index.* 和 02_methods_gaussian_fitting 作为主入口。
"@
}

$config = Get-PaperSearchConfig -ConfigPath $ConfigPath
$projectRoot = Get-ProjectRoot

$dailyDir = Join-Path $projectRoot (($config.output_paths.daily) -replace '/', '\')
$gaussianDir = Join-Path $projectRoot (($config.output_paths.gaussian) -replace '/', '\')
$gaussianDailyDir = Join-Path $projectRoot (($config.output_paths.gaussian_daily) -replace '/', '\')
$methodNotesDir = Join-Path $projectRoot (($config.output_paths.method_notes) -replace '/', '\')

Ensure-Directory -Path $dailyDir
Ensure-Directory -Path $gaussianDir
Ensure-Directory -Path $gaussianDailyDir
Ensure-Directory -Path $methodNotesDir

$seedPapers = Get-Content -Raw -Encoding UTF8 -Path $SeedPath | ConvertFrom-Json
$allRecords = New-Object System.Collections.Generic.List[object]
foreach ($paper in @($seedPapers)) {
    $allRecords.Add((ConvertTo-ScoredPaperRecord -Paper $paper -Config $config)) | Out-Null
}

if (-not $SkipLiveSearch) {
    $liveCandidates = Get-LivePaperCandidates -Config $config
    foreach ($candidate in @($liveCandidates)) {
        $allRecords.Add((ConvertTo-ScoredPaperRecord -Paper $candidate -Config $config)) | Out-Null
    }
}

$mergedRecords = Merge-PaperRecords -PaperRecords $allRecords
$orderedRecords = @($mergedRecords | Sort-Object @{ Expression = { Get-RelevanceRank -RelevanceLevel $_.relevance_level }; Descending = $true }, @{ Expression = { [int]($_.year -as [int]) }; Descending = $true }, title)
$gaussianRecords = @($orderedRecords | Where-Object { $_.uses_gaussian_fitting -or $_.uses_radio_centroid -or $_.uses_source_size })
$recommendedPapers = @($orderedRecords | Where-Object { $_.relevance_level -in @("A", "B") })

$dailyReportPath = Join-Path $dailyDir "$AsOfDate`_paper_recommendations.md"
$gaussianDailyPath = Join-Path $gaussianDailyDir "$AsOfDate`_gaussian_fitting_papers.md"
$paperIndexCsvPath = Join-Path $projectRoot "paper_master_index.csv"
$paperIndexMdPath = Join-Path $projectRoot "paper_master_index.md"
$gaussianIndexCsvPath = Join-Path $gaussianDir "gaussian_fitting_paper_index.csv"
$gaussianIndexMdPath = Join-Path $gaussianDir "gaussian_fitting_paper_index.md"
$gaussianReviewPath = Join-Path $gaussianDir "gaussian_fitting_method_review.md"
$gaussianImplementationPath = Join-Path $gaussianDir "gaussian_fitting_implementation_notes.md"
$gaussianQualityPath = Join-Path $gaussianDir "gaussian_fitting_quality_control.md"
$gaussianUncertaintyPath = Join-Path $gaussianDir "gaussian_fitting_uncertainty_notes.md"
$codeSuggestionPath = Join-Path $methodNotesDir "gaussian_fitting_code_improvement_suggestions_$AsOfDate.md"
$organizationLogPath = Join-Path $projectRoot "organization_log_$AsOfDate.md"
$statePath = Join-Path $projectRoot ".paper_recommendation_state.json"

$updatedFiles = @(
    "daily_recommendations/$AsOfDate`_paper_recommendations.md",
    "paper_master_index.csv",
    "paper_master_index.md",
    "02_methods_gaussian_fitting/gaussian_fitting_paper_index.csv",
    "02_methods_gaussian_fitting/gaussian_fitting_paper_index.md",
    "02_methods_gaussian_fitting/gaussian_fitting_method_review.md",
    "02_methods_gaussian_fitting/gaussian_fitting_implementation_notes.md",
    "02_methods_gaussian_fitting/gaussian_fitting_quality_control.md",
    "02_methods_gaussian_fitting/gaussian_fitting_uncertainty_notes.md",
    "02_methods_gaussian_fitting/gaussian_fitting_literature_daily/$AsOfDate`_gaussian_fitting_papers.md",
    "08_project_method_notes/gaussian_fitting_code_improvement_suggestions_$AsOfDate.md",
    "organization_log_$AsOfDate.md"
)

$keywordSummary = @()
foreach ($group in @($config.keyword_groups)) {
    $keywordSummary += @($group.queries)
}
$keywordSummary = @($keywordSummary | Sort-Object -Unique)

$dailyReportContent = New-DailyReportContent -AsOfDate $AsOfDate -KeywordSummary $keywordSummary -RecommendedPapers $recommendedPapers -UpdatedFiles $updatedFiles
$gaussianReviewContent = New-GaussianMethodReviewContent -GaussianPapers $gaussianRecords
$gaussianImplementationContent = New-GaussianImplementationNotesContent
$gaussianQualityContent = New-GaussianQualityControlContent
$gaussianUncertaintyContent = New-GaussianUncertaintyNotesContent
$gaussianDailyContent = New-GaussianDailyContent -AsOfDate $AsOfDate -GaussianPapers $gaussianRecords
$codeSuggestionContent = New-CodeSuggestionContent -GaussianPapers $gaussianRecords
$organizationLogContent = New-OrganizationLogContent -RunDate $AsOfDate

ConvertTo-CsvFriendlyRecords -PaperRecords $orderedRecords | Export-Csv -Path $paperIndexCsvPath -NoTypeInformation -Encoding UTF8
ConvertTo-GaussianCsvFriendlyRecords -GaussianPapers $gaussianRecords | Export-Csv -Path $gaussianIndexCsvPath -NoTypeInformation -Encoding UTF8

Write-Utf8BomFile -Path $dailyReportPath -Content $dailyReportContent
Write-Utf8BomFile -Path $paperIndexMdPath -Content (New-MasterIndexMarkdown -PaperRecords $orderedRecords)
Write-Utf8BomFile -Path $gaussianIndexMdPath -Content (New-GaussianIndexMarkdown -GaussianPapers $gaussianRecords)
Write-Utf8BomFile -Path $gaussianReviewPath -Content $gaussianReviewContent
Write-Utf8BomFile -Path $gaussianImplementationPath -Content $gaussianImplementationContent
Write-Utf8BomFile -Path $gaussianQualityPath -Content $gaussianQualityContent
Write-Utf8BomFile -Path $gaussianUncertaintyPath -Content $gaussianUncertaintyContent
Write-Utf8BomFile -Path $gaussianDailyPath -Content $gaussianDailyContent
Write-Utf8BomFile -Path $codeSuggestionPath -Content $codeSuggestionContent
Write-Utf8BomFile -Path $organizationLogPath -Content $organizationLogContent

$state = [pscustomobject]@{
    last_run = (Get-Date).ToString("s")
    as_of_date = $AsOfDate
    skip_live_search = [bool]$SkipLiveSearch
    total_papers = @($orderedRecords).Count
    gaussian_papers = @($gaussianRecords).Count
    latest_daily_report = $dailyReportPath
}
Write-Utf8BomFile -Path $statePath -Content ($state | ConvertTo-Json -Depth 4)

Write-Host "Generated daily report: $dailyReportPath"
Write-Host "Total indexed papers: $(@($orderedRecords).Count)"
Write-Host "Gaussian-method papers: $(@($gaussianRecords).Count)"
