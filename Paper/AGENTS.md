# Paper Evidence Library Instructions

These instructions apply to `D:\solarphysics\Paper` and its subdirectories.

## Static evidence boundary

- Keep this partition limited to the literature catalog, its deterministic
  Markdown view, paper-backed method notes, and ignored local documents.
- Do not add scripts, runtime configuration, tests, run state, dated reports,
  automation plans, execution logs, or history notes under `Paper/`.
- Search, merge, validation, and publication behavior belongs in the workspace
  root under `tools/literature/`.

## Catalog and metadata

- Treat `catalog/papers.json` as the canonical record set and preserve its full
  schema when updating records.
- Generate `catalog/papers.md` deterministically from the JSON catalog; never
  maintain the two files independently.
- Deduplicate by normalized title, DOI, and arXiv identifier.
- Keep preprint, accepted, conference or chapter, and formally published states
  separate. An arXiv result must not replace verified publication metadata.
- Prefer DOI, Crossref, publisher, or exact arXiv evidence. Record uncertainty
  rather than inferring missing publication facts.

## Method notes

- Keep Gaussian/source-centroid guidance tied to papers in the catalog.
- Distinguish observed apparent source size from beam-deconvolved intrinsic
  size, and keep propagation or scattering limitations explicit.
- Treat type II or herringbone papers as method-transfer evidence only; do not
  transfer their physical conclusions to type III spike-topping events.
- Mark details that still require full-text verification instead of smoothing
  over the gap.

## Local documents and external surfaces

- Keep PDF, DOC, and DOCX files under `00_local_documents/` local and ignored.
  They are not Git LFS objects and must not be staged, uploaded, or published.
- Do not send manuscripts or local literature files to Work, Calendar, Sites,
  or other external surfaces without an explicit request and reviewed subset.

## Workflow and verification

- Use `academic-paper-director` for literature notes, citations, DOI checks,
  publication-status claims, and restrained academic style.
- From the workspace root, run the read-only check with
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\literature\update_catalog.ps1 -Check`,
  then run the focused literature tests after catalog or method changes.
- Report sources checked, catalog changes, validation results, and unresolved
  metadata. Do not claim a commit, push, or remote publication without direct
  evidence.
