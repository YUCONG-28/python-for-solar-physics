# Solar Research Workspace Instructions

These instructions coordinate the public `Paper`, `Python`, and `Apps`
partitions plus the ignored `Local` runtime tree. Finance and study-abroad work
remain separate.

## Python environments

- Prefer a repository-specific interpreter such as a project `.venv` when the
  repository explicitly defines one.
- Otherwise use the `solarphysics_env_latest` interpreter under the configured
  Miniforge root for current work in this workspace.
- Use `solarphysics_env` as the supported old-version fallback only when a
  compatibility comparison or rollback is explicitly needed.
- The old fallback retains known Conda ownership warnings and does not include
  newer optional packages such as FITSIO and PyQtGraph. Workflows that need
  those packages must stay on `solarphysics_env_latest`.
- `solarphysics_backup` has been removed and is unsupported. Do not recreate
  or select it automatically.
- Switch with the existing Conda activation commands or the application's
  existing interpreter option; do not introduce a separate switch script.

## Routing

- Route manuscripts, literature notes, citations, DOI checks, and publication
  status through `academic-paper-director`, then follow `Paper\AGENTS.md` and
  use `Paper\catalog` as the literature source of record and
  `tools\literature` for catalog retrieval, validation, and publication.
- Route scientific presentation style and outline work through
  `ppt-style-director`. Use `presentation-skill` or `Presentations` for an
  editable `.pptx` and perform render-based QA before delivery.
- Use `Python` for reusable scientific code and reproducible analysis. Use
  `Apps` for versioned frontends, application workflows, and their tests. A
  literature recommendation is not an implemented code change.

## Cross-repository boundaries

- Treat Paper as the evidence and publication-metadata layer, Python as the
  reusable implementation layer, Apps as the application layer, and Local as
  private runtime state.
- When a task spans both repositories, state which evidence is consumed by
  Python and verify each repository independently.
- Do not copy director-skill instructions into project data or generated
  outputs; keep detailed style policy in the skills themselves.
- Do not send raw observations, bulk generated figures, local absolute paths,
  manuscripts, or personal source files to Work, Calendar, Sites, or other
  external surfaces unless the user explicitly selects a reviewed subset.
- Do not commit, push, merge, or clean one repository merely because work in
  the other repository completed.
