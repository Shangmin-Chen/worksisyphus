# Deterministic Resume Compiler Plan

## Objective

Build a resume and cover-letter system where Gemini never writes final TeX. Gemini may interpret messy input and propose a structured selection plan, but trusted local code owns all formatting, escaping, rendering, caching, compilation, and filesystem writes.

The target guarantee is:

```text
same normalized SelectionPlan
+ same TemplateSpec
+ same canonical profile data
+ same renderer version
+ same compiler config
= same generated TeX
```

Gemini planning is allowed to vary. Artifact generation is not.

## Benchmark Target

The project should move toward an A-grade TUI/document tool benchmark:

- Deterministic renderer with exact TeX snapshot tests.
- Strict schema validation for planner output.
- Atomic writes for TeX, PDF, logs, and cache metadata.
- No compilation of user-supplied or Gemini-supplied TeX.
- Cached plans and cached artifacts with stable keys.
- Compile backend reports truthful structured success/failure.
- TUI actions are non-blocking, testable, cancellable where practical, and never leave ambiguous state.
- Tests cover schema, validator, renderer, cache identity, atomic write behavior, compiler failure, and TUI flows.

## Current Problems To Remove

- `src/generate.py` asks Gemini to produce final LaTeX.
- `src/compile.py` generates TeX directly from the full JSON without a selection plan.
- Compile helpers swallow errors and can print success paths after failure.
- Writes overwrite output paths directly.
- The TUI accepts pasted TeX as an output artifact instead of treating it as import input.
- There are no automated tests.
- Generated PDFs and local build artifacts are mixed with source-controlled outputs.

## Core Concepts

### CanonicalProfile

The authoritative candidate data. In the current repo this is `templates/experiences.json`, but it should be loaded into typed Python data structures.

Canonical data may include:

- Contact data.
- Education entries.
- Experience entries.
- Project entries.
- Skill groups.
- Stable IDs for every selectable item.
- Stable IDs for bullets.

If older JSON has no IDs, the loader may derive deterministic IDs from names, roles, dates, and bullet indexes. The derived IDs must be stable and validated for collisions.

### RawInput

Any untrusted user input:

- Job descriptions.
- Pasted resume TeX.
- Pasted cover-letter TeX.
- Notes.
- Company/role text.

Raw input is never compiled and never rendered directly. It is only used by a planner.

### SelectionPlan

The only Gemini-controlled artifact that can influence output content. It must be JSON and must contain references to canonical data, not TeX.

Typical fields:

- `document_type`: `resume` or `cover_letter`.
- `template_id`.
- `target.company`.
- `target.role`.
- `sections`.
- `education_ids`.
- `experience_ids`.
- `project_ids`.
- `bullet_ids_by_item`.
- `skill_ids_by_group`.
- Optional `rationale` excluded from artifact hashing.

Planner output is not trusted until validated and normalized.

### TemplateSpec

Versioned metadata for a template. It captures the structural formatting contract used by the renderer.

Typical fields:

- `id`.
- `version`.
- `document_type`.
- `source_template`.
- `section_order`.
- `max_experiences`.
- `max_projects`.
- `max_bullets_per_experience`.
- `max_bullets_per_project`.
- `skill_group_order`.
- `page_limit`.
- `preamble`.
- `command_profile`.
- `spacing_profile`.

Template specs should be checked in and edited intentionally. Inferring specs from `.tex` files is out of scope for normal runtime.

### RenderModel

The exact content that will appear in the document after applying a valid `SelectionPlan` to `CanonicalProfile` under a `TemplateSpec`.

This is where max counts, section order, fallback content, and missing optional fields are resolved.

### TexRenderer

A pure deterministic compiler:

```text
RenderModel + TemplateSpec -> TeX string
```

It must do no filesystem IO, no Gemini calls, and no subprocess calls.

### ArtifactStore

The only layer that writes user-facing outputs and cached artifacts. It owns:

- Atomic temp-file writes.
- Cache-key calculation.
- Artifact lookup.
- Exporting cached artifacts to requested output names.
- Metadata records linking requested jobs to artifact hashes.

### CompilerBackend

The layer that compiles trusted renderer output to PDF. It must:

- Compile in an isolated temporary build directory.
- Use explicit argv, never shell interpolation.
- Use timeouts.
- Capture logs.
- Return structured status.
- Only publish PDF artifacts after the PDF exists and passes basic checks.

## Cache Design

Use two separate caches.

### Plan Cache

Purpose: avoid another Gemini call for the exact same planning request.

Key inputs:

- Raw input hash.
- Canonical profile hash.
- Template ID.
- Prompt version.
- Model ID.
- Planner schema version.

Value:

- Raw planner JSON.
- Normalized `SelectionPlan`.
- Validation report.
- Timestamp and metadata.

### Artifact Cache

Purpose: avoid rendering and compiling the same artifact more than once, even across different jobs.

Key inputs:

- Normalized `SelectionPlan` without rationale.
- Template spec hash.
- Canonical profile hash.
- Renderer version.
- Compiler config version.

Value:

- TeX artifact.
- PDF artifact when compilation succeeds.
- Compile log.
- Metadata.

If job 1 and job 2 normalize to the same artifact key, the system should export/copy the existing cached PDF and TeX instead of recompiling.

## Normalization Rules

- Sort JSON object keys before hashing.
- Preserve ordered lists where visual order matters: sections, experience IDs, project IDs, bullet IDs.
- Sort unordered metadata and rationale fields only if they are retained for diagnostics.
- Exclude rationale, timestamps, Gemini response IDs, and token usage from artifact hash.
- Lowercase and trim IDs.
- Reject duplicate IDs.
- Reject unknown IDs.
- Enforce template max counts before hashing.

## Safety Rules

Within spec:

- Gemini chooses canonical IDs.
- Gemini proposes target company and role as plain strings.
- Pasted TeX is treated as raw input for planning only.
- Renderer emits whitelisted commands from `TemplateSpec`.
- User text is escaped before rendering.
- Existing cached artifacts can be exported under new requested names.

Out of spec:

- Gemini emits final TeX.
- User-pasted TeX is compiled directly.
- Unknown TeX commands are passed through from input.
- Compile failures return success paths.
- Files are overwritten directly without temp-file publishing.
- Artifact hash includes nondeterministic metadata.
- Plan validation silently drops invalid IDs without diagnostics.

## Atomicity Rules

- Write new files to a temp path in the same directory.
- Flush and fsync file contents before rename.
- Rename into place with `os.replace`.
- For user-facing exports, publish TeX first, then PDF, then metadata.
- If PDF compile fails, preserve the TeX and log in the artifact store but do not claim a PDF export succeeded.
- Never remove an old successful artifact until the new artifact is complete.

## Determinism Rules

- Rendering must be pure and byte-stable.
- JSON serialization used for hashes must be canonical.
- Dates in generated content must come from explicit inputs or be omitted; the renderer must not call `today`.
- Compile logs and PDF bytes may vary by environment; tests should benchmark PDF page count and extracted/rendered content, not raw PDF bytes.
- Snapshot tests compare TeX exactly.

## Slice Plan

### Slice 0: Planning Artifact

Deliverables:

- This document.
- Explicit in-scope and out-of-scope rules.
- Acceptance criteria for later slices.

Acceptance:

- The plan names data contracts, cache contracts, safety rules, atomicity rules, determinism rules, tests, and migration steps.

### Slice 1: Data Contracts And Validation

Deliverables:

- New package module for canonical profile loading.
- Typed model layer for `TemplateSpec`, `SelectionPlan`, `RenderModel`, and validation errors.
- Stable ID derivation for legacy `experiences.json`.
- Built-in template specs for current resume and cover-letter templates.
- Unit tests for ID derivation and invalid plans.

Acceptance:

- Unknown experience, project, bullet, skill, or section IDs are rejected.
- Duplicate IDs are rejected.
- Counts above template limits are rejected or deterministically trimmed only if configured.
- Normalized valid plans serialize deterministically.
- No rendering or Gemini changes are required in this slice.

Edge cases:

- Two experiences derive the same ID.
- Bullet text contains LaTeX special characters.
- Plan asks for a project bullet under an experience ID.
- Plan omits optional sections.
- Existing profile lacks stable IDs.

### Slice 2: Deterministic Renderer And Artifact Store

Deliverables:

- `TexRenderer` pure functions for resume output using `RenderModel`.
- Atomic write helper.
- Artifact cache key calculation.
- Artifact store that exports cached TeX and PDF paths.
- Tests for exact TeX snapshots and cache identity.

Acceptance:

- Same `RenderModel` and `TemplateSpec` produce byte-identical TeX.
- `\resumeSubItem` recursion bug is gone.
- User content is escaped.
- Atomic writes do not leave partial final files on simulated failure.
- Artifact hash ignores rationale and keeps order-sensitive fields.

Edge cases:

- Empty skill group.
- Long URL or missing optional contact field.
- Missing optional project technologies.
- Repeated export names.
- Cache hit for two different raw jobs with identical normalized plans.

### Slice 3: Safe Compiler Backend

Deliverables:

- Isolated TeX-to-PDF compiler backend.
- Structured compile result.
- Timeout and captured logs.
- Publish only after PDF exists.
- Tests for success and failure where local TeX tooling is available, plus mocked failure tests.

Acceptance:

- Compile failure returns nonzero status and does not claim success.
- Logs are retained.
- No user/Gemini raw TeX can enter the compiler through public APIs.

Edge cases:

- Missing `latexmk`.
- `pdflatex` fallback unavailable.
- Generated TeX fails to compile.
- Existing output PDF exists and new compile fails.

### Slice 4: Gemini Planner

Deliverables:

- Replace TeX-generation prompt with planner prompt.
- Gemini returns JSON matching `SelectionPlan`.
- Planner cache.
- Plan validation before any render or compile.
- Deterministic fallback planner for API failure.

Acceptance:

- Gemini output cannot include TeX that reaches the compiler.
- Invalid JSON fails clearly.
- Unknown IDs fail clearly.
- Exact same raw request can reuse cached plan.

Edge cases:

- Gemini returns markdown fenced JSON.
- Gemini returns rationale only.
- Gemini chooses too many bullets.
- Gemini references IDs from old profile version.
- API timeout.

### Slice 5: CLI And TUI Migration

Deliverables:

- CLI commands for plan, render, compile, and generate.
- TUI "Add TeX" becomes "Import Raw Text/TeX".
- TUI generate path writes plan, generated TeX, PDF, and logs through the artifact store.
- `--help` works for CLI surfaces.

Acceptance:

- No UI path writes raw TeX into `tex_files/` as trusted output.
- TUI cannot compile unvalidated input.
- Logs distinguish plan cache hit, artifact cache hit, render, compile, and export.

Edge cases:

- Empty JD.
- No template selected.
- Invalid imported TeX.
- Multiple clicks while a job is running.
- Output name collision.

### Slice 6: Benchmark And Docs

Deliverables:

- Pytest suite.
- Snapshot fixtures.
- Benchmark command that scores determinism, validation, cache hits, compile status, and TUI smoke behavior.
- Updated README.

Acceptance:

- Tests are runnable with one command.
- Benchmark reports pass/fail criteria and a numeric score.
- README no longer promises AI-written TeX.

## Test Matrix

- `test_profile_ids.py`: stable IDs and collision handling.
- `test_selection_plan.py`: valid/invalid plan normalization.
- `test_template_specs.py`: known template metadata.
- `test_renderer_resume.py`: exact TeX snapshot.
- `test_renderer_escape.py`: all special characters escape safely.
- `test_artifact_cache.py`: same plan hits same artifact, rationale ignored.
- `test_atomic_write.py`: simulated failure leaves previous output intact.
- `test_compiler_backend.py`: success/failure status.
- `test_planner.py`: fenced JSON parsing, invalid JSON, fallback planner.
- `test_tui.py`: headless Textual smoke tests for disabled invalid actions.

## Reviewer Checklist

Every reviewer must check:

- Does this slice obey the no-Gemini-TeX rule?
- Are all new writes atomic or isolated?
- Is any nondeterministic value included in artifact hashes?
- Are invalid inputs rejected with useful diagnostics?
- Are old user changes preserved?
- Do tests prove the slice acceptance criteria, or only exercise a narrow happy path?
- Does the implementation match this plan, and if not, is the deviation intentional and reported?

