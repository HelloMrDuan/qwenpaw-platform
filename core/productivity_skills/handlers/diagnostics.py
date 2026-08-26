"""SQL, log, API, operations, network and configuration diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
import configparser
import json
from pathlib import Path
import re
import shlex
from typing import Any, Iterable
import xml.etree.ElementTree as ET

from ..artifacts import write_report
from ..capabilities import CapabilityResolver
from ..models import SkillStatus, invalid, result


SECRET_KEY = re.compile(r"(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|authorization)", re.I)
TIMESTAMP = re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2}[T ][0-9:.+Z-]+)")


def _redact(value: str) -> str:
    value = re.sub(r"(?i)(authorization\s*:\s*)([^\s]+(?:\s+[^\s]+)?)", r"\1<redacted>", value)
    value = re.sub(r"(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)([^\s,;]+)", r"\1<redacted>", value)
    return value


def _report(request: dict[str, Any], title: str, sections: Iterable[tuple[str, Any]], operation: str):
    lines = [f"# {title}", ""]
    for heading, content in sections:
        lines.extend([f"## {heading}", ""])
        if isinstance(content, list):
            lines.extend([f"- {_redact(str(item))}" for item in content] or ["- None"])
        else:
            lines.append(_redact(str(content)) or "None")
        lines.append("")
    _path, item = write_report(request, "\n".join(lines), operation=operation)
    return item


ORA_KNOWLEDGE = {
    "ORA-00001": ("Unique constraint violation", "Find the conflicting key and correct the upsert/sequence strategy."),
    "ORA-00933": ("SQL command not properly ended", "Remove dialect-incompatible clauses or misplaced separators."),
    "ORA-00904": ("Invalid identifier", "Verify aliases, quoted case and column existence."),
    "ORA-01400": ("Cannot insert NULL", "Provide the required value or change the nullable contract after review."),
    "ORA-01722": ("Invalid number conversion", "Validate source strings and use guarded explicit conversion."),
    "ORA-02012": ("Missing remote database context", "Inspect the database-link call chain and remote error that follows."),
    "ORA-02261": ("Unique/primary key already exists", "Remove the duplicate constraint declaration."),
    "ORA-12899": ("Value too large for column", "Measure encoded length and correct input/schema sizing."),
    "ORA-01427": ("Single-row subquery returned multiple rows", "Fix cardinality with a key predicate; do not hide it with arbitrary MIN/MAX."),
    "ORA-06502": ("PL/SQL value or conversion error", "Check variable size, numeric conversion and call parameter types."),
    "ORA-00979": ("Not a GROUP BY expression", "Group every non-aggregated selected expression or aggregate it deliberately."),
}


def _format_sql(sql: str) -> str:
    keywords = ("select", "from", "where", "join", "left join", "right join", "inner join", "group by", "order by", "having", "union", "values", "set", "returning")
    output = re.sub(r"\s+", " ", sql.strip())
    for keyword in sorted(keywords, key=len, reverse=True):
        output = re.sub(rf"\s+({re.escape(keyword)})\s+", lambda match: "\n" + match.group(1).upper() + " ", output, flags=re.I)
    return output.strip()


def _sql(request: dict[str, Any]) -> dict[str, Any]:
    sql = str(request.get("sql") or "").strip()
    if not sql and request.get("input"):
        path = Path(str(request["input"]))
        if path.is_file():
            sql = path.read_text(encoding="utf-8", errors="replace")
    error_text = str(request.get("error") or "")
    execution_plan = str(request.get("execution_plan") or "")
    if not sql and not error_text and not execution_plan:
        return invalid("sql, error or execution_plan is required")
    findings = []
    if sql:
        if sql.count("(") != sql.count(")"):
            findings.append({"location": "parentheses", "root_cause": "Unbalanced parentheses", "impact": "SQL cannot parse", "minimal_fix": "Balance the expression", "risk": "low"})
        aliases = re.findall(r"\b(?:from|join)\s+[\w.$\"]+\s+(?:as\s+)?([A-Za-z_]\w*)", sql, re.I)
        duplicates = [name for name, count in Counter(alias.lower() for alias in aliases).items() if count > 1]
        if duplicates:
            findings.append({"location": "FROM/JOIN", "root_cause": f"Duplicate aliases: {duplicates}", "impact": "Ambiguous column resolution", "minimal_fix": "Use unique aliases", "risk": "medium"})
        if re.search(r"\bdelete\s+from\b", sql, re.I) and not re.search(r"\bwhere\b", sql, re.I):
            findings.append({"location": "DELETE", "root_cause": "DELETE has no WHERE clause", "impact": "All rows may be removed", "minimal_fix": "Add a reviewed predicate or explicitly confirm full-table deletion", "risk": "critical"})
        if re.search(r"\bupdate\b", sql, re.I) and not re.search(r"\bwhere\b", sql, re.I):
            findings.append({"location": "UPDATE", "root_cause": "UPDATE has no WHERE clause", "impact": "All rows may be modified", "minimal_fix": "Add a reviewed predicate", "risk": "critical"})
        if re.search(r"select\s+distinct\b", sql, re.I) and re.search(r"\bjoin\b", sql, re.I):
            findings.append({"location": "DISTINCT", "root_cause": "DISTINCT may be masking JOIN cardinality", "impact": "Extra sort/hash and hidden data defect", "minimal_fix": "Validate join keys before retaining DISTINCT", "risk": "medium"})
        if re.search(r"\bselect\s+\*", sql, re.I):
            findings.append({"location": "SELECT", "root_cause": "Wildcard projection", "impact": "Unstable contract and excess I/O", "minimal_fix": "List required columns", "risk": "low"})
        if re.search(r"\bnot\s+in\s*\(", sql, re.I):
            findings.append({"location": "NOT IN", "root_cause": "NULL-sensitive anti-join", "impact": "Unexpected empty result when subquery contains NULL", "minimal_fix": "Use NOT EXISTS with correlated keys", "risk": "high"})
    matched_error = None
    for code, knowledge in ORA_KNOWLEDGE.items():
        if code in error_text.upper():
            matched_error = {"code": code, "root_cause": knowledge[0], "minimal_fix": knowledge[1]}
            findings.insert(0, {"location": code, "root_cause": knowledge[0], "impact": "Statement or transaction failed", "minimal_fix": knowledge[1], "risk": "high"})
            break
    if re.search(r"(?:SQLGrammarException|DataIntegrityViolationException|ConstraintViolationException|JDBCException)", error_text):
        findings.append({"location": "JDBC/Hibernate wrapper", "root_cause": "Framework exception wraps a database-specific cause", "impact": "Top-level class is insufficient for diagnosis", "minimal_fix": "Use the deepest SQLState/vendor code and bound-parameter types", "risk": "medium"})
    if execution_plan:
        for pattern, cause, fix, risk in (
            (r"TABLE ACCESS FULL|Seq Scan", "Full table scan detected", "Validate selectivity and a matching composite/index access path", "medium"),
            (r"CARTESIAN|Cross Join", "Cartesian join detected", "Add or correct the join predicate", "critical"),
            (r"TEMP TABLE TRANSFORMATION|Using temporary", "Temporary materialization/sort detected", "Reduce intermediate rows and inspect grouping/order indexes", "medium"),
            (r"NESTED LOOPS|Nested Loop", "Nested-loop join is present", "Check outer-row cardinality and inner lookup index before changing join type", "low"),
        ):
            if re.search(pattern, execution_plan, re.I): findings.append({"location": "Execution Plan", "root_cause": cause, "impact": "May dominate latency at current cardinality", "minimal_fix": fix, "risk": risk})
    formatted = _format_sql(sql) if sql else ""
    recommended = formatted
    sections = [
        ("Problem Location", [item["location"] for item in findings]),
        ("Root Cause", [item["root_cause"] for item in findings]),
        ("Impact", [item["impact"] for item in findings]),
        ("Minimal Fix", [item["minimal_fix"] for item in findings]),
        ("Recommended SQL", f"```sql\n{recommended}\n```" if recommended else "No SQL supplied"),
        ("Risk", [item["risk"] for item in findings]),
    ]
    item = _report(request, "SQL Diagnostic Report", sections, "sql-diagnostics")
    return result(SkillStatus.SUCCESS, "SQL analyzed without execution", data={"dialect": request.get("dialect", "auto"), "findings": findings, "formatted_sql": formatted, "matched_error": matched_error, "execution_plan_supplied": bool(execution_plan), "executed": False}, artifacts=[item])


def _read_logs(request: dict[str, Any]) -> list[str]:
    if request.get("logs"):
        value = request["logs"]
        if isinstance(value, list):
            return [str(item) for item in value]
        return str(value).splitlines()
    paths = request.get("inputs") or ([request.get("input")] if request.get("input") else [])
    lines = []
    for value in paths:
        path = Path(str(value))
        if path.is_file():
            lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return lines


def _log(request: dict[str, Any]) -> dict[str, Any]:
    lines = _read_logs(request)
    if not lines:
        return invalid("logs or input file is required")
    events = []
    current = None
    error_pattern = re.compile(r"\b(ERROR|FATAL|Exception|Traceback|ORA-\d+|OOMKilled|CrashLoopBackOff)\b", re.I)
    warning_pattern = re.compile(r"\b(WARN(?:ING)?|retry|timeout)\b", re.I)
    for index, line in enumerate(lines):
        timestamp = (TIMESTAMP.search(line).group("ts") if TIMESTAMP.search(line) else None)
        if error_pattern.search(line):
            signature = re.sub(r"\b\d+\b", "#", line.strip())[:240]
            current = {"line": index + 1, "timestamp": timestamp, "message": _redact(line.strip()), "signature": signature, "level": "ERROR"}
            events.append(current)
        elif warning_pattern.search(line):
            events.append({"line": index + 1, "timestamp": timestamp, "message": _redact(line.strip()), "signature": re.sub(r"\b\d+\b", "#", line.strip())[:240], "level": "WARNING"})
        elif current and (line.startswith((" ", "\t", "at ")) or line.strip().startswith("Caused by:")):
            current["message"] += "\n" + _redact(line.strip())
    errors = [item for item in events if item["level"] == "ERROR"]
    warnings = [item for item in events if item["level"] == "WARNING"]
    clusters = Counter(item["signature"] for item in events)
    root = errors[0] if errors else (warnings[0] if warnings else None)
    last_normal = None
    if root:
        for line in reversed(lines[: root["line"] - 1]):
            if not error_pattern.search(line) and not warning_pattern.search(line) and line.strip():
                last_normal = _redact(line.strip()); break
    types = []
    joined = "\n".join(lines[:5000])
    for label, pattern in {
        "Java/Spring": r"(?:org\.springframework|java\.lang|Hibernate)",
        "Python": r"(?:Traceback|File \".*\.py\")",
        "Node.js": r"(?:node:internal|npm ERR|TypeError:)",
        "Nginx": r"(?:upstream timed out|connect\(\) failed)",
        "Database": r"(?:ORA-\d+|SQLSTATE|MySQL|PostgreSQL)",
        "Kubernetes": r"(?:pod/|CrashLoopBackOff|ImagePullBackOff|OOMKilled)",
        "GPU": r"(?:CUDA|NVRM|nvidia-smi)",
    }.items():
        if re.search(pattern, joined, re.I): types.append(label)
    secondary = errors[1:6]
    sections = [
        ("Incident Summary", root["message"] if root else "No explicit error token detected"),
        ("Timeline", [f"line {item['line']} {item['timestamp'] or ''} {item['message'].splitlines()[0]}" for item in events[:20]]),
        ("Root Cause", root["message"] if root else "Insufficient evidence"),
        ("Secondary Errors", [item["message"].splitlines()[0] for item in secondary]),
        ("Evidence", [f"{count}x {signature}" for signature, count in clusters.most_common(10)]),
        ("Suggested Checks", ["Validate the earliest causal error before later retries", "Correlate request/trace IDs across components", "Confirm dependency health around the failure start"]),
        ("Suggested Fix", "Apply the smallest fix supported by the earliest error and re-run the same request."),
    ]
    item = _report(request, "Incident Analysis", sections, "log-incident-analyzer")
    return result(SkillStatus.SUCCESS, "Logs analyzed chronologically", data={"detected_types": types, "events": len(events), "errors": len(errors), "warnings": len(warnings), "first_exception": root, "last_normal": last_normal, "clusters": clusters.most_common()}, artifacts=[item])


def _api(request: dict[str, Any]) -> dict[str, Any]:
    if not any(request.get(key) is not None for key in ("url", "status", "error", "request", "response", "curl")):
        return invalid("url, status, error, request, response or curl evidence is required")
    status = request.get("status")
    error = str(request.get("error") or "")
    timings = request.get("timings") or {}
    classification = "insufficient_evidence"
    evidence = []
    if re.search(r"(?:name or service not known|NXDOMAIN|getaddrinfo|could not resolve)", error, re.I): classification = "dns_failure"
    elif re.search(r"(?:certificate|SSL|TLS|handshake)", error, re.I): classification = "tls_failure"
    elif re.search(r"(?:proxy|SOCKS|407)", error, re.I): classification = "proxy_failure"
    elif re.search(r"(?:connection refused|connect timeout|failed to connect)", error, re.I): classification = "connect_failure"
    elif re.search(r"(?:read timed out|response timeout|first byte)", error, re.I): classification = "read_timeout"
    elif isinstance(status, int) and status >= 500: classification = "server_5xx"
    elif isinstance(status, int) and status >= 400: classification = "client_4xx"
    elif isinstance(status, int): classification = "http_success" if status < 400 else "http_error"
    if timings:
        if timings.get("connect") is not None: evidence.append(f"connect={timings['connect']}")
        if timings.get("first_byte") is not None: evidence.append(f"first_byte={timings['first_byte']}")
        if timings.get("total") is not None: evidence.append(f"total={timings['total']}")
    method = str(request.get("method") or "GET").upper()
    url = str(request.get("url") or "https://example.invalid")
    headers = {str(k): ("<redacted>" if SECRET_KEY.search(str(k)) else str(v)) for k, v in dict(request.get("headers") or {}).items()}
    body = request.get("body")
    form = {str(k): ("<redacted>" if SECRET_KEY.search(str(k)) else str(v)) for k, v in dict(request.get("form") or {}).items()}
    files = {str(k): str(v) for k, v in dict(request.get("files") or {}).items()}
    curl = ["curl", "-i", "-X", method]
    for key, value in headers.items(): curl += ["-H", f"{key}: {value}"]
    for key, value in form.items(): curl += ["-F", f"{key}={value}"]
    for key, value in files.items(): curl += ["-F", f"{key}=@{value}"]
    if body is not None: curl += ["--data", json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body]
    curl.append(url)
    curl_command = " ".join(shlex.quote(part) for part in curl)
    python_code = f"import requests\nr = requests.request({method!r}, {url!r}, headers={headers!r}, json={body!r}, data={form!r}, files={{name: open(path, 'rb') for name, path in {files!r}.items()}}, timeout=(5, 30))\nprint(r.status_code)\n"
    java_code = f'HttpRequest request = HttpRequest.newBuilder(URI.create("{url}")).method("{method}", HttpRequest.BodyPublishers.noBody()).build();'
    webclient_code = f'webClient.method(HttpMethod.{method}).uri("{url}").retrieve();'
    rest_template_code = f'restTemplate.exchange("{url}", HttpMethod.{method}, HttpEntity.EMPTY, String.class);'
    sections = [("Classification", classification), ("Evidence", evidence or [error or f"HTTP {status}"]), ("Generated curl", f"```bash\n{curl_command}\n```"), ("Python requests", f"```python\n{python_code}```"), ("Java HttpClient", f"```java\n{java_code}\n```"), ("Spring WebClient", f"```java\n{webclient_code}\n```"), ("Spring RestTemplate", f"```java\n{rest_template_code}\n```")]
    item = _report(request, "API Diagnostic Report", sections, "api-debugger")
    return result(SkillStatus.SUCCESS, "API evidence analyzed; no network request executed", data={"classification": classification, "curl": curl_command, "python": python_code, "java_http_client": java_code, "spring_webclient": webclient_code, "spring_rest_template": rest_template_code, "executed": False}, artifacts=[item])


OPS_PLANS = {
    "crashloopbackoff": ["kubectl describe pod <pod>", "kubectl logs <pod> --previous --tail=200", "Verify the first terminated container exit reason"],
    "imagepullbackoff": ["kubectl describe pod <pod>", "Check image name/tag and imagePullSecrets", "Verify registry DNS/TLS from the node"],
    "pending": ["kubectl describe pod <pod>", "Inspect scheduler events", "Compare requests, taints, affinity and available capacity"],
    "oomkilled": ["kubectl describe pod <pod>", "Inspect last termination reason and memory limit", "Correlate working-set growth before changing limits"],
    "port": ["Inspect the owning process for the target port", "Confirm intended bind address", "Check firewall/NAT only after local listen state"],
    "disk": ["Check filesystem capacity and inode usage", "Identify the largest recent growth", "Verify log rotation and deleted-open files"],
    "gpu": ["Run nvidia-smi", "Compare driver-reported CUDA with application Runtime", "Inspect container device exposure"],
}


def _ops(request: dict[str, Any]) -> dict[str, Any]:
    symptom = str(request.get("symptom") or request.get("evidence") or "").strip()
    if not symptom:
        return invalid("symptom or evidence is required")
    key = next((name for name in OPS_PLANS if name in symptom.lower().replace(" ", "")), "port" if "connection refused" in symptom.lower() else None)
    checks = OPS_PLANS.get(key or "", ["Capture the failing component state", "Form one hypothesis from the observed transition", "Run the narrowest command that can falsify it"])
    hypothesis = {
        "oomkilled": "The container exceeded its effective memory limit",
        "crashloopbackoff": "The process exits after startup and Kubernetes restarts it",
        "imagepullbackoff": "The node cannot authenticate to or resolve the image registry",
        "pending": "The scheduler cannot place the pod with current constraints",
    }.get(key, "The supplied symptom needs one focused state check before a root-cause claim")
    sections = [("Observation", symptom), ("Hypothesis", hypothesis), ("Verification Commands", checks), ("Conclusion Gate", "Conclude only after the verification output supports or falsifies the hypothesis.")]
    item = _report(request, "Operations Troubleshooting Plan", sections, "ops-troubleshooter")
    return result(SkillStatus.SUCCESS, "Focused observe-hypothesize-verify plan generated", data={"observation": symptom, "hypothesis": hypothesis, "verification": checks, "executed": False}, artifacts=[item])


def _network(request: dict[str, Any]) -> dict[str, Any]:
    host = str(request.get("host") or "").strip()
    if not host:
        return invalid("host is required")
    os_name = str(request.get("os") or "windows").lower()
    port = int(request.get("port") or (443 if request.get("tls", True) else 80))
    protocol = str(request.get("protocol") or "tcp").lower()
    commands = (
        [f"Resolve-DnsName {host} -Type A", f"Resolve-DnsName {host} -Type AAAA", f"Test-NetConnection {host} -Port {port}", f"tracert {host}", f"curl.exe -v --connect-timeout 5 https://{host}:{port}/"]
        if os_name.startswith("win")
        else [f"dig A {host}", f"dig AAAA {host}", f"nc -vz -w 5 {host} {port}", f"traceroute {host}", f"curl -v --connect-timeout 5 https://{host}:{port}/"]
    )
    if protocol == "udp":
        commands = ([f"Test-NetConnection {host} -Port {port} -InformationLevel Detailed", f"Use an application-level UDP probe for {host}:{port}; ICMP reachability is not UDP service proof"] if os_name.startswith("win") else [f"nc -zvu -w 5 {host} {port}", f"Use an application-level UDP request for {host}:{port}"]) + commands[:2]
    evidence = str(request.get("evidence") or "")
    suspicion = []
    if re.search(r"different|mismatch|pollution", evidence, re.I): suspicion.append("DNS answer inconsistency; compare trusted resolvers before calling it pollution")
    if "ipv6" in evidence.lower(): suspicion.append("IPv6 route or AAAA preference may differ from IPv4")
    if "proxy" in evidence.lower(): suspicion.append("Verify HTTP(S)_PROXY/NO_PROXY and SOCKS routing separately")
    sections = [("Target", f"{host}:{port}"), ("Observation", evidence or "No measurements supplied"), ("Verification Order", commands), ("Interpretation", suspicion or ["DNS -> route -> TCP -> TLS -> HTTP; stop at the first failing layer"])]
    item = _report(request, "Network Diagnostic Plan", sections, "network-diagnostics")
    return result(SkillStatus.SUCCESS, "Cross-platform network verification plan generated", data={"commands": commands, "protocol": protocol, "executed": False, "suspicions": suspicion}, artifacts=[item])


def _duplicate_json_keys(text: str):
    duplicates = []
    def hook(pairs):
        seen = set(); value = {}
        for key, item in pairs:
            if key in seen: duplicates.append(key)
            seen.add(key); value[key] = item
        return value
    return json.loads(text, object_pairs_hook=hook), duplicates


def _walk_config(value: Any, path: str = ""):
    findings = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if SECRET_KEY.search(str(key)):
                findings.append({"type": "sensitive", "path": current, "value": "<redacted>"})
            if isinstance(item, str) and re.search(r"\$\{[^}]+\}", item):
                findings.append({"type": "unresolved_reference", "path": current, "value": "<reference>"})
            findings.extend(_walk_config(item, current))
    elif isinstance(value, list):
        for index, item in enumerate(value): findings.extend(_walk_config(item, f"{path}[{index}]"))
    return findings


def _config(request: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(request.get("input") or ""))
    if not path.is_file():
        return invalid("input must reference an existing configuration file")
    text = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    duplicates = []
    parsed: Any = {}
    capabilities = CapabilityResolver().resolve_many(("yaml",))
    try:
        if suffix == ".json": parsed, duplicates = _duplicate_json_keys(text)
        elif suffix == ".xml": parsed = {"root": ET.fromstring(text).tag}
        elif suffix in {".ini", ".cfg"}:
            parser = configparser.ConfigParser(strict=True); parser.read_string(text); parsed = {section: dict(parser[section]) for section in parser.sections()}
        elif suffix in {".yaml", ".yml"}:
            if not capabilities["yaml"]["available"]:
                return result(SkillStatus.DEPENDENCY_MISSING, "PyYAML is required for YAML diagnostics", error_code="YAML_RUNTIME_MISSING", capabilities=capabilities)
            import yaml
            parsed = yaml.safe_load(text)
        elif suffix in {".env", ".properties"}:
            parsed = {}
            for line_number, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"): continue
                if "=" not in stripped:
                    return invalid(f"line {line_number} has no '=' separator")
                key, value = stripped.split("=", 1)
                if key in parsed: duplicates.append(key)
                parsed[key] = value
        else:
            parsed = {"lines": len(text.splitlines()), "kind": "text-config"}
    except Exception as exc:
        return result(SkillStatus.INVALID_INPUT, "Configuration syntax is invalid", error_code=type(exc).__name__, error_detail=str(exc), capabilities=capabilities)
    findings = _walk_config(parsed)
    findings.extend({"type": "duplicate_key", "path": key, "value": "<redacted>" if SECRET_KEY.search(key) else None} for key in duplicates)
    port_values = re.findall(r"(?im)^\s*(?:port|listen)\s*[:= ]\s*(\d{2,5})", text)
    duplicate_ports = [port for port, count in Counter(port_values).items() if count > 1]
    findings.extend({"type": "port_conflict_candidate", "path": port, "value": None} for port in duplicate_ports)
    sections = [("Syntax", "Valid"), ("Findings", [f"{item['type']}: {item['path']}" for item in findings]), ("Security", "Sensitive values were not copied to this report."), ("Dependency Chain", "Resolve referenced environment variables before dependent services start.")]
    item = _report(request, "Configuration Diagnostic Report", sections, "config-diagnostics")
    return result(SkillStatus.SUCCESS, "Configuration analyzed with sensitive values redacted", data={"format": suffix.lstrip("."), "findings": findings, "duplicate_keys": duplicates}, artifacts=[item], capabilities=capabilities)


def execute(skill_name: str, request: dict[str, Any]) -> dict[str, Any]:
    handlers = {
        "sql-diagnostics": _sql,
        "log-incident-analyzer": _log,
        "api-debugger": _api,
        "ops-troubleshooter": _ops,
        "network-diagnostics": _network,
        "config-diagnostics": _config,
    }
    handler = handlers.get(skill_name)
    return handler(request) if handler else invalid(f"Unsupported diagnostics Skill: {skill_name}")
