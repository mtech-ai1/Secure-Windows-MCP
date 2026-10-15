"""Guard: this fork ships with no telemetry of any kind.

Fails if a PostHog (or similar) client, telemetry env switch, or analytics
module is reintroduced, e.g. by merging an upstream change.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"posthog|telemetry|with_analytics|get_analytics|uuid_extensions", re.IGNORECASE)


def test_source_has_no_telemetry_references():
    hits = [
        f"{path.relative_to(ROOT)}:{n}"
        for path in (ROOT / "src").rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORBIDDEN.search(line)
    ]
    assert hits == []


def test_no_telemetry_dependencies():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert not re.search(r'"(posthog|uuid7)[<>=~! ]', pyproject)


def test_analytics_module_removed():
    assert not (ROOT / "src" / "windows_mcp" / "infrastructure" / "analytics.py").exists()
