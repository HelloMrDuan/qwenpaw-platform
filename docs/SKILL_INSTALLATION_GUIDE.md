# Core Skill Pack Installation Guide

## 1. Build

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\build_skill_pack.py
```

The command builds all 17 new packages plus the retained
`advanced-pdf-editor.skill.zip` under `dist/skills/`. To build one new Skill:

```powershell
.\.venv\Scripts\python.exe scripts\build_skill_pack.py --skill image-toolkit
```

## 2. Package structure

Each new package has this installable root:

```text
SKILL.md
README.md
skill.yaml
scripts/run.py
schemas/
runtime/
```

`runtime/` is a private copy of the small internal execution foundation and the
handler group required by the Skill. It does not import `qwenpaw-platform`, use
`PYTHONPATH`, or contain an absolute repository path.

## 3. Pre-install verification

For every ZIP:

1. verify SHA256 against the build report;
2. open the ZIP and run integrity verification;
3. reject absolute/`..` entries;
4. confirm root `SKILL.md` and `scripts/run.py` exist;
5. scan for `.env`, Secrets, DB/cursor files, logs, caches and model-weight
   suffixes;
6. extract into a clean temporary directory and invoke `scripts/run.py` in
   Python isolated mode;
7. verify a dependency-missing path reports the corresponding structured
   status instead of success.

These checks are automated by `tests/skills/test_core_productivity_skill_pack.py`.

## 4. Install into QwenPaw

Upload one `.skill.zip` through the QwenPaw Skill management surface used by
the tenant, enable it for the target Agent, and run an input/output smoke test.
Install shared native dependencies in the Runtime environment, not inside the
Skill ZIP.

Model-backed features require a separately approved Runtime and separately
managed model files. Installing the Skill does not install or download models.

## 5. Rollback

1. disable the affected Skill version;
2. restore the previous immutable Skill ZIP;
3. do not delete user input or generated Artifacts;
4. re-run the isolated smoke test and one representative operation;
5. record the prior/new ZIP hashes in the deployment report.

Advanced PDF Editor keeps its existing internal ID and v1.2 engine. The release
alias changes its product positioning only; it does not migrate or rewrite PDF
logic.
