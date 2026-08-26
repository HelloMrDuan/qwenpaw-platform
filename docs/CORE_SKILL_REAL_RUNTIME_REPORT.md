# Core Skill Real Runtime Report

## Validation baseline

Phase 16.0 was executed in a real QwenPaw Runtime environment. All 18 Skill
packages were discovered, there were no hard failures, built-in PDF routing and
Advanced PDF Editor routing remained separate, and Artifact delivery succeeded.

## Phase 16.1 quality findings

| Skill | Phase 16.0 observation | Root cause | Phase 16.1 resolution | Status |
| --- | --- | --- | --- | --- |
| `image-quality-enhancer` | A requested 2x upscale reported `SUCCESS` although the observed scale was 1x in traditional mode | Requested scale was not derived consistently from operation aliases and the result status was not checked against measured output dimensions | Resolve 1x/2x/4x from `upscale`, `scale`, or `upscale_2x`/`upscale_4x`; measure actual scale; return `PARTIAL_SUCCESS` or `MODEL_RUNTIME_REQUIRED` when the request is unmet; expose `requested_scale`, `actual_scale`, `mode`, and `missing_capability` | `PARTIAL -> FIXED` |
| `sql-diagnostics` | `analyze` did not detect `A.NAME` missing from `GROUP BY` unless ORA-00979 was also supplied | SQL analysis had error-code knowledge and risk regexes but no SELECT/GROUP BY expression alignment | Add offline static aggregate semantics for GROUP BY, aggregate functions, aliases, DISTINCT/ORDER BY, and basic HAVING validation; produce a minimal recommended query | `PARTIAL -> FIXED` |

## Acceptance examples

### Image quality status semantics

- Requested 2x and measured 1x: never `SUCCESS`; returns `PARTIAL_SUCCESS`,
  preserves the produced Artifact, and identifies `realesrgan` when it is the
  unavailable upgrade path.
- Requested AI 4x without an injected Real-ESRGAN Runtime: returns
  `MODEL_RUNTIME_REQUIRED` with actual scale 1x and no fabricated Artifact.
- Requested 2x/4x and measured output reaches that scale through the documented
  traditional LANCZOS path: `SUCCESS` remains valid and `mode=traditional` is
  explicit.

### SQL static semantics

Input:

```sql
SELECT A.ID, A.NAME, COUNT(*) FROM TEST A GROUP BY A.ID;
```

The `analyze` operation now emits:

```text
non-aggregated column A.NAME is not included in GROUP BY
```

and recommends the minimal alignment `GROUP BY A.ID, A.NAME`. No database is
contacted and no ORA-00979 input is required.

## Boundaries

This phase changes only Extension Skill logic, tests, and documentation. It does
not install optional dependencies, connect to external APIs, add Skills, or
modify QwenPaw Runtime or Advanced PDF Editor.
