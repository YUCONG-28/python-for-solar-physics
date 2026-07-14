[CmdletBinding()]
param(
    [string]$AsOfDate = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$SkipLiveSearch,
    [switch]$Check,
    [switch]$CommitAndPush,
    [string]$GitRemote = "origin",
    [string]$GitBranch = "main"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Import-Module (Join-Path $PSScriptRoot "LiteratureCatalog.psm1") -Force -DisableNameChecking
$paths = Resolve-LiteratureCatalogPaths -ToolRoot $PSScriptRoot

if ($Check -and $CommitAndPush) {
    throw "-Check cannot be combined with -CommitAndPush."
}

if ($CommitAndPush) {
    [void](Assert-GitLiteraturePublishReady -ProjectRoot $paths.ProjectRoot -RemoteName $GitRemote)
}

$result = Invoke-LiteratureCatalogUpdate `
    -ConfigPath $paths.ConfigPath `
    -CatalogJsonPath $paths.CatalogJsonPath `
    -CatalogMarkdownPath $paths.CatalogMarkdownPath `
    -AsOfDate $AsOfDate `
    -SkipLiveSearch:$SkipLiveSearch `
    -Check:$Check

if ($Check) {
    Write-Host "Literature catalog check passed: $($result.TotalPapers) papers; Markdown matches JSON."
    exit 0
}

Write-Host "Literature catalog update completed: $($result.TotalPapers) papers ($($result.AddedPapers) added)."
if ($result.LiveSearchUsed) {
    foreach ($sourceName in @("Arxiv", "Crossref")) {
        $status = $result.SourceStatus.$sourceName
        Write-Host "$($status.Source): state=$($status.State); successful_queries=$($status.SuccessfulQueries); failed_queries=$($status.FailedQueries); candidates=$($status.CandidateCount); rejected_by_date=$($status.RejectedByDate)."
    }
}
if ($result.UpdatedFiles.Count -eq 0) {
    Write-Host "No catalog files changed."
}
else {
    foreach ($path in @($result.UpdatedFiles)) {
        Write-Host "Updated: $path"
    }
}

if ($CommitAndPush) {
    $publishResult = Invoke-GitLiteratureCommitPush `
        -ProjectRoot $paths.ProjectRoot `
        -AsOfDate $AsOfDate `
        -RemoteName $GitRemote `
        -BranchName $GitBranch
    if ($publishResult.HasCommittedChanges) {
        Write-Host "Committed and pushed the two-file literature catalog to $GitRemote/$GitBranch."
    }
    else {
        Write-Host "No allowlisted catalog changes were committed or pushed."
    }
}
else {
    Write-Host "Git commit and push were not requested."
}
