# AgentScope PDF Editor V1.2.0 Validation Record

## 1. Record status

This document records the confirmed production-style acceptance result for the
PDF Editor Skill package in a real AgentScope/QwenPaw Workspace. The validation
result was supplied by the deployment operator and is recorded without
changing the PDF Engine or Runtime.

| Item | Value |
| --- | --- |
| Record date | 2026-08-25 |
| Actual validation date | Not provided; pending operator record |
| Validation mode | Real AgentScope Skill Center upload and Agent invocation |
| Result | PASS, with documented `page_numbers` fallback |
| Evidence level | Operator-confirmed execution result; Workspace identifiers, logs, screenshots, and Artifact hashes were not supplied to this repository |

This record updates the status of PDF Editor V1.2.0 only. It does not imply
that every Extension package, Plugin, Adapter, or future AgentScope/QwenPaw
version has completed real Runtime validation.

## 2. Environment

| Field | Recorded value |
| --- | --- |
| Deployment platform | AgentScope Skill Center / QwenPaw Workspace |
| AgentScope version | Not provided; must be added from the validated environment |
| QwenPaw version | Not provided; must be added from the validated environment |
| Workspace name | Not provided; must be added using a non-sensitive identifier |
| Workspace ID | Not provided; may remain masked if it is tenant-sensitive |
| Skill name | `pdf-editor` |
| Skill display name | PDF Editor |
| Skill version | `1.2.0` |
| Release package | `pdf-editor-v1.2.0.skill.zip` |
| Manifest type | `skill` |
| Executor | Existing PDF Editor Contract executor |

Version and Workspace fields are intentionally marked as not provided. Package
upload success cannot be used to infer the exact Runtime version or Workspace
identity.

## 3. Deployment flow

The validated path was:

```text
Local repository
        |
        v
pdf-editor-v1.2.0.skill.zip
        |
        v
AgentScope Skill upload
        |
        v
Skill activation
        |
        v
Agent invocation
        |
        v
PDF operation result + Artifact
```

Recorded deployment steps:

1. Build or select the immutable `pdf-editor-v1.2.0.skill.zip` release package.
2. Upload the package through AgentScope Skill Center.
3. AgentScope accepts and loads the package Manifest.
4. Activate the uploaded Skill in the target Workspace.
5. Invoke PDF Editor through an Agent.
6. Validate the requested PDF operation and returned Artifact.

No direct Runtime directory replacement or AgentScope/QwenPaw core change was
part of this validation.

## 4. Test cases

### Case 1: Delete PDF page

| Field | Result |
| --- | --- |
| Operation | Delete a selected PDF page |
| Execution | Existing PDF Editor executor invoked successfully |
| Result | **PASS** |

The requested page deletion completed successfully in the AgentScope-hosted
Skill execution path.

### Case 2: Rotate page

| Field | Result |
| --- | --- |
| Operation | Rotate a selected PDF page |
| Execution | Existing PDF Editor executor invoked successfully |
| Result | **PASS** |

The requested page rotation completed successfully.

### Case 3: Add page numbers

| Field | Result |
| --- | --- |
| Primary operation | `page_numbers` |
| Primary result | Encountered a font glyph limitation |
| Fallback | `add_text` |
| Fallback result | Completed successfully |
| Overall result | **PASS WITH FALLBACK** |

The dedicated `page_numbers` path encountered a glyph limitation in the target
font environment. The operation was completed using the existing `add_text`
fallback. This confirms that page-number output can be delivered through the
fallback, but it does not remove the underlying glyph limitation from the
dedicated operation.

Follow-up acceptance should retain a Chinese/non-ASCII font case and record the
actual font family used by the AgentScope execution environment. No PDF Engine
change is made as part of this validation record.

### Case 4: Artifact return

| Field | Result |
| --- | --- |
| Output type | PDF Artifact |
| AgentScope return path | Skill result returned an Artifact successfully |
| Result | **PASS** |

The Agent received a usable Artifact result from the uploaded Skill execution.
The Artifact identifier, SHA256, size, and download-retention evidence were not
provided and remain optional evidence fields for the next validation run.

## 5. Acceptance conclusion

The real Workspace validation confirms the following for PDF Editor V1.2.0:

- **PASS — Skill package format compatibility:** AgentScope Skill Center
  accepted `pdf-editor-v1.2.0.skill.zip`.
- **PASS — Manifest loading:** the uploaded Skill Manifest loaded successfully.
- **PASS — Executor invocation:** Agent invocation reached and executed the
  existing PDF Editor executor.
- **PASS — PDF operations:** delete-page and rotate-page cases completed.
- **PASS WITH FALLBACK — Page numbers:** `page_numbers` encountered a font glyph
  limitation; `add_text` completed the requested output.
- **PASS — Artifact return:** the Skill returned the generated PDF Artifact to
  the Agent path successfully.

Overall acceptance status: **PDF Editor V1.2.0 is validated for AgentScope Skill
Center upload, activation, Agent execution, and Artifact return in the tested
Workspace, with the documented page-number glyph limitation.**

## 6. Relationship to offline deployment validation

`AGENTSCOPE_RUNTIME_VALIDATION.md` deliberately records Runtime Discovery as
`NOT_EXECUTED` for the generic offline deployment bridge. This real validation
adds evidence for one specific deployment tuple:

```text
Extension: pdf-editor
Version:   1.2.0
Type:      skill
Runtime:   exact version pending record
Workspace: exact identifier pending record
```

The generic offline report must not be changed to claim universal Runtime
discovery. The real result belongs in this scoped validation record until the
missing environment identifiers and version compatibility matrix are captured.

## 7. Known limitation and follow-up evidence

Known limitation:

- `page_numbers` may fail when the target font lacks required glyphs.
- `add_text` is the validated fallback for this acceptance run.
- OCR redraw remains outside PDF Editor V1.2.0 scope.

Recommended evidence to add after the next controlled validation, without
including secrets or customer documents:

- AgentScope and QwenPaw exact versions or image digest;
- masked Workspace identifier and region;
- package SHA256;
- sanitized input and output PDF hashes;
- operation request IDs and Artifact metadata;
- screenshots or logs with user data removed;
- font family and glyph coverage used by `page_numbers` and `add_text`;
- activation and rollback receipts, if the platform exposes them.

## 8. Change boundary

This validation record does not modify:

- PDF Editor Engine or executor behavior;
- AgentScope Runtime or QwenPaw Runtime;
- Agent configuration or logic;
- Gateway, Message Model, Streaming core, Plugin, or Adapter code.

Only documentation is added by this change.
