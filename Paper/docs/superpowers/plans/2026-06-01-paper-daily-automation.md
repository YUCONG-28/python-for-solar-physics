# Paper Daily Recommendation Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local PowerShell workflow that searches, scores, indexes, and summarizes daily papers for the `spikes topping type III` project without claiming unsupported background automation.

**Architecture:** Keep the workflow self-contained inside `Paper/` with a PowerShell module for scoring/rendering, a thin entry script for execution, a seed library for baseline papers, and generated markdown/CSV outputs for daily review. Live retrieval should be optional and degradable so the workflow still produces useful outputs when network access or API credentials are unavailable.

**Tech Stack:** Windows PowerShell 5.1, Pester 3.4, JSON configuration, CSV/Markdown outputs, public APIs such as arXiv/Crossref and optional NASA ADS token.

---

### Task 1: Scaffold the workflow and tests

**Files:**
- Create: `D:\solarphysics\Paper\tests\PaperRecommendation.Tests.ps1`
- Create: `D:\solarphysics\Paper\config\paper_search_config.json`
- Create: `D:\solarphysics\Paper\data\seed_papers.json`

- [ ] **Step 1: Write failing tests for scoring, deduplication, and report sections**
- [ ] **Step 2: Run the Pester file and confirm missing-module failures**
- [ ] **Step 3: Add the minimal config and seed data needed by the future module**
- [ ] **Step 4: Re-run Pester and confirm the same API gaps remain the only failures**

### Task 2: Implement the PowerShell recommendation module

**Files:**
- Create: `D:\solarphysics\Paper\scripts\PaperRecommendation\PaperRecommendation.psm1`

- [ ] **Step 1: Implement keyword-group loading, title normalization, and relevance scoring**
- [ ] **Step 2: Implement record conversion, deduplication, and markdown rendering helpers**
- [ ] **Step 3: Re-run targeted Pester tests until the scoring/report tests pass**

### Task 3: Implement the executable daily runner

**Files:**
- Create: `D:\solarphysics\Paper\scripts\paper_daily_recommendation.ps1`

- [ ] **Step 1: Add project-structure creation and seed-paper loading**
- [ ] **Step 2: Add optional live retrieval wrappers for arXiv/Crossref and graceful fallback**
- [ ] **Step 3: Add writers for daily report, master index, Gaussian-method files, and method suggestions**
- [ ] **Step 4: Re-run Pester and a dry-run execution to verify outputs are produced**

### Task 4: Add local execution and scheduling guidance

**Files:**
- Create: `D:\solarphysics\Paper\README.md`
- Create: `D:\solarphysics\Paper\scripts\setup_daily_task.ps1`
- Create: `D:\solarphysics\Paper\scripts\paper_daily_recommendation_task.xml`

- [ ] **Step 1: Document manual execution, optional credential variables, and output paths**
- [ ] **Step 2: Add a Task Scheduler registration script and an importable XML task definition**
- [ ] **Step 3: Verify the XML and PowerShell command lines point at the correct workspace**

### Task 5: Generate the first managed outputs for 2026-06-01

**Files:**
- Create: `D:\solarphysics\Paper\daily_recommendations\2026-06-01_paper_recommendations.md`
- Create: `D:\solarphysics\Paper\paper_master_index.csv`
- Create: `D:\solarphysics\Paper\paper_master_index.md`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_paper_index.csv`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_paper_index.md`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_method_review.md`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_implementation_notes.md`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_quality_control.md`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_uncertainty_notes.md`
- Create: `D:\solarphysics\Paper\02_methods_gaussian_fitting\gaussian_fitting_literature_daily\2026-06-01_gaussian_fitting_papers.md`
- Create: `D:\solarphysics\Paper\08_project_method_notes\gaussian_fitting_code_improvement_suggestions_2026-06-01.md`

- [ ] **Step 1: Run the entry script for `2026-06-01` with seed papers and no destructive reorganization**
- [ ] **Step 2: Inspect the generated markdown/CSV files for required sections and paths**
- [ ] **Step 3: Record the run summary in the automation memory file**
