$modulePath = Join-Path (Split-Path -Parent $PSScriptRoot) "scripts\PaperRecommendation\PaperRecommendation.psm1"
Import-Module $modulePath -Force

Describe "ConvertTo-ScoredPaperRecord" {
    It "marks Gaussian centroid imaging papers as high relevance" {
        $config = Get-PaperSearchConfig -ConfigPath (Join-Path (Split-Path -Parent $PSScriptRoot) "config\paper_search_config.json")

        $rawPaper = [pscustomobject]@{
            title = "On the Source Position and Duration of a Solar Type III Radio Burst Observed by LOFAR"
            authors = @("M. Zhang", "D. L. Clarkson")
            year = 2019
            journal = "ApJ"
            doi = "10.3847/1538-4357/ab45f5"
            arxiv_id = ""
            ads_url = "https://ui.adsabs.harvard.edu/abs/2019ApJ...885..124Z"
            pdf_url = ""
            local_pdf_path = ""
            summary = "This study tracks the apparent source position, directivity and duration of a type III solar radio burst with LOFAR imaging spectroscopy, including source motion and scattering context."
            topic_tags = @("type III radio burst", "radio source centroid", "LOFAR", "Gaussian fitting")
            method_tags = @("radio source centroid", "source trajectory")
            date_added = "2026-06-01"
        }

        $record = ConvertTo-ScoredPaperRecord -Paper $rawPaper -Config $config

        $record.relevance_level | Should Be "A"
        $record.uses_gaussian_fitting | Should Be $true
        $record.uses_radio_centroid | Should Be $true
        $record.uses_frequency_drift_rate | Should Be $true
    }
}

Describe "Merge-PaperRecords" {
    It "deduplicates by normalized title and keeps combined topic tags" {
        $first = [pscustomobject]@{
            title = "Type-III solar radio bursts with spike-like toppings"
            topic_tags = @("type III radio burst")
            method_tags = @("frequency drift rate")
            relevance_level = "A"
            recommended_priority = "high"
        }

        $second = [pscustomobject]@{
            title = "Type III solar radio bursts with spike like toppings"
            topic_tags = @("solar radio spikes")
            method_tags = @("fine structures")
            relevance_level = "A"
            recommended_priority = "high"
        }

        $merged = Merge-PaperRecords -PaperRecords @($first, $second)

        $merged.Count | Should Be 1
        ($merged[0].topic_tags -join ";") | Should Match "type III radio burst"
        ($merged[0].topic_tags -join ";") | Should Match "solar radio spikes"
    }
}

Describe "New-DailyReportContent" {
    It "contains the required sections for the solar physics workflow" {
        $report = New-DailyReportContent -AsOfDate "2026-06-01" -KeywordSummary @("spikes topping type III") -RecommendedPapers @()

        $report | Should Match "# 2026-06-01 文献检索日报"
        $report | Should Match "## 6. 与 Gaussian fitting / radio source centroid 相关论文"
        $report | Should Match "## 9. 对当前项目的具体建议"
        $report | Should Match "## 10. 今日更新文件列表"
    }
}

Describe "New-GaussianMethodReviewContent" {
    It "documents contour comparison and apparent-size caveats" {
        $content = New-GaussianMethodReviewContent -GaussianPapers @()

        $content | Should Match "Gaussian fitted center"
        $content | Should Match "contour center"
        $content | Should Match "observed apparent size"
    }
}

Describe "Get-GitAutoPushPlan" {
    It "commits and pushes when generated files changed" {
        $plan = Get-GitAutoPushPlan -AsOfDate "2026-06-08" -RemoteName "origin" -BranchName "main" -StatusPorcelain " M paper_master_index.csv"

        $plan.HasChanges | Should Be $true
        $plan.CommitMessage | Should Be "Update paper recommendations for 2026-06-08"
        ($plan.Commands -join "`n") | Should Match "git add -A"
        ($plan.Commands -join "`n") | Should Match "git commit -m"
        ($plan.Commands -join "`n") | Should Match "git push origin HEAD:main"
        ($plan.Commands -join "`n") | Should Match "git lfs push origin main"
    }

    It "still pushes when there are no generated file changes" {
        $plan = Get-GitAutoPushPlan -AsOfDate "2026-06-08" -RemoteName "origin" -BranchName "main" -StatusPorcelain ""

        $plan.HasChanges | Should Be $false
        ($plan.Commands -join "`n") | Should Not Match "git commit"
        ($plan.Commands -join "`n") | Should Match "git push origin HEAD:main"
        ($plan.Commands -join "`n") | Should Match "git lfs push origin main"
    }
}

Describe "paper_daily_recommendation.ps1 entrypoint" {
    It "resolves default config and seed paths when run through powershell -File" {
        $repoRoot = Split-Path -Parent $PSScriptRoot
        $scriptPath = Join-Path $repoRoot "scripts\paper_daily_recommendation.ps1"
        $statePath = Join-Path $repoRoot ".paper_recommendation_state.json"
        $originalState = if (Test-Path -LiteralPath $statePath) {
            Get-Content -Raw -Encoding UTF8 -Path $statePath
        }
        else {
            $null
        }
        $testDate = "2099-01-01"

        try {
            $output = & powershell -NoProfile -ExecutionPolicy Bypass -File $scriptPath -AsOfDate $testDate -SkipLiveSearch -SkipGitPush 2>&1
            $exitCode = $LASTEXITCODE

            $exitCode | Should Be 0
            ($output -join "`n") | Should Match "Generated daily report"
        }
        finally {
            $generatedPaths = @(
                "daily_recommendations\$testDate`_paper_recommendations.md",
                "02_methods_gaussian_fitting\gaussian_fitting_literature_daily\$testDate`_gaussian_fitting_papers.md",
                "08_project_method_notes\gaussian_fitting_code_improvement_suggestions_$testDate.md",
                "organization_log_$testDate.md"
            )

            foreach ($relativePath in $generatedPaths) {
                $fullPath = Join-Path $repoRoot $relativePath
                if (Test-Path -LiteralPath $fullPath) {
                    Remove-Item -LiteralPath $fullPath -Force
                }
            }

            if ($null -eq $originalState) {
                if (Test-Path -LiteralPath $statePath) {
                    Remove-Item -LiteralPath $statePath -Force
                }
            }
            else {
                Set-Content -Encoding UTF8 -Path $statePath -Value $originalState
            }
        }
    }
}
