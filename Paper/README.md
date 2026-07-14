# Paper Evidence Library

`Paper/` is the static evidence partition of the solar-physics workspace. It
stores a canonical literature catalog, a deterministic Markdown view, and a
small set of paper-backed method notes. Search, validation, and publication
logic lives outside this directory under `tools/literature/`.

## Contents

- `catalog/papers.json`: canonical, lossless literature records.
- `catalog/papers.md`: deterministic human-readable view generated from the
  JSON catalog.
- `methods/gaussian-fitting.md`: stable Gaussian fitting and source-centroid
  guidance tied to cataloged papers.
- `00_local_documents/`: ignored local PDFs, manuscripts, and theses. These
  files are not uploaded or tracked with Git LFS.

`Paper/` does not store dated recommendations, execution logs, run state,
automation plans, or repository history notes.

## Catalog contract

Treat `catalog/papers.json` as the source of truth. Preserve the full record
schema and update publication metadata only from evidence-backed sources.
Preprints, accepted manuscripts, conference or book chapters, and formally
published papers must remain distinct.

Do not edit `catalog/papers.md` independently. Regenerate it from the JSON
catalog so the two files remain consistent. Title, DOI, and arXiv identifiers
are the deduplication keys; an arXiv record must not overwrite a verified
formal publication.

## Updating and checking

Run the literature workflow from the workspace root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\literature\update_catalog.ps1
```

For an offline, read-only consistency check:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\literature\update_catalog.ps1 -Check
```

Use `-SkipLiveSearch` when an update should rely only on the existing catalog.
Publishing requires an explicit `-CommitAndPush`; the publication allowlist is
limited to `catalog/papers.json` and `catalog/papers.md`.

## Local documents

PDF, DOC, and DOCX files under `00_local_documents/` are private local research
inputs. Keep their existing paths intact. They are ignored by Git, are not Git
LFS objects, and must not be included in automated publication.
