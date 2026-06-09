#!/usr/bin/env python3
"""
SAST Adapter — point d'entrée unifié pour le format JSON pivot SecPilot.

Convertit la sortie de n'importe quel SAST supporté (Semgrep, SonarQube,
CodeQL) vers le format pivot défini dans schemas/finding.schema.json.

Usage:
    python sast_adapter.py --source semgrep   --input report.sarif --output findings.json
    python sast_adapter.py --source sonarqube --input issues.json  --output findings.json
    python sast_adapter.py --source codeql    --input report.sarif --output findings.json

Le format de sortie est strictement conforme à schemas/finding.schema.json
et peut être envoyé tel quel à l'API_P SecPilot via POST /analyze.
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SCHEMA_VERSION = "1.0"

SEVERITY_MAP_SARIF = {
    "error": "CRITIQUE",
    "warning": "HAUTE",
    "note": "MOYENNE",
    "none": "INFO",
}

SEVERITY_MAP_SONARQUBE = {
    "BLOCKER": "CRITIQUE",
    "CRITICAL": "CRITIQUE",
    "MAJOR": "HAUTE",
    "MINOR": "MOYENNE",
    "INFO": "INFO",
}

LANGUAGE_FROM_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".cs": "csharp",
    ".php": "php",
}


def detect_language(filepath: str) -> str:
    """Devine le langage depuis l'extension du fichier."""
    for ext, lang in LANGUAGE_FROM_EXTENSION.items():
        if filepath.endswith(ext):
            return lang
    return "other"


def normalize_domain(value: str) -> str:
    """Mappe une valeur libre vers le vocabulaire fermé du schéma."""
    if not value:
        return "general"
    value = value.lower()
    if value in {"banking", "ecommerce", "healthcare"}:
        return value
    return "general"


def parse_semgrep_sarif(sarif: dict) -> List[dict]:
    """Convertit un rapport Semgrep SARIF en liste de findings pivot."""
    findings = []
    for run in sarif.get("runs", []):
        rules_index = {
            rule["id"]: rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
        }
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "unknown")
            rule_info = rules_index.get(rule_id, {})
            properties = rule_info.get("properties", {})

            loc = {}
            if result.get("locations"):
                physical = result["locations"][0].get("physicalLocation", {})
                loc = {
                    "file": physical.get("artifactLocation", {}).get("uri", ""),
                    "line": physical.get("region", {}).get("startLine", 0),
                    "snippet": physical.get("region", {}).get("snippet", {}).get("text", ""),
                }

            findings.append({
                "rule_id": rule_id,
                "severity": SEVERITY_MAP_SARIF.get(result.get("level", "warning"), "MOYENNE"),
                "language": detect_language(loc.get("file", "")),
                "message": result.get("message", {}).get("text", ""),
                "location": loc,
                "metadata": {
                    "business_rule": properties.get("business_rule", ""),
                    "domain": normalize_domain(properties.get("domain", "")),
                    "category": properties.get("category", "security"),
                },
            })
    return findings


def parse_sonarqube_json(report: dict) -> List[dict]:
    """Convertit un rapport SonarQube (export issues API) en findings pivot."""
    findings = []
    for issue in report.get("issues", []):
        loc = {
            "file": issue.get("component", "").split(":")[-1],
            "line": issue.get("line", 0),
        }
        text_range = issue.get("textRange", {})
        if text_range:
            loc["line"] = text_range.get("startLine", loc["line"])
            loc["column"] = text_range.get("startOffset", 0)
            loc["end_line"] = text_range.get("endLine", loc["line"])

        rule = issue.get("rule", "unknown")
        findings.append({
            "rule_id": rule,
            "severity": SEVERITY_MAP_SONARQUBE.get(issue.get("severity", "MAJOR"), "HAUTE"),
            "language": detect_language(loc.get("file", "")),
            "message": issue.get("message", ""),
            "location": loc,
            "metadata": {
                "business_rule": "",
                "domain": "general",
                "category": "vulnerability" if issue.get("type") == "VULNERABILITY" else "classic-bug",
                "cwe": _extract_cwe(issue.get("tags", [])),
            },
        })
    return findings


def parse_codeql_sarif(sarif: dict) -> List[dict]:
    """Convertit un rapport CodeQL SARIF en findings pivot."""
    findings = []
    for run in sarif.get("runs", []):
        rules_index = {
            rule["id"]: rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
        }
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "unknown")
            rule_info = rules_index.get(rule_id, {})
            properties = rule_info.get("properties", {})

            loc = {}
            if result.get("locations"):
                physical = result["locations"][0].get("physicalLocation", {})
                loc = {
                    "file": physical.get("artifactLocation", {}).get("uri", ""),
                    "line": physical.get("region", {}).get("startLine", 0),
                    "end_line": physical.get("region", {}).get("endLine", 0),
                    "snippet": physical.get("region", {}).get("snippet", {}).get("text", ""),
                }

            security_severity = properties.get("security-severity")
            severity = _codeql_severity(result.get("level"), security_severity)

            tags = properties.get("tags", [])
            findings.append({
                "rule_id": rule_id,
                "severity": severity,
                "language": detect_language(loc.get("file", "")),
                "message": result.get("message", {}).get("text", ""),
                "location": loc,
                "metadata": {
                    "business_rule": "",
                    "domain": "general",
                    "category": "security" if "security" in tags else "classic-bug",
                    "cwe": _extract_cwe(tags),
                },
            })
    return findings


def _codeql_severity(level: Optional[str], security_severity: Optional[str]) -> str:
    """Mappe la sévérité CodeQL (CVSS-like) vers le vocabulaire pivot."""
    if security_severity:
        try:
            score = float(security_severity)
            if score >= 9.0:
                return "CRITIQUE"
            if score >= 7.0:
                return "HAUTE"
            if score >= 4.0:
                return "MOYENNE"
            return "BASSE"
        except ValueError:
            pass
    return SEVERITY_MAP_SARIF.get(level or "warning", "MOYENNE")


def _extract_cwe(tags: List[str]) -> str:
    """Extrait le premier identifiant CWE depuis une liste de tags."""
    for tag in tags:
        upper = tag.upper().replace("EXTERNAL/CWE/", "")
        if upper.startswith("CWE-"):
            return upper
    return ""


def build_summary(findings: List[dict]) -> dict:
    """Construit les agrégats consommés par le dispatcher LLM."""
    by_severity: Dict[str, int] = {}
    by_domain: Dict[str, int] = {}
    by_language: Dict[str, int] = {}
    for f in findings:
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1
        domain = f.get("metadata", {}).get("domain", "general")
        by_domain[domain] = by_domain.get(domain, 0) + 1
        lang = f.get("language", "other")
        by_language[lang] = by_language.get(lang, 0) + 1
    return {
        "by_severity": by_severity,
        "by_domain": by_domain,
        "by_language": by_language,
    }


PARSERS = {
    "semgrep": parse_semgrep_sarif,
    "sonarqube": parse_sonarqube_json,
    "codeql": parse_codeql_sarif,
}


def convert(source: str, input_path: Path, target: Optional[dict] = None) -> dict:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    findings = PARSERS[source](raw)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "scan_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": target or {},
        "total_findings": len(findings),
        "summary": build_summary(findings),
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description="Convertit un rapport SAST vers le format pivot SecPilot.")
    parser.add_argument("--source", required=True, choices=sorted(PARSERS.keys()))
    parser.add_argument("--input", required=True, help="Chemin du rapport SAST source.")
    parser.add_argument("--output", required=True, help="Chemin du JSON pivot de sortie.")
    parser.add_argument("--repository", default="", help="Nom du dépôt scanné.")
    parser.add_argument("--branch", default="", help="Branche scannée.")
    parser.add_argument("--commit", default="", help="SHA du commit scanné.")
    args = parser.parse_args()

    target = {}
    if args.repository:
        target["repository"] = args.repository
    if args.branch:
        target["branch"] = args.branch
    if args.commit:
        target["commit"] = args.commit

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Fichier introuvable : {input_path}", file=sys.stderr)
        sys.exit(1)

    pivot = convert(args.source, input_path, target=target or None)
    Path(args.output).write_text(json.dumps(pivot, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] {args.source} : {pivot['total_findings']} finding(s) -> {args.output}")
    for sev, count in sorted(pivot["summary"]["by_severity"].items()):
        print(f"  {sev:<10} : {count}")


if __name__ == "__main__":
    main()
