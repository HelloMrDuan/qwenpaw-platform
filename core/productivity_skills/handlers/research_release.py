"""Release-note generation and evidence-driven research orchestration."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from ..artifacts import write_report
from ..models import SkillStatus, invalid, result


CONVENTIONAL = re.compile(r"^(?P<type>feat|fix|perf|refactor|docs|test|build|ci|chore|revert)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<message>.+)$", re.I)


def _git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout


def _release_notes(request: dict[str, Any]) -> dict[str, Any]:
    log_text = str(request.get("git_log") or "")
    diff_text = str(request.get("git_diff") or "")
    changed_files = [str(item) for item in request.get("changed_files", [])]
    repo_value = request.get("repository")
    if not log_text and repo_value:
        repo = Path(str(repo_value))
        if not (repo / ".git").exists(): return invalid("repository must be a Git worktree")
        base = str(request.get("base") or "HEAD~20")
        target = str(request.get("target") or "HEAD")
        try:
            log_text = _git(repo, ["log", "--format=%s", f"{base}..{target}"])
            diff_text = _git(repo, ["diff", "--stat", base, target])
            changed_files = _git(repo, ["diff", "--name-only", base, target]).splitlines()
        except Exception as exc:
            return result(SkillStatus.INVALID_INPUT, "Git range cannot be read", error_code=type(exc).__name__, error_detail=str(exc))
    commits = [line.strip() for line in log_text.splitlines() if line.strip()]
    if not commits and not changed_files and not diff_text:
        return invalid("git_log, git_diff, changed_files or repository is required")
    groups = defaultdict(list); breaking = []
    for commit in commits:
        match = CONVENTIONAL.match(commit)
        if match:
            kind = match.group("type").lower(); groups[kind].append(match.group("message"))
            if match.group("breaking"): breaking.append(commit)
        else: groups["other"].append(commit)
        if "BREAKING CHANGE" in commit.upper(): breaking.append(commit)
    database = [name for name in changed_files if re.search(r"(?:migration|schema|\.sql$|liquibase|flyway)", name, re.I)]
    configs = [name for name in changed_files if re.search(r"(?:config|\.ya?ml$|\.properties$|\.env|docker-compose|helm)", name, re.I)]
    tests = [name for name in changed_files if re.search(r"(?:^|/)(?:test|tests)/|test_.*\.py$|.*\.spec\.", name, re.I)]
    risks = []
    if breaking: risks.append("Breaking changes require consumer migration")
    if database: risks.append("Database changes require ordered migration and backup")
    if configs: risks.append("Configuration changes require environment comparison")
    if not tests: risks.append("No changed test file was detected; verify test evidence separately")
    lines = ["# Release Notes", "", "## Features"]
    lines += [f"- {item}" for item in groups.get("feat", [])] or ["- None"]
    lines += ["", "## Bug Fixes"]
    lines += [f"- {item}" for item in groups.get("fix", [])] or ["- None"]
    lines += ["", "## Breaking Changes"]
    lines += [f"- {item}" for item in breaking] or ["- None"]
    lines += ["", "## Migration Notes"]
    lines += [f"- Review {item}" for item in database + configs] or ["- No migration file detected"]
    lines += ["", "## Database Changes"]
    lines += [f"- {item}" for item in database] or ["- None"]
    lines += ["", "## Config Changes"]
    lines += [f"- {item}" for item in configs] or ["- None"]
    lines += ["", "## Deployment Notes", "- Apply database migrations before application rollout when present", "- Compare environment configuration before restart", "", "## Risk"]
    lines += [f"- {item}" for item in risks] or ["- Normal release risk"]
    lines += ["", "## Rollback Plan", "- Disable the release entry point", "- Restore the previous immutable artifact", "- Do not reverse data migrations without a reviewed down plan", "", "## Test Summary", f"- Changed test files: {len(tests)}", f"- Test execution evidence supplied: {'yes' if request.get('test_summary') else 'no'}", ""]
    _path, item = write_report(request, "\n".join(lines), operation="release-notes", suffix="release-notes")
    data = {"commits": len(commits), "groups": dict(groups), "breaking_changes": breaking, "database_changes": database, "config_changes": configs, "test_files": tests, "risks": risks, "diff_summary": diff_text[-5000:]}
    return result(SkillStatus.SUCCESS, "Release notes generated from supplied Git evidence", data=data, artifacts=[item])


def _parse_date(value: Any):
    if not value: return None
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return None


def _research(request: dict[str, Any]) -> dict[str, Any]:
    sources = request.get("sources")
    if not isinstance(sources, list) or not sources:
        return invalid("sources must contain browser-collected source records")
    normalized = []
    claim_sources = defaultdict(list)
    now = datetime.now(timezone.utc)
    for index, source in enumerate(sources, 1):
        if not isinstance(source, dict): continue
        title = str(source.get("title") or f"Source {index}")
        url = str(source.get("url") or "")
        authority = str(source.get("authority") or "unknown").lower()
        published = _parse_date(source.get("published"))
        age_days = (now - published.astimezone(timezone.utc)).days if published and published.tzinfo else None
        quality = 3 if authority in {"primary", "official", "government", "research"} else 2 if authority in {"reputable", "secondary"} else 1
        freshness = 3 if age_days is not None and age_days <= 30 else 2 if age_days is not None and age_days <= 365 else 1 if age_days is not None else 0
        claims = [str(item).strip() for item in source.get("claims", []) if str(item).strip()]
        for claim in claims: claim_sources[claim.lower()].append(index)
        normalized.append({"index": index, "title": title, "url": url, "authority": authority, "published": source.get("published"), "age_days": age_days, "quality_score": quality, "freshness_score": freshness, "claims": claims, "viewpoint": source.get("viewpoint")})
    corroborated = [{"claim": claim, "source_indexes": indexes} for claim, indexes in claim_sources.items() if len(indexes) >= 2]
    conflicts = request.get("conflicts") or []
    facts = request.get("facts") or [item["claim"] for item in corroborated]
    inferences = request.get("inferences") or []
    lines = ["# Web Research Report", "", "## Research Question", "", str(request.get("question") or "Not supplied"), "", "## Verified Facts", ""]
    lines += [f"- {fact}" for fact in facts] or ["- No cross-verified fact yet"]
    lines += ["", "## Inferences", ""] + ([f"- {item} *(inference)*" for item in inferences] or ["- None"])
    lines += ["", "## Conflicting Evidence", ""] + ([f"- {item}" for item in conflicts] or ["- None recorded"])
    lines += ["", "## Source Quality", ""]
    for source in normalized:
        link = f"[{source['title']}]({source['url']})" if source["url"] else source["title"]
        lines.append(f"- {source['index']}. {link} — authority={source['authority']}, quality={source['quality_score']}, freshness={source['freshness_score']}")
    lines += ["", "## Research Summary", "", str(request.get("summary") or "The evidence set has been structured; conclusions should remain bounded by the cited sources."), "", "## Sources", ""]
    lines += [f"{item['index']}. [{item['title']}]({item['url']})" if item["url"] else f"{item['index']}. {item['title']}" for item in normalized]
    _path, item = write_report(request, "\n".join(lines) + "\n", operation="web-research-report", suffix="research")
    status = SkillStatus.SUCCESS if corroborated or facts else SkillStatus.PARTIAL_SUCCESS
    return result(status, "Research evidence normalized and cross-validation reported", data={"sources": normalized, "corroborated_claims": corroborated, "conflicts": conflicts, "facts": facts, "inferences": inferences, "browser_access_performed": False}, artifacts=[item])


def execute(skill_name: str, request: dict[str, Any]) -> dict[str, Any]:
    if skill_name == "release-notes": return _release_notes(request)
    if skill_name == "web-research-report": return _research(request)
    return invalid(f"Unsupported research/release Skill: {skill_name}")
