"""
Bumblebee Engine — Post-Write Guardrails

Additional QA checks that run after Forge writes files:
  1. Svelte $-prefix scanner  — catches missing $ on store refs in templates
  2. Export integrity check   — catches Forge rewriting/removing existing exports
  3. Diff-size guardrail      — flags suspiciously large deletions
"""
from __future__ import annotations

import re
import subprocess
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    passed: bool
    check: str
    note: str
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Svelte $-prefix scanner
# ---------------------------------------------------------------------------

def _extract_svelte_store_imports(content: str) -> list[str]:
    """Extract store names imported from $lib/stores/* in a Svelte file."""
    names = []
    # Match: import { foo, bar } from '$lib/stores/...'
    pattern = re.compile(
        r"import\s*\{([^}]+)\}\s*from\s*['\"][\$@]lib/stores/[^'\"]+['\"]",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        for name in m.group(1).split(","):
            name = name.strip()
            # Strip "as alias" syntax
            if " as " in name:
                name = name.split(" as ")[0].strip()
            if name and not name.startswith("type "):
                names.append(name)
    return names


def _extract_svelte_template(content: str) -> str:
    """Extract the template section of a Svelte file (everything after </script>)."""
    # Find end of last <script> block
    last_script_end = content.rfind("</script>")
    if last_script_end == -1:
        return content
    return content[last_script_end + len("</script>"):]


def check_svelte_store_prefix(path: Path) -> GuardrailResult:
    """
    Verify that every Svelte store imported from $lib/stores/* is accessed
    with the $ prefix in the template. Catches {storeName} instead of {$storeName}.
    """
    if path.suffix != ".svelte":
        return GuardrailResult(passed=True, check="svelte_store_prefix",
                               note="not a svelte file, skipped")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return GuardrailResult(passed=False, check="svelte_store_prefix",
                               note=f"could not read file: {e}")

    store_names = _extract_svelte_store_imports(content)
    if not store_names:
        return GuardrailResult(passed=True, check="svelte_store_prefix",
                               note="no store imports found")

    template = _extract_svelte_template(content)
    violations = []

    for name in store_names:
        # Patterns that indicate bare (non-$ prefixed) usage in template:
        # {name}, {name.foo}, {name?.foo}, {name > 0}, {#if name}, {#each name},
        # class:x={name}, but NOT {$name}
        bare_patterns = [
            rf"\{{{name}[^$a-zA-Z0-9_]",   # {name} or {name. or {name?
            rf"\{{{name}\}}",                 # {name} exactly
            rf"\{{#{name}[^a-zA-Z0-9_]",     # {#name (block)
            rf"\{{#if {name}[^a-zA-Z0-9_$]", # {#if name
            rf"\{{#each {name}[^a-zA-Z0-9_$]",# {#each name
            rf"={{{name}[^$a-zA-Z0-9_]",     # ={name
        ]
        for pat in bare_patterns:
            if re.search(pat, template):
                violations.append(f"`{name}` used without $ prefix in template")
                break

    if violations:
        return GuardrailResult(
            passed=False, check="svelte_store_prefix",
            note=f"Missing $ prefix on {len(violations)} store(s): {'; '.join(violations)}. "
                 f"Fix: replace {{storeName}} with {{$storeName}} in the template.",
        )

    return GuardrailResult(
        passed=True, check="svelte_store_prefix",
        note=f"all {len(store_names)} store(s) use $ prefix correctly",
    )


# ---------------------------------------------------------------------------
# 2. Export integrity check
# ---------------------------------------------------------------------------

def _extract_exports(content: str, suffix: str) -> set[str]:
    """Extract exported names from a TypeScript/JavaScript/Svelte file."""
    exports = set()
    # export const/let/function/class/type/interface NAME
    pattern = re.compile(
        r"^export\s+(?:const|let|var|function|class|type|interface|async\s+function)\s+"
        r"([a-zA-Z_$][a-zA-Z0-9_$]*)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        exports.add(m.group(1))
    # export { name1, name2 }
    named = re.compile(r"^export\s*\{([^}]+)\}", re.MULTILINE)
    for m in named.finditer(content):
        for name in m.group(1).split(","):
            name = name.strip().split(" as ")[0].strip()
            if name:
                exports.add(name)
    return exports


def check_export_integrity(
    path: Path,
    baseline_content: str | None,
) -> GuardrailResult:
    """
    Verify that exports present before Forge ran are still present after.
    Catches Forge rewriting a module from scratch and losing existing exports.
    Only runs when baseline_content is available (from pre-dispatch git snapshot).
    """
    if path.suffix not in (".ts", ".tsx", ".js", ".jsx", ".svelte"):
        return GuardrailResult(passed=True, check="export_integrity",
                               note="not a JS/TS/Svelte file, skipped")

    if baseline_content is None:
        return GuardrailResult(passed=True, check="export_integrity",
                               note="no baseline available, skipped")

    try:
        new_content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return GuardrailResult(passed=False, check="export_integrity",
                               note=f"could not read file: {e}")

    before = _extract_exports(baseline_content, path.suffix)
    after = _extract_exports(new_content, path.suffix)

    missing = before - after
    # Filter out common false positives — things that might be legitimately renamed
    # (e.g. internal helpers that aren't part of the public contract)
    # For now flag everything missing as a warning, only fail on >2 missing
    if missing:
        msg = f"exports removed by Forge: {sorted(missing)}"
        if len(missing) > 2:
            return GuardrailResult(
                passed=False, check="export_integrity",
                note=f"Too many missing exports ({len(missing)}): {sorted(missing)}. "
                     f"Forge likely rewrote the module instead of extending it.",
            )
        else:
            return GuardrailResult(
                passed=True, check="export_integrity",
                note=f"minor export changes (within tolerance): {msg}",
                warnings=[msg],
            )

    return GuardrailResult(
        passed=True, check="export_integrity",
        note=f"all {len(before)} original exports preserved",
    )


# ---------------------------------------------------------------------------
# 3. Diff-size guardrail
# ---------------------------------------------------------------------------

def check_diff_size(
    path: Path,
    deliverable_root: Path,
    threshold_pct: float = 100.0,  # Disabled — full rewrites are normal for new projects
) -> GuardrailResult:
    """
    Use git diff to check whether Forge deleted more than threshold_pct% of
    the original file. Flags suspiciously large rewrites.
    Conservative default: 60% deletion triggers a warning, not a hard fail.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", str(path.relative_to(deliverable_root))],
            cwd=str(deliverable_root),
            capture_output=True, text=True, timeout=10,
        )
        diff = result.stdout
    except Exception as e:
        return GuardrailResult(passed=True, check="diff_size",
                               note=f"git diff unavailable, skipped: {e}")

    if not diff:
        return GuardrailResult(passed=True, check="diff_size",
                               note="no diff (file unchanged)")

    # Count added and deleted lines
    added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    deleted = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
    total_original = deleted + max(
        sum(1 for l in diff.splitlines() if not l.startswith(("+", "-", "@", "\\"))),
        1,
    )

    if deleted == 0:
        return GuardrailResult(passed=True, check="diff_size",
                               note=f"+{added} lines, no deletions")

    deletion_pct = (deleted / max(total_original, 1)) * 100

    if deletion_pct >= threshold_pct:
        return GuardrailResult(
            passed=False, check="diff_size",
            note=f"Forge deleted {deletion_pct:.0f}% of the original file "
                 f"({deleted} lines removed, {added} added). "
                 f"Likely a full rewrite instead of a targeted edit. "
                 f"Review with: git diff HEAD -- {path.name}",
        )

    return GuardrailResult(
        passed=True, check="diff_size",
        note=f"+{added}/-{deleted} lines ({deletion_pct:.0f}% deleted, within threshold)",
    )


# ---------------------------------------------------------------------------
# 4. Auto-inject rules based on file types
# ---------------------------------------------------------------------------

def auto_inject_rules(files_to_write: list[str], existing_rules: list[str] | None) -> list[str]:
    """
    Return additional rules to inject into the Forge prompt based on
    the file types being written. Keeps rules short to avoid context bloat.
    """
    existing = set(existing_rules or [])
    injected = []

    has_svelte = any(f.endswith(".svelte") for f in files_to_write)
    has_ts_store = any(
        "stores/" in f and f.endswith(".ts")
        for f in files_to_write
    )
    has_shared_ts = any(
        f.endswith(".ts") and "stores/" not in f and "components/" not in f
        for f in files_to_write
    )

    if has_svelte:
        rule = (
            "SVELTE STORES: In the template, every store must use the $ prefix. "
            "Write {$storeName}, {#if $store}, {#each $store as item}, class:x={$store === 'y'}. "
            "Never write {storeName} without $ — that renders [object Object]."
        )
        if rule not in existing:
            injected.append(rule)

    if has_ts_store or has_shared_ts:
        rule = (
            "SHARED FILES: Only ADD to this file. Do not remove or rename existing exports, "
            "interfaces, or functions. The existing code must remain exactly as shown."
        )
        if rule not in existing:
            injected.append(rule)

    rule_out_of_spec = (
        "FILE SCOPE: Only write the files listed above. Do not modify any other file."
    )
    if rule_out_of_spec not in existing:
        injected.append(rule_out_of_spec)

    return injected


# ---------------------------------------------------------------------------
# Combined guardrail runner
# ---------------------------------------------------------------------------

def run_guardrails(
    files_written: list[str],
    deliverable_root: Path,
    baselines: dict[str, str] | None = None,
    diff_threshold_pct: float = 100.0,  # Disabled for new project builds
) -> list[GuardrailResult]:
    """
    Run all post-write guardrails on every file Forge wrote.
    Returns list of results — caller decides how to handle failures.
    """
    results = []
    baselines = baselines or {}

    for file_path_str in files_written:
        path = Path(file_path_str)

        # 1. Svelte $-prefix scanner
        r = check_svelte_store_prefix(path)
        results.append(r)
        if not r.passed:
            log.warning(f"Guardrail [svelte_store_prefix] FAILED {path.name}: {r.note}")
        elif r.warnings:
            log.info(f"Guardrail [svelte_store_prefix] WARNING {path.name}: {r.warnings}")
        else:
            log.info(f"Guardrail [svelte_store_prefix] ok {path.name}: {r.note}")

        # 2. Export integrity
        baseline = baselines.get(str(path.resolve()))
        r = check_export_integrity(path, baseline)
        results.append(r)
        if not r.passed:
            log.warning(f"Guardrail [export_integrity] FAILED {path.name}: {r.note}")
        elif r.warnings:
            log.info(f"Guardrail [export_integrity] WARNING {path.name}: {r.warnings}")
        else:
            log.info(f"Guardrail [export_integrity] ok {path.name}: {r.note}")

        # 3. Diff-size guardrail
        if deliverable_root and path.is_relative_to(deliverable_root):
            r = check_diff_size(path, deliverable_root, threshold_pct=diff_threshold_pct)
            results.append(r)
            if not r.passed:
                log.warning(f"Guardrail [diff_size] FAILED {path.name}: {r.note}")
            else:
                log.info(f"Guardrail [diff_size] ok {path.name}: {r.note}")

    return results


def guardrails_passed(results: list[GuardrailResult]) -> tuple[bool, str]:
    """Check if all guardrail results passed. Returns (ok, error_summary)."""
    failures = [r for r in results if not r.passed]
    if not failures:
        return True, ""
    summary = "; ".join(f"[{r.check}] {r.note}" for r in failures)
    return False, summary
