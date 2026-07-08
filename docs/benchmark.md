# Deterministic Compiler Benchmark

Run the benchmark from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python src/benchmark.py
```

For machine-readable output:

```bash
PYTHONDONTWRITEBYTECODE=1 python src/benchmark.py --json
```

The benchmark is intentionally local and deterministic. It runs `unittest`
discovery, checks renderer/cache invariants, probes safe compiler behavior with
temporary directories, audits CLI/TUI source paths, and reports an optional real
TeX engine smoke when `latexmk` or `pdflatex` is available. It does not write to
the repository output PDFs or trusted `tex_files/` artifacts during compile
smoke checks.

## Grade scale

| Grade | Meaning | Threshold |
| --- | --- | --- |
| A | prod ready | 95-100 |
| B | getting there | 80-94.99 |
| C | needs major fixes | 65-79.99 |
| D | ngmi | 50-64.99 |
| F | dog shit | below 50 |

An A requires more than "the current happy path works." It means the supported
document modes are deterministic, tested, safe under cache reuse, and covered by
tooling/runtime smoke at a level comparable to mature TUI/document tools. The
current resume pipeline can score high, but the benchmark should remain honest:
the deterministic cover-letter renderer is not implemented yet, and TUI runtime
coverage depends on whether Textual is installed in the local environment.

## Scored areas

### Tests - 20 points

- Full `unittest discover -s tests -v` pass and minimum test count.
- Focused tests exist for renderer determinism, artifact cache behavior,
  compiler backend safety, planner validation/cache, and CLI/TUI migration.

### Determinism and cache - 25 points

- Stable fields and formatting: the same `CanonicalProfile`, `TemplateSpec`,
  and `SelectionPlan` render identical TeX bytes.
- Render from scratch: Gemini does not write final TeX. Gemini only emits
  structured `SelectionPlan` JSON.
- Stable artifact key: rationale text does not affect artifact identity, while
  order-sensitive fields do.
- Identical profile/template/plan combinations copy cached PDFs instead of
  recompiling.
- Every advertised document mode has a deterministic renderer.

### Safety and atomicity - 25 points

- Artifact writes use temp files, `fsync`, and atomic replace.
- Compiler execution is isolated in temp build directories with explicit argv
  and `shell=False`.
- No raw imported TeX or Gemini-authored TeX reaches executable compile paths.
- Planner output containing document commands or incomplete plan shapes is
  rejected before normalization.
- PDF cache/export validates `%PDF-` bytes before publishing and preserves prior
  exports on invalid cached bytes.

### Compile status - 15 points

- `src/compile.py --tex-only` exports deterministic TeX without constructing a
  compiler backend.
- `CompilerBackend` can publish a valid PDF through the artifact store using an
  injected fake engine.
- Custom `--output` paths default PDF output next to the requested TeX path,
  rather than clobbering canonical PDFs.
- Optional, unscored: real TeX engine smoke in a temp directory when
  `latexmk`/`pdflatex` is available.

### TUI and tooling - 15 points

This is the comparison against mature TUI/document tools: long-running commands
must be routed off the UI path, unsafe inputs must be visibly separated from
trusted artifacts, unsupported paths must fail closed, and runtime import smoke
should pass when dependencies are installed.

- Generate/compile commands are routed through Textual workers.
- Raw TeX imports are stored under `raw_inputs/` as `.raw.txt`, not trusted
  `.tex` artifacts.
- The Compile tab rebuilds the deterministic JSON resume instead of compiling
  arbitrary selected `.tex` files.
- Cover-letter generation fails closed until the deterministic renderer exists.
- README and this benchmark doc describe the safe Gemini/TeX boundary.

## Current interpretation

The target architecture is:

1. Gemini takes the raw input, canonical profile, and template spec.
2. Gemini returns only a structured JSON `SelectionPlan`.
3. Local validation normalizes or rejects that plan.
4. The local renderer builds TeX from scratch from `RenderModel` and
   `TemplateSpec`.
5. `ArtifactStore` writes/cache-exports artifacts atomically.
6. `CompilerBackend` compiles trusted rendered TeX in an isolated temp dir.
7. Matching artifact keys reuse cached PDFs by copy instead of recompilation.

That architecture is strong for deterministic resume generation. The remaining
gap for a true A is breadth: deterministic cover-letter rendering and stronger
runtime TUI coverage should land before calling the whole tool production ready.
