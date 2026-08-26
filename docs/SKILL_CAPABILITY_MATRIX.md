# Skill Capability Matrix

| Capability | Classification | Offline/native behavior | Optional Runtime or dependency | Built-in boundary |
| --- | --- | --- | --- | --- |
| QwenPaw PDF | `QWENPAW BUILTIN` | Read, OCR, merge, split, rotate, encrypt | QwenPaw Runtime | Custom pack does not duplicate it |
| QwenPaw DOCX/XLSX/PPTX | `QWENPAW BUILTIN` | Office editing and rendering | QwenPaw Runtime | Batch processor delegates format work |
| Browser/research access | `QWENPAW BUILTIN` | Page access and retrieval | Browser Runtime | Research Skill only evaluates/synthesizes supplied sources |
| `image-toolkit` | `CUSTOM SKILL` | Info, EXIF, hash, conversion, resize, crop, rotate, flip, compression, DPI, EXIF removal, alpha, concat, split, image-to-PDF, duplicate detection and batch conversion/compression | Pillow required; OpenCV/ImageMagick optional | No AI for simple operations |
| `photo-restoration` | `CUSTOM SKILL` | Inspect, denoise, unsharp/deblur fallback, autocontrast, brightness/color recovery and before/after comparison, batch pipeline | OpenCV optional; Real-ESRGAN, GFPGAN, CodeFormer, LaMa and colorization are `OPTIONAL RUNTIME` | Missing AI yields partial/model-required, never fake restoration |
| `advanced-ocr` | `CUSTOM SKILL` | Image OCR orchestration, confidence, bbox, reading order and JSON/Markdown/TXT/CSV/XLSX output | Tesseract optional; PaddleOCR/layout/table is `OPTIONAL RUNTIME` | PDF OCR delegates to built-in PDF |
| `media-transcriber` | `CUSTOM SKILL` | ffprobe inspection, ffmpeg audio extraction, transcript Markdown/TXT/SRT/VTT, heuristic summary/action/decision/keyword extraction | ffmpeg optional; Whisper/FunASR is `OPTIONAL RUNTIME`; diarization uses supplied/runtime speaker labels | No model download |
| `image-background-tools` | `CUSTOM SKILL` | Solid-background transparency, solid-color replacement, blur, subject crop and batch | OpenCV optional; rembg/segmentation is `OPTIONAL RUNTIME` | Alpha matting is not claimed without Runtime |
| `image-quality-enhancer` | `CUSTOM SKILL` | 2x/4x LANCZOS, median denoise, sharpening, JPEG artifact reduction fallback, gamma, contrast and white balance, batch | OpenCV optional; Real-ESRGAN is `OPTIONAL RUNTIME` | Native upscale is identified as traditional, not AI |
| `sql-diagnostics` | `CUSTOM SKILL` | Read-only syntax/logic/risk checks, Oracle error knowledge, JDBC wrapper analysis and execution-plan signals | sqlparse optional | Never executes SQL by default |
| `log-incident-analyzer` | `CUSTOM SKILL` | Chronological detection, earliest error, last normal, clustering, stack continuation, secondary errors and cross-stack classification | None | Evidence precedes root-cause claim |
| `api-debugger` | `CUSTOM SKILL` | DNS/TCP/TLS/proxy/connect/read/4xx/5xx classification and curl/requests/HttpClient/WebClient/RestTemplate generation | curl optional for user-run verification | No outbound request by default |
| `ops-troubleshooter` | `CUSTOM SKILL` | Focused observation, hypothesis, up to three verification checks and conclusion gate | docker, kubectl, nvidia-smi optional | Does not dump unrelated commands |
| `network-diagnostics` | `CUSTOM SKILL` | Windows/Linux IPv4/IPv6, DNS, TCP/UDP-basic, route, TLS, HTTP and proxy verification plans | OS network CLIs optional | Generated plan is not an executed probe |
| `config-diagnostics` | `CUSTOM SKILL` | JSON duplicate keys, XML, INI, env/properties, references, ports and secret-redacted security findings | PyYAML optional for YAML, Compose and Kubernetes YAML | Never returns Secret values |
| `archive-inspector` | `CUSTOM SKILL` | ZIP/tar tree, sizes, checksums, duplicate content, hidden/nested files, comparison and safe extraction | 7z CLI optional | Zip Slip/path traversal blocks extraction |
| `data-profiler` | `CUSTOM SKILL` | CSV/TSV/JSONL and XLSX shape/schema/null/duplicate/constant/unique/statistics/percentiles/outliers/categories/correlation/timestamp gaps/imbalance/leakage suspicion; Markdown/JSON and optional XLSX report | openpyxl optional for XLSX report/input; PyArrow optional for Parquet | Not an XLSX editor |
| `document-batch-processor` | `CUSTOM SKILL` | Inventory, metadata, classification, hashes, duplicates, copy/move plan, safe apply and JSON index | Built-in Office/PDF Skills for content operations | Does not implement Office editors |
| `release-notes` | `CUSTOM SKILL` | Conventional Commit grouping, changelog, breaking/migration/database/config/deployment/risk/rollback/test sections | Git optional when repository/range input is used | Read-only Git inspection |
| `web-research-report` | `CUSTOM SKILL` | Source authority/freshness scoring, claim cross-validation, conflict tracking, fact/inference separation and citations | Built-in Browser supplies sources | Does not duplicate Browser |
| Advanced PDF Editor | `CUSTOM SKILL` | Precise image/text replacement, bbox/transform preservation, validated insertion, Chinese page numbers, layout and visual validation | Existing PyMuPDF/Pillow dependencies | Ordinary PDF work stays built-in |
| Hermes | `ARCHIVED` | Source retained for design reference only | None | No production Runtime, Gateway or Plugin |
