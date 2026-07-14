Set-StrictMode -Version Latest

function Get-ProjectRoot {
    return (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
}

function Get-PaperSearchConfig {
    [CmdletBinding()]
    param(
        [string]$ConfigPath = (Join-Path (Get-ProjectRoot) "config\paper_search_config.json")
    )

    return (Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json)
}

function Merge-StringArray {
    [CmdletBinding()]
    param(
        [Parameter(ValueFromPipeline = $true)]
        [object[]]$Values
    )

    $items = New-Object System.Collections.Generic.List[string]

    foreach ($value in $Values) {
        if ($null -eq $value) {
            continue
        }

        if ($value -is [string]) {
            foreach ($part in ($value -split ';')) {
                $trimmed = $part.Trim()
                if ($trimmed) {
                    [void]$items.Add($trimmed)
                }
            }
            continue
        }

        foreach ($entry in @($value)) {
            if ($null -eq $entry) {
                continue
            }
            $text = [string]$entry
            $trimmed = $text.Trim()
            if ($trimmed) {
                [void]$items.Add($trimmed)
            }
        }
    }

    return $items.ToArray() | Sort-Object -Unique
}

function Get-NormalizedTitle {
    [CmdletBinding()]
    param(
        [string]$Title
    )

    if (-not $Title) {
        return ""
    }

    $lower = $Title.ToLowerInvariant()
    return ([regex]::Replace($lower, '[^a-z0-9]+', ' ')).Trim()
}

function Test-TextMatch {
    [CmdletBinding()]
    param(
        [string]$Text,
        [string]$Pattern
    )

    if (-not $Text -or -not $Pattern) {
        return $false
    }

    return $Text.ToLowerInvariant().Contains($Pattern.ToLowerInvariant())
}

function Get-RelevanceRank {
    [CmdletBinding()]
    param(
        [string]$RelevanceLevel
    )

    switch ($RelevanceLevel) {
        "A" { return 4 }
        "B" { return 3 }
        "C" { return 2 }
        "D" { return 1 }
        default { return 0 }
    }
}

function Get-PropertyValue {
    [CmdletBinding()]
    param(
        [psobject]$Object,
        [string]$Name,
        $Default = $null
    )

    if ($null -eq $Object) {
        return $Default
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
}

function Get-PaperTextBlob {
    [CmdletBinding()]
    param(
        [psobject]$Paper
    )

    $chunks = @(
        (Get-PropertyValue -Object $Paper -Name "title" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "summary" -Default ""),
        ((Merge-StringArray -Values @((Get-PropertyValue -Object $Paper -Name "topic_tags" -Default @()), (Get-PropertyValue -Object $Paper -Name "method_tags" -Default @()))) -join " "),
        (Get-PropertyValue -Object $Paper -Name "journal" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "instrument" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "target_event_type" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "gaussian_model" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "centroid_definition" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "source_size_definition" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "beam_handling" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "background_handling" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "uncertainty_method" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "quality_control" -Default ""),
        (Get-PropertyValue -Object $Paper -Name "applicability_to_DART_DRAT" -Default "")
    )

    return (($chunks | Where-Object { $_ }) -join " ").ToLowerInvariant()
}

function Get-RecommendedPriority {
    [CmdletBinding()]
    param(
        [string]$RelevanceLevel,
        $Config
    )

    $configured = Get-PropertyValue -Object $Config.priority_map -Name $RelevanceLevel
    if ($configured) {
        return [string]$configured
    }

    switch ($RelevanceLevel) {
        "A" { return "high" }
        "B" { return "medium" }
        "C" { return "background" }
        default { return "hold" }
    }
}

function ConvertTo-ScoredPaperRecord {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Paper,
        [Parameter(Mandatory = $true)]
        $Config
    )

    $text = Get-PaperTextBlob -Paper $Paper
    $topicTags = Merge-StringArray -Values @((Get-PropertyValue -Object $Paper -Name "topic_tags" -Default @()))
    $methodTags = Merge-StringArray -Values @((Get-PropertyValue -Object $Paper -Name "method_tags" -Default @()))

    $score = 0
    $matchedDirections = New-Object System.Collections.Generic.List[string]

    foreach ($group in @($Config.keyword_groups)) {
        $groupMatched = $false
        foreach ($term in @($group.score_terms)) {
            if (Test-TextMatch -Text $text -Pattern $term.pattern) {
                $score += [int]$term.score
                $groupMatched = $true
            }
        }

        if ($groupMatched) {
            [void]$matchedDirections.Add([string]$group.direction)
        }
    }

    $usesGaussian = $false
    foreach ($pattern in @($Config.flags.uses_gaussian_fitting)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesGaussian = $true
            break
        }
    }

    $usesCentroid = $false
    foreach ($pattern in @($Config.flags.uses_radio_centroid)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesCentroid = $true
            break
        }
    }

    $usesSourceSize = $false
    foreach ($pattern in @($Config.flags.uses_source_size)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesSourceSize = $true
            break
        }
    }

    $usesBeam = $false
    foreach ($pattern in @($Config.flags.uses_beam_deconvolution)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesBeam = $true
            break
        }
    }

    $usesAia = $false
    foreach ($pattern in @($Config.flags.uses_aia)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesAia = $true
            break
        }
    }

    $usesHmi = $false
    foreach ($pattern in @($Config.flags.uses_hmi)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesHmi = $true
            break
        }
    }

    $usesNewkirk = $false
    foreach ($pattern in @($Config.flags.uses_newkirk_model)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesNewkirk = $true
            break
        }
    }

    $usesDrift = $false
    foreach ($pattern in @($Config.flags.uses_frequency_drift_rate)) {
        if (Test-TextMatch -Text $text -Pattern $pattern) {
            $usesDrift = $true
            break
        }
    }
    if (-not $usesDrift -and (Test-TextMatch -Text $text -Pattern "type iii") -and ((Test-TextMatch -Text $text -Pattern "duration") -or (Test-TextMatch -Text $text -Pattern "motion"))) {
        $usesDrift = $true
    }

    if ($usesGaussian -and $usesCentroid) {
        $score += 4
    }
    if ($usesSourceSize) {
        $score += 2
    }
    if ($usesBeam) {
        $score += 2
    }
    if ($usesAia -or $usesHmi) {
        $score += 2
    }
    if ($usesDrift -or $usesNewkirk) {
        $score += 2
    }

    $relevanceLevel = [string](Get-PropertyValue -Object $Paper -Name "relevance_level" -Default "")
    if (-not $relevanceLevel) {
        $thresholds = $Config.relevance_thresholds
        if ($score -ge [int]$thresholds.A) {
            $relevanceLevel = "A"
        }
        elseif ($score -ge [int]$thresholds.B) {
            $relevanceLevel = "B"
        }
        elseif ($score -ge [int]$thresholds.C) {
            $relevanceLevel = "C"
        }
        else {
            $relevanceLevel = "D"
        }
    }

    $priority = [string](Get-PropertyValue -Object $Paper -Name "recommended_priority" -Default "")
    if (-not $priority) {
        $priority = Get-RecommendedPriority -RelevanceLevel $relevanceLevel -Config $Config
    }

    $topicTags = Merge-StringArray -Values @($topicTags, $matchedDirections)
    $methodTags = Merge-StringArray -Values @(
        $methodTags,
        @(
            $(if ($usesGaussian) { "Gaussian fitting" }),
            $(if ($usesCentroid) { "radio source centroid" }),
            $(if ($usesSourceSize) { "source size / FWHM" }),
            $(if ($usesBeam) { "beam handling" }),
            $(if ($usesDrift) { "frequency drift rate" })
        )
    )

    return [pscustomobject]@{
        title = [string](Get-PropertyValue -Object $Paper -Name "title" -Default "")
        authors = Merge-StringArray -Values @((Get-PropertyValue -Object $Paper -Name "authors" -Default @()))
        year = [string](Get-PropertyValue -Object $Paper -Name "year" -Default "")
        journal = [string](Get-PropertyValue -Object $Paper -Name "journal" -Default "")
        doi = [string](Get-PropertyValue -Object $Paper -Name "doi" -Default "")
        arxiv_id = [string](Get-PropertyValue -Object $Paper -Name "arxiv_id" -Default "")
        ads_url = [string](Get-PropertyValue -Object $Paper -Name "ads_url" -Default "")
        pdf_url = [string](Get-PropertyValue -Object $Paper -Name "pdf_url" -Default "")
        local_pdf_path = [string](Get-PropertyValue -Object $Paper -Name "local_pdf_path" -Default "")
        topic_tags = $topicTags
        relevance_level = $relevanceLevel
        recommended_priority = $priority
        method_tags = $methodTags
        uses_gaussian_fitting = $usesGaussian
        uses_radio_centroid = $usesCentroid
        uses_source_size = $usesSourceSize
        uses_beam_deconvolution = $usesBeam
        uses_aia = $usesAia
        uses_hmi = $usesHmi
        uses_newkirk_model = $usesNewkirk
        uses_frequency_drift_rate = $usesDrift
        summary_cn = [string](Get-PropertyValue -Object $Paper -Name "summary_cn" -Default "待补充")
        key_methods = [string](Get-PropertyValue -Object $Paper -Name "key_methods" -Default "")
        why_relevant_to_current_project = [string](Get-PropertyValue -Object $Paper -Name "why_relevant_to_current_project" -Default "")
        date_added = [string](Get-PropertyValue -Object $Paper -Name "date_added" -Default (Get-Date -Format "yyyy-MM-dd"))
        last_checked = [string](Get-PropertyValue -Object $Paper -Name "last_checked" -Default (Get-Date -Format "yyyy-MM-dd"))
        summary = [string](Get-PropertyValue -Object $Paper -Name "summary" -Default "")
        direction = [string](Get-PropertyValue -Object $Paper -Name "direction" -Default (($matchedDirections | Select-Object -First 1)))
        instrument = [string](Get-PropertyValue -Object $Paper -Name "instrument" -Default "")
        radio_frequency_range = [string](Get-PropertyValue -Object $Paper -Name "radio_frequency_range" -Default "")
        target_event_type = [string](Get-PropertyValue -Object $Paper -Name "target_event_type" -Default "")
        gaussian_model = [string](Get-PropertyValue -Object $Paper -Name "gaussian_model" -Default "")
        centroid_definition = [string](Get-PropertyValue -Object $Paper -Name "centroid_definition" -Default "")
        source_size_definition = [string](Get-PropertyValue -Object $Paper -Name "source_size_definition" -Default "")
        beam_handling = [string](Get-PropertyValue -Object $Paper -Name "beam_handling" -Default "")
        background_handling = [string](Get-PropertyValue -Object $Paper -Name "background_handling" -Default "")
        uncertainty_method = [string](Get-PropertyValue -Object $Paper -Name "uncertainty_method" -Default "")
        quality_control = [string](Get-PropertyValue -Object $Paper -Name "quality_control" -Default "")
        applicability_to_DART_DRAT = [string](Get-PropertyValue -Object $Paper -Name "applicability_to_DART_DRAT" -Default "")
        notes_for_current_code = [string](Get-PropertyValue -Object $Paper -Name "notes_for_current_code" -Default "")
    }
}

function Merge-PaperRecords {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$PaperRecords
    )

    $mergedByTitle = @{}

    foreach ($record in @($PaperRecords)) {
        if ($null -eq $record) {
            continue
        }

        $key = Get-NormalizedTitle -Title $record.title
        if (-not $mergedByTitle.ContainsKey($key)) {
            $mergedByTitle[$key] = $record
            continue
        }

        $existing = $mergedByTitle[$key]
        foreach ($property in @($record.PSObject.Properties.Name)) {
            $currentValue = $existing.$property
            $incomingValue = $record.$property

            if ($property -in @("topic_tags", "method_tags", "authors")) {
                $existing.$property = Merge-StringArray -Values @($currentValue, $incomingValue)
                continue
            }

            if ($property -eq "relevance_level") {
                if ((Get-RelevanceRank -RelevanceLevel $incomingValue) -gt (Get-RelevanceRank -RelevanceLevel $currentValue)) {
                    $existing.$property = $incomingValue
                }
                continue
            }

            if ($property -eq "recommended_priority" -and -not $currentValue) {
                $existing.$property = $incomingValue
                continue
            }

            if (($null -eq $currentValue) -or ([string]$currentValue).Trim() -eq "") {
                $existing.$property = $incomingValue
            }
        }

        $mergedByTitle[$key] = $existing
    }

    $result = @($mergedByTitle.GetEnumerator() | ForEach-Object { $_.Value })
    Write-Output -NoEnumerate $result
}

function Get-RecommendationLinkText {
    [CmdletBinding()]
    param(
        [psobject]$Paper
    )

    if ($Paper.doi) {
        return "DOI: $($Paper.doi)"
    }
    if ($Paper.arxiv_id) {
        return "arXiv: $($Paper.arxiv_id)"
    }
    if ($Paper.ads_url) {
        return "ADS"
    }
    return "待补充"
}

function Format-PaperSummaryBlock {
    [CmdletBinding()]
    param(
        [psobject]$Paper,
        [switch]$Gaussian
    )

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("### $($Paper.title)")
    [void]$lines.Add("")
    [void]$lines.Add("- 年份：$($Paper.year)")
    [void]$lines.Add("- 期刊/来源：$($Paper.journal)")
    [void]$lines.Add("- 相关性：$($Paper.relevance_level)")
    [void]$lines.Add("- 主题标签：$($Paper.topic_tags -join '; ')")
    [void]$lines.Add("- 简述：$($Paper.summary_cn)")
    [void]$lines.Add("- 对当前项目的价值：$($Paper.why_relevant_to_current_project)")
    [void]$lines.Add("- 链接：$((Get-RecommendationLinkText -Paper $Paper))")

    if ($Gaussian) {
        [void]$lines.Add("- 该论文如何定义 radio source center：$($Paper.centroid_definition)")
        [void]$lines.Add("- 是否使用 2D Gaussian / elliptical Gaussian：$($Paper.gaussian_model)")
        [void]$lines.Add("- 是否讨论 FWHM / source size：$($Paper.source_size_definition)")
        [void]$lines.Add("- 是否处理 beam deconvolution：$($Paper.beam_handling)")
        [void]$lines.Add("- 是否讨论 centroid uncertainty：$($Paper.uncertainty_method)")
        [void]$lines.Add("- 是否适合当前 DART / DRAT 射电源图像：$($Paper.applicability_to_DART_DRAT)")
    }

    [void]$lines.Add("")
    return ($lines -join "`r`n")
}

function New-DailyReportContent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AsOfDate,
        [string[]]$KeywordSummary = @(),
        [object[]]$RecommendedPapers = @(),
        [string[]]$UpdatedFiles = @()
    )

    $relevantPapers = @($RecommendedPapers | Where-Object { $_.relevance_level -in @("A", "B") })
    $ordered = @($relevantPapers | Sort-Object @{ Expression = { Get-RelevanceRank -RelevanceLevel $_.relevance_level }; Descending = $true }, @{ Expression = { [int]($_.year -as [int]) }; Descending = $true }, title)

    $typePapers = @($ordered | Where-Object { ($_.topic_tags -join " ").ToLowerInvariant() -match "type iii|spikes topping|fine structure" })
    $spikePapers = @($ordered | Where-Object { ($_.topic_tags -join " ").ToLowerInvariant() -match "spike" })
    $jointPapers = @($ordered | Where-Object { $_.uses_aia -or $_.uses_hmi })
    $gaussianPapers = @($ordered | Where-Object { $_.uses_gaussian_fitting -or $_.uses_radio_centroid -or $_.uses_source_size })
    $newkirkPapers = @($ordered | Where-Object { $_.uses_newkirk_model -or $_.uses_frequency_drift_rate })

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("# $AsOfDate 文献检索日报")
    [void]$lines.Add("")
    [void]$lines.Add("## 1. 今日检索关键词")
    [void]$lines.Add("")
    foreach ($keyword in $KeywordSummary) {
        [void]$lines.Add("- $keyword")
    }
    if (-not $KeywordSummary) {
        [void]$lines.Add("- 今日沿用配置文件中的优先关键词组。")
    }
    [void]$lines.Add("")
    [void]$lines.Add("## 2. 今日新增重点论文总览")
    [void]$lines.Add("")
    [void]$lines.Add("| 序号 | 论文 | 年份 | 方向 | 相关性 | 推荐等级 | DOI/arXiv/ADS | 本地记录 |")
    [void]$lines.Add("|---|---|---|---|---|---|---|---|")

    $index = 1
    foreach ($paper in $ordered) {
        $linkText = Get-RecommendationLinkText -Paper $paper
        [void]$lines.Add("| $index | $($paper.title) | $($paper.year) | $($paper.direction) | $($paper.relevance_level) | $($paper.recommended_priority) | $linkText | paper_master_index.csv |")
        $index += 1
    }
    if (-not $ordered) {
        [void]$lines.Add("| 1 | 今日没有发现比已有文献更相关的新论文。 | - | - | - | - | - | paper_master_index.csv |")
    }
    [void]$lines.Add("")

    [void]$lines.Add("## 3. 与 spikes topping type III / type III burst 相关论文")
    [void]$lines.Add("")
    if ($typePapers) {
        foreach ($paper in $typePapers) {
            [void]$lines.Add((Format-PaperSummaryBlock -Paper $paper))
        }
    }
    else {
        [void]$lines.Add("今日没有发现比已有文献更相关的新论文。")
        [void]$lines.Add("")
    }

    [void]$lines.Add("## 4. 与 solar radio spikes / fine structures 相关论文")
    [void]$lines.Add("")
    if ($spikePapers) {
        foreach ($paper in $spikePapers) {
            [void]$lines.Add((Format-PaperSummaryBlock -Paper $paper))
        }
    }
    else {
        [void]$lines.Add("今日没有发现比已有文献更相关的新论文。")
        [void]$lines.Add("")
    }

    [void]$lines.Add("## 5. 与 AIA / EUV / HMI / radio 联合分析相关论文")
    [void]$lines.Add("")
    if ($jointPapers) {
        foreach ($paper in $jointPapers) {
            [void]$lines.Add((Format-PaperSummaryBlock -Paper $paper))
        }
    }
    else {
        [void]$lines.Add("今日没有发现比已有文献更相关的新论文。")
        [void]$lines.Add("")
    }

    [void]$lines.Add("## 6. 与 Gaussian fitting / radio source centroid 相关论文")
    [void]$lines.Add("")
    [void]$lines.Add("必须重点回答：")
    [void]$lines.Add("- 该论文如何定义 radio source center？")
    [void]$lines.Add("- 是否使用 2D Gaussian / elliptical Gaussian？")
    [void]$lines.Add("- 是否讨论 FWHM / source size？")
    [void]$lines.Add("- 是否处理 beam deconvolution？")
    [void]$lines.Add("- 是否讨论 centroid uncertainty？")
    [void]$lines.Add("- 是否适合当前 DART / DRAT 射电源图像？")
    [void]$lines.Add("")
    if ($gaussianPapers) {
        foreach ($paper in $gaussianPapers) {
            [void]$lines.Add((Format-PaperSummaryBlock -Paper $paper -Gaussian))
        }
    }
    else {
        [void]$lines.Add("今日没有新增 A/B 级 Gaussian fitting 论文。")
        [void]$lines.Add("")
    }

    [void]$lines.Add("## 7. 与 Newkirk density model / frequency drift rate / source motion 相关论文")
    [void]$lines.Add("")
    if ($newkirkPapers) {
        foreach ($paper in $newkirkPapers) {
            [void]$lines.Add((Format-PaperSummaryBlock -Paper $paper))
        }
    }
    else {
        [void]$lines.Add("今日没有新增 A/B 级 Newkirk / drift-rate 论文。")
        [void]$lines.Add("")
    }

    [void]$lines.Add("## 8. 今日最值得精读的 3–5 篇论文")
    [void]$lines.Add("")
    $topPapers = @($ordered | Select-Object -First 5)
    if ($topPapers) {
        $rank = 1
        foreach ($paper in $topPapers) {
            [void]$lines.Add("$rank. $($paper.title) - $($paper.why_relevant_to_current_project)")
            $rank += 1
        }
    }
    else {
        [void]$lines.Add("1. 今日没有发现比已有文献更相关的新论文。")
    }
    [void]$lines.Add("")

    [void]$lines.Add("## 9. 对当前项目的具体建议")
    [void]$lines.Add("")
    [void]$lines.Add("- 建议把单源 elliptical Gaussian 作为默认模型，暂不直接扩展到多源分解，除非 ROI 内存在稳定多峰证据。")
    [void]$lines.Add("- 建议缩紧 ROI / mask / threshold，避免 max_fwhm_arcsec = 1800.0 导致无物理意义的大椭圆。")
    [void]$lines.Add("- 建议加入背景扣除开关，并支持 Gaussian + constant background 与 Gaussian + tilted plane background 两种模式。")
    [void]$lines.Add("- 建议将 Gaussian center 与 contour center 逐频逐时对比，偏差过大时直接打上 fit_quality_flag。")
    [void]$lines.Add("- 建议保存 drift 选取频谱图与选点线条，以便把 dynamic spectrum 选点证据纳入论文图版。")
    [void]$lines.Add("- 建议把 Newkirk 比较从单纯空间外推改为 height-frequency 与 height-time 双视角比较。")
    [void]$lines.Add("- 建议更新 README 与 Gaussian fitting 方法综述，使文献库、诊断图和代码建议三者一致。")
    [void]$lines.Add("")

    [void]$lines.Add("## 10. 今日更新文件列表")
    [void]$lines.Add("")
    foreach ($file in $UpdatedFiles) {
        [void]$lines.Add("- $file")
    }
    if (-not $UpdatedFiles) {
        [void]$lines.Add("- 本次仅生成内存中的日报内容，尚未落盘。")
    }

    return ($lines -join "`r`n")
}

function New-GaussianMethodReviewContent {
    [CmdletBinding()]
    param(
        [object[]]$GaussianPapers = @()
    )

    $titles = @($GaussianPapers | Select-Object -ExpandProperty title)
    $paperList = if ($titles) { $titles } else { @("待持续补充的核心文献将按日自动更新。") }

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("# Gaussian fitting 方法综述")
    [void]$lines.Add("")
    [void]$lines.Add("## 当前纳入的核心文献")
    [void]$lines.Add("")
    foreach ($title in $paperList) {
        [void]$lines.Add("- $title")
    }
    [void]$lines.Add("")
    [void]$lines.Add("## 5.1 图像输入与坐标")
    [void]$lines.Add("")
    [void]$lines.Add("- 射电图像输入应保留 FITS 原始头信息，优先记录 RA / Dec 与 helioprojective coordinates 之间的转换链条。")
    [void]$lines.Add("- 多频率射电图像不应直接比较，必须先检查 pixel-to-world transformation、观测时刻和太阳半径定义。")
    [void]$lines.Add("- 叠加到 AIA 背景图时，需要明确射电太阳半径与 EUV 太阳半径可能不一致，并记录任何经验缩放。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.2 背景扣除")
    [void]$lines.Add("")
    [void]$lines.Add("- 优先支持 pre-burst background subtraction、quiet-Sun background、running median / temporal median 三类背景估计。")
    [void]$lines.Add("- 当前项目建议把背景作为可切换项，至少保留 Gaussian + constant background 和 Gaussian + tilted plane background。")
    [void]$lines.Add("- 背景扣除会直接影响 centroid，弱源、扩展源和偏心源尤其敏感。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.3 拟合模型")
    [void]$lines.Add("")
    [void]$lines.Add("默认模型：")
    [void]$lines.Add("")
    [void]$lines.Add("    I(x, y) = A exp[-0.5 * Q(x, y)] + B")
    [void]$lines.Add("    Q = (x' / sigma_x)^2 + (y' / sigma_y)^2")
    [void]$lines.Add("")
    [void]$lines.Add("带倾斜背景模型：")
    [void]$lines.Add("")
    [void]$lines.Add("    I(x, y) = Gaussian(x, y) + B0 + Bx x + By y")
    [void]$lines.Add("")
    [void]$lines.Add("- 当前项目默认优先使用单源 elliptical Gaussian。")
    [void]$lines.Add("- 只有在 ROI 明显多峰且文献支持时，才考虑多源模型。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.4 初始参数选择")
    [void]$lines.Add("")
    [void]$lines.Add("- amplitude 初值可取 ROI 最大值减边缘背景。")
    [void]$lines.Add("- x0, y0 初值可取最大亮度像素或 intensity-weighted centroid。")
    [void]$lines.Add("- sigma 初值可由半高宽区域估计。")
    [void]$lines.Add("- theta 初值可设为 0，或由二阶矩估计。")
    [void]$lines.Add("- background 初值建议取 ROI 边缘中位数。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.5 拟合约束")
    [void]$lines.Add("")
    [void]$lines.Add("    A > 0")
    [void]$lines.Add("    sigma_x > 0")
    [void]$lines.Add("    sigma_y > 0")
    [void]$lines.Add("    centroid 位于 ROI 内")
    [void]$lines.Add("    background 不主导总强度")
    [void]$lines.Add("")
    [void]$lines.Add("- 需要重点复核 max_fwhm_arcsec = 1800.0 是否过宽。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.6 拟合质量控制")
    [void]$lines.Add("")
    [void]$lines.Add("- 建议输出 fit_success, fit_reason, snr, noise_sigma, reduced_chi_square, residual_rms。")
    [void]$lines.Add("- 噪声优先用 sigma_noise ≈ 1.4826 × MAD。")
    [void]$lines.Add("- 需要同步输出 is_edge_source, is_multi_peak, is_overlarge_fwhm, is_low_snr, is_bad_fit。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.7 centroid 可靠性验证")
    [void]$lines.Add("")
    [void]$lines.Add("- 必须并行记录 Gaussian fitted center 与 contour center。")
    [void]$lines.Add("- 推荐输出 gaussian_x_arcsec, gaussian_y_arcsec, contour_x_arcsec, contour_y_arcsec, delta_r_arcsec。")
    [void]$lines.Add("- 如果 Gaussian fitted center 与 contour center 偏差过大，应优先检查背景项、ROI、阈值与多峰结构。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.8 beam / PSF / 分辨率修正")
    [void]$lines.Add("")
    [void]$lines.Add("    FWHM_intrinsic^2 ≈ FWHM_observed^2 - FWHM_beam^2")
    [void]$lines.Add("")
    [void]$lines.Add("- 如果缺少可靠 beam 信息，当前 source size 应写成 observed apparent size，而不是 intrinsic source size。")
    [void]$lines.Add("- 对 major / minor axis 不同的 beam，应分别去卷积。")
    [void]$lines.Add("")
    [void]$lines.Add("## 5.9 与 Newkirk 高度和频率漂移率结合")
    [void]$lines.Add("")
    [void]$lines.Add("- 每个频率对应一个 Gaussian center，并通过 Newkirk density model 转换成理论高度。")
    [void]$lines.Add("- 对比 spatial trajectory、height-frequency、height-time 和 dynamic-spectrum drift rate。")
    [void]$lines.Add("- 不同速度量含义不同，不能把 Gaussian center motion speed、Newkirk height-derived speed、dynamic-spectrum drift-rate-derived speed 简单等同。")

    return ($lines -join "`r`n")
}

function New-MasterIndexMarkdown {
    [CmdletBinding()]
    param(
        [object[]]$PaperRecords
    )

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("# Paper Master Index")
    [void]$lines.Add("")
    [void]$lines.Add("| Title | Year | Relevance | Priority | Key methods | Why relevant |")
    [void]$lines.Add("|---|---|---|---|---|---|")
    foreach ($paper in @($PaperRecords | Sort-Object @{ Expression = { Get-RelevanceRank -RelevanceLevel $_.relevance_level }; Descending = $true }, @{ Expression = { [int]($_.year -as [int]) }; Descending = $true }, title)) {
        [void]$lines.Add("| $($paper.title) | $($paper.year) | $($paper.relevance_level) | $($paper.recommended_priority) | $($paper.key_methods) | $($paper.why_relevant_to_current_project) |")
    }

    return ($lines -join "`r`n")
}

function New-GaussianIndexMarkdown {
    [CmdletBinding()]
    param(
        [object[]]$GaussianPapers
    )

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("# Gaussian Fitting Paper Index")
    [void]$lines.Add("")
    [void]$lines.Add("| Title | Year | Instrument | Gaussian model | Centroid definition | Beam handling | DART/DRAT applicability |")
    [void]$lines.Add("|---|---|---|---|---|---|---|")
    foreach ($paper in @($GaussianPapers | Sort-Object @{ Expression = { Get-RelevanceRank -RelevanceLevel $_.relevance_level }; Descending = $true }, @{ Expression = { [int]($_.year -as [int]) }; Descending = $true }, title)) {
        [void]$lines.Add("| $($paper.title) | $($paper.year) | $($paper.instrument) | $($paper.gaussian_model) | $($paper.centroid_definition) | $($paper.beam_handling) | $($paper.applicability_to_DART_DRAT) |")
    }
    return ($lines -join "`r`n")
}

function New-GaussianImplementationNotesContent {
    [CmdletBinding()]
    param()

    return @"
# Gaussian fitting implementation notes

- 默认优先实现单源 elliptical Gaussian，并保留常数背景项。
- 当 ROI 存在明显梯度时，切换到 `Gaussian + tilted plane background`。
- 先输出 observed centroid 与 observed apparent size，再在 beam 信息可靠时做去卷积。
- 每个拟合结果应保留原始 ROI、拟合图、残差图和参数协方差矩阵。
"@
}

function New-GaussianQualityControlContent {
    [CmdletBinding()]
    param()

    return @"
# Gaussian fitting quality control

- 噪声估计：优先使用 1.4826 × MAD，记录估计区域。
- SNR 过低、FWHM 过大、ROI 触边、多峰源和残差结构异常时都应触发 flag。
- 低频图像分辨率更差，若 Gaussian center 与 contour center 偏差显著，不应用于速度拟合。
- 建议每次运行保存一份 fit_reason 汇总，便于筛掉不稳定时间帧。
"@
}

function New-GaussianUncertaintyNotesContent {
    [CmdletBinding()]
    param()

    return @"
# Gaussian fitting uncertainty notes

- `centroid_uncertainty_x` 与 `centroid_uncertainty_y` 应区分拟合参数误差和成像系统误差。
- 若 beam 未知或散射显著，应把位置误差与 source-size 误差写成保守上界。
- 低 SNR、偏心源、背景梯度和多峰结构都会放大 centroid 偏差。
- 对论文级结果，建议同时报告 Gaussian fitted center、contour center 与两者差值。
"@
}

function New-GaussianDailyContent {
    [CmdletBinding()]
    param(
        [string]$AsOfDate,
        [object[]]$GaussianPapers
    )

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("# $AsOfDate Gaussian fitting 文献更新")
    [void]$lines.Add("")
    if ($GaussianPapers) {
        foreach ($paper in $GaussianPapers) {
            [void]$lines.Add((Format-PaperSummaryBlock -Paper $paper -Gaussian))
        }
    }
    else {
        [void]$lines.Add("今日没有新增 A/B 级 Gaussian fitting 文献。")
    }

    return ($lines -join "`r`n")
}

function New-CodeSuggestionContent {
    [CmdletBinding()]
    param(
        [object[]]$GaussianPapers
    )

    return @"
# Gaussian fitting 代码改进建议

## 1. 当前项目可能已有功能

- 基于射电图像选择 ROI。
- 估计 source center、source size、频率漂移率和 Newkirk 高度。
- 生成 AIA / 射电联合图和动态频谱选点结果。

## 2. 当前可能存在的问题

- Gaussian center 是否偏离真实源区。
- ROI 是否过大，导致背景主导拟合。
- FWHM 是否异常放大。
- 是否存在多峰源、低 SNR 拟合和低频分辨率退化。
- 149 MHz 前几个时间帧是否没有真实 burst。
- Gaussian center 与 contour center 是否一致。

## 3. 建议新增输出字段

- fit_success, fit_reason, snr, noise_sigma
- gaussian_x_arcsec, gaussian_y_arcsec
- contour_x_arcsec, contour_y_arcsec
- delta_r_arcsec, fwhm_major_arcsec, fwhm_minor_arcsec
- is_multi_peak, is_overlarge_fwhm, is_low_snr, fit_quality_flag

## 4. 建议新增诊断图

- 原始射电图 + contour + Gaussian ellipse
- Gaussian center 与 contour center 对比
- residual map
- FWHM 随时间/频率变化
- SNR 随时间/频率变化
- centroid offset 随时间/频率变化
- Gaussian center trajectory
- Newkirk height vs frequency
- Gaussian center height comparison
- drift-rate selected spectrogram with saved selected lines

## 5. 建议新增质量控制 flag

- is_edge_source
- is_multi_peak
- is_overlarge_fwhm
- is_low_snr
- is_bad_fit

## 6. 是否建议当前阶段修改算法

- 当前建议：只整理文献、增加诊断输出、增加背景扣除开关、增加 contour center 对比。
- 暂不建议立即修改核心拟合模型。
- 当诊断输出确认系统性偏差后，再进入算法改进阶段。
"@
}

function ConvertTo-CsvFriendlyRecords {
    [CmdletBinding()]
    param(
        [object[]]$PaperRecords
    )

    $records = foreach ($paper in $PaperRecords) {
        [pscustomobject]@{
            title = $paper.title
            authors = $paper.authors -join "; "
            year = $paper.year
            journal = $paper.journal
            doi = $paper.doi
            arxiv_id = $paper.arxiv_id
            ads_url = $paper.ads_url
            pdf_url = $paper.pdf_url
            local_pdf_path = $paper.local_pdf_path
            topic_tags = $paper.topic_tags -join "; "
            relevance_level = $paper.relevance_level
            recommended_priority = $paper.recommended_priority
            method_tags = $paper.method_tags -join "; "
            uses_gaussian_fitting = $paper.uses_gaussian_fitting
            uses_radio_centroid = $paper.uses_radio_centroid
            uses_source_size = $paper.uses_source_size
            uses_beam_deconvolution = $paper.uses_beam_deconvolution
            uses_aia = $paper.uses_aia
            uses_hmi = $paper.uses_hmi
            uses_newkirk_model = $paper.uses_newkirk_model
            uses_frequency_drift_rate = $paper.uses_frequency_drift_rate
            summary_cn = $paper.summary_cn
            key_methods = $paper.key_methods
            why_relevant_to_current_project = $paper.why_relevant_to_current_project
            date_added = $paper.date_added
            last_checked = $paper.last_checked
        }
    }

    return @($records)
}

function ConvertTo-GaussianCsvFriendlyRecords {
    [CmdletBinding()]
    param(
        [object[]]$GaussianPapers
    )

    $records = foreach ($paper in $GaussianPapers) {
        [pscustomobject]@{
            title = $paper.title
            authors = $paper.authors -join "; "
            year = $paper.year
            instrument = $paper.instrument
            radio_frequency_range = $paper.radio_frequency_range
            target_event_type = $paper.target_event_type
            gaussian_model = $paper.gaussian_model
            centroid_definition = $paper.centroid_definition
            source_size_definition = $paper.source_size_definition
            beam_handling = $paper.beam_handling
            background_handling = $paper.background_handling
            uncertainty_method = $paper.uncertainty_method
            quality_control = $paper.quality_control
            applicability_to_DART_DRAT = $paper.applicability_to_DART_DRAT
            notes_for_current_code = $paper.notes_for_current_code
        }
    }

    return @($records)
}

function ConvertTo-NormalizedGitPath {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$Path = ""
    )

    return $Path.Replace("\", "/").Trim("/")
}

function Test-GitPathWithinPaper {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [AllowEmptyString()]
        [string]$PaperPathPrefix = ""
    )

    $normalizedPath = ConvertTo-NormalizedGitPath -Path $Path
    $normalizedPrefix = ConvertTo-NormalizedGitPath -Path $PaperPathPrefix
    if ([string]::IsNullOrWhiteSpace($normalizedPrefix)) {
        return $true
    }

    return $normalizedPath.Equals($normalizedPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
        $normalizedPath.StartsWith("$normalizedPrefix/", [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-GitPathAllowedForPaperPublish {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [AllowEmptyString()]
        [string]$PaperPathPrefix = ""
    )

    if (-not (Test-GitPathWithinPaper -Path $Path -PaperPathPrefix $PaperPathPrefix)) {
        return $false
    }

    $normalizedPath = ConvertTo-NormalizedGitPath -Path $Path
    $normalizedPrefix = ConvertTo-NormalizedGitPath -Path $PaperPathPrefix
    $relativePath = if ([string]::IsNullOrWhiteSpace($normalizedPrefix)) {
        $normalizedPath
    }
    elseif ($normalizedPath.Length -gt $normalizedPrefix.Length) {
        $normalizedPath.Substring($normalizedPrefix.Length + 1)
    }
    else {
        ""
    }

    $exactPaths = @(
        "config/paper_search_config.json",
        "data/seed_papers.json",
        "paper_master_index.csv",
        "paper_master_index.md"
    )
    if ($exactPaths -contains $relativePath) {
        return $true
    }

    foreach ($directoryPrefix in @("daily_recommendations", "02_methods_gaussian_fitting", "08_project_method_notes")) {
        if ($relativePath.StartsWith("$directoryPrefix/", [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $relativePath -match '^organization_log_\d{4}-\d{2}-\d{2}\.md$'
}

function Get-GitPaperPublishPathspecs {
    [CmdletBinding()]
    param(
        [AllowEmptyString()]
        [string]$PaperPathPrefix = ""
    )

    $normalizedPrefix = ConvertTo-NormalizedGitPath -Path $PaperPathPrefix
    $relativePathspecs = @(
        "config/paper_search_config.json",
        "data/seed_papers.json",
        "daily_recommendations",
        "paper_master_index.csv",
        "paper_master_index.md",
        "02_methods_gaussian_fitting",
        "08_project_method_notes",
        ":(glob)organization_log_*.md"
    )

    if ([string]::IsNullOrWhiteSpace($normalizedPrefix)) {
        return @($relativePathspecs)
    }

    return @($relativePathspecs | ForEach-Object {
        if ($_.StartsWith(":(glob)")) {
            ":(glob)$normalizedPrefix/$($_.Substring(7))"
        }
        else {
            "$normalizedPrefix/$_"
        }
    })
}

function Get-GitPaperRepositoryState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot
    )

    $gitRootOutput = @(& git -C $ProjectRoot rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or $gitRootOutput.Count -eq 0) {
        throw "Paper publishing requires '$ProjectRoot' to be inside a Git repository."
    }
    $gitRoot = [string]$gitRootOutput[-1]

    $prefixOutput = @(& git -C $ProjectRoot rev-parse --show-prefix 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve the Paper path relative to the Git root."
    }
    $paperPathPrefix = if ($prefixOutput.Count -gt 0) {
        ConvertTo-NormalizedGitPath -Path ([string]$prefixOutput[-1])
    }
    else {
        ""
    }

    $stagedPaths = @(& git -C $gitRoot diff --cached --name-only --)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect staged Git changes."
    }
    $unstagedPaths = @(& git -C $gitRoot diff --name-only --)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect unstaged Git changes."
    }
    $untrackedPaths = @(& git -C $gitRoot ls-files --others --exclude-standard)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect untracked Git files."
    }

    $stagedPaths = @($stagedPaths | ForEach-Object { ConvertTo-NormalizedGitPath -Path ([string]$_) } | Where-Object { $_ } | Sort-Object -Unique)
    $changedPaths = @($stagedPaths + $unstagedPaths + $untrackedPaths |
        ForEach-Object { ConvertTo-NormalizedGitPath -Path ([string]$_) } |
        Where-Object { $_ } |
        Sort-Object -Unique)

    return [pscustomobject]@{
        GitRoot = $gitRoot
        PaperPathPrefix = $paperPathPrefix
        ChangedPaths = $changedPaths
        StagedPaths = $stagedPaths
    }
}

function Get-GitPaperPublishPlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AsOfDate,
        [string]$RemoteName = "origin",
        [string]$BranchName = "main",
        [AllowEmptyString()]
        [string]$PaperPathPrefix = "",
        [string[]]$ChangedPaths = @(),
        [string[]]$StagedPaths = @()
    )

    $normalizedChangedPaths = @($ChangedPaths | ForEach-Object { ConvertTo-NormalizedGitPath -Path ([string]$_) } | Where-Object { $_ } | Sort-Object -Unique)
    $normalizedStagedPaths = @($StagedPaths | ForEach-Object { ConvertTo-NormalizedGitPath -Path ([string]$_) } | Where-Object { $_ } | Sort-Object -Unique)

    if ($normalizedStagedPaths.Count -gt 0) {
        throw "Paper publishing requires an empty Git index. Staged paths: $($normalizedStagedPaths -join ', ')"
    }

    $outsidePaperPaths = @($normalizedChangedPaths | Where-Object {
        -not (Test-GitPathWithinPaper -Path $_ -PaperPathPrefix $PaperPathPrefix)
    })
    if ($outsidePaperPaths.Count -gt 0) {
        throw "Paper publishing refused because changes exist outside Paper: $($outsidePaperPaths -join ', ')"
    }

    $allowlistedPaths = @($normalizedChangedPaths | Where-Object {
        Test-GitPathAllowedForPaperPublish -Path $_ -PaperPathPrefix $PaperPathPrefix
    })
    $skippedPaperPaths = @($normalizedChangedPaths | Where-Object {
        -not (Test-GitPathAllowedForPaperPublish -Path $_ -PaperPathPrefix $PaperPathPrefix)
    })
    $pathspecs = @(Get-GitPaperPublishPathspecs -PaperPathPrefix $PaperPathPrefix)
    $commitMessage = "Update paper recommendations for $AsOfDate"
    $commands = New-Object System.Collections.Generic.List[string]

    if ($allowlistedPaths.Count -gt 0) {
        $quotedPathspecs = @($pathspecs | ForEach-Object { "`"$_`"" })
        [void]$commands.Add("git add -- $($quotedPathspecs -join ' ')")
        [void]$commands.Add("git commit -m `"$commitMessage`"")
        [void]$commands.Add("git push $RemoteName HEAD:$BranchName")
    }

    return [pscustomobject]@{
        HasChanges = $allowlistedPaths.Count -gt 0
        CommitMessage = $commitMessage
        Commands = $commands.ToArray()
        Pathspecs = $pathspecs
        AllowlistedPaths = $allowlistedPaths
        SkippedPaperPaths = $skippedPaperPaths
    }
}

function Assert-GitPaperPublishReady {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [string]$RemoteName = "origin"
    )

    $state = Get-GitPaperRepositoryState -ProjectRoot $ProjectRoot
    Get-GitPaperPublishPlan -AsOfDate "preflight" -PaperPathPrefix $state.PaperPathPrefix -ChangedPaths $state.ChangedPaths -StagedPaths $state.StagedPaths | Out-Null

    $remoteNames = @(& git -C $state.GitRoot remote)
    if ($LASTEXITCODE -ne 0 -or ($remoteNames -notcontains $RemoteName)) {
        throw "Paper publishing requires remote '$RemoteName' to be configured."
    }

    return $state
}

function Invoke-GitPaperCommitPush {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [Parameter(Mandatory = $true)]
        [string]$AsOfDate,
        [string]$RemoteName = "origin",
        [string]$BranchName = "main"
    )

    function Invoke-GitPaperCommand {
        param(
            [Parameter(Mandatory = $true)]
            [string[]]$Arguments,
            [Parameter(Mandatory = $true)]
            [string]$FailureMessage
        )

        $output = @(& git @Arguments 2>&1)
        $exitCode = $LASTEXITCODE
        foreach ($line in $output) {
            if ($line) {
                Write-Host $line
            }
        }
        if ($exitCode -ne 0) {
            throw $FailureMessage
        }
    }

    $state = Assert-GitPaperPublishReady -ProjectRoot $ProjectRoot -RemoteName $RemoteName
    $plan = Get-GitPaperPublishPlan -AsOfDate $AsOfDate -RemoteName $RemoteName -BranchName $BranchName -PaperPathPrefix $state.PaperPathPrefix -ChangedPaths $state.ChangedPaths

    if (-not $plan.HasChanges) {
        Write-Host "No allowlisted Paper changes to commit; push skipped."
        return [pscustomobject]@{
            HasCommittedChanges = $false
            HasPushed = $false
            CommitMessage = $plan.CommitMessage
            RemoteName = $RemoteName
            BranchName = $BranchName
            SkippedPaperPaths = $plan.SkippedPaperPaths
        }
    }

    $addArguments = @("-C", $state.GitRoot, "add", "--") + @($plan.Pathspecs)
    Invoke-GitPaperCommand -Arguments $addArguments -FailureMessage "Git add failed during Paper publishing."

    $stagedState = Get-GitPaperRepositoryState -ProjectRoot $ProjectRoot
    $outsidePaperPaths = @($stagedState.ChangedPaths | Where-Object {
        -not (Test-GitPathWithinPaper -Path $_ -PaperPathPrefix $stagedState.PaperPathPrefix)
    })
    if ($outsidePaperPaths.Count -gt 0) {
        throw "Paper publishing stopped because changes appeared outside Paper: $($outsidePaperPaths -join ', ')"
    }

    $unexpectedStagedPaths = @($stagedState.StagedPaths | Where-Object {
        -not (Test-GitPathAllowedForPaperPublish -Path $_ -PaperPathPrefix $stagedState.PaperPathPrefix)
    })
    if ($unexpectedStagedPaths.Count -gt 0) {
        throw "Paper publishing stopped because non-allowlisted paths were staged: $($unexpectedStagedPaths -join ', ')"
    }

    if ($stagedState.StagedPaths.Count -eq 0) {
        Write-Host "No allowlisted Paper changes were staged; commit and push skipped."
        return [pscustomobject]@{
            HasCommittedChanges = $false
            HasPushed = $false
            CommitMessage = $plan.CommitMessage
            RemoteName = $RemoteName
            BranchName = $BranchName
            SkippedPaperPaths = $plan.SkippedPaperPaths
        }
    }

    Invoke-GitPaperCommand -Arguments @("-C", $state.GitRoot, "commit", "-m", $plan.CommitMessage) -FailureMessage "Git commit failed during Paper publishing."
    Invoke-GitPaperCommand -Arguments @("-C", $state.GitRoot, "push", $RemoteName, "HEAD:$BranchName") -FailureMessage "Git push failed during Paper publishing."

    return [pscustomobject]@{
        HasCommittedChanges = $true
        HasPushed = $true
        CommitMessage = $plan.CommitMessage
        RemoteName = $RemoteName
        BranchName = $BranchName
        SkippedPaperPaths = $plan.SkippedPaperPaths
    }
}

Export-ModuleMember -Function Get-PaperSearchConfig, Merge-StringArray, Get-NormalizedTitle, Get-RelevanceRank, ConvertTo-ScoredPaperRecord, Merge-PaperRecords, New-DailyReportContent, New-GaussianMethodReviewContent, New-MasterIndexMarkdown, New-GaussianIndexMarkdown, New-GaussianImplementationNotesContent, New-GaussianQualityControlContent, New-GaussianUncertaintyNotesContent, New-GaussianDailyContent, New-CodeSuggestionContent, ConvertTo-CsvFriendlyRecords, ConvertTo-GaussianCsvFriendlyRecords, Get-GitPaperPublishPlan, Assert-GitPaperPublishReady, Invoke-GitPaperCommitPush, Get-ProjectRoot
