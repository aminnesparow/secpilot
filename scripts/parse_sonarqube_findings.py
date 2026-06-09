#!/usr/bin/env python3
"""
Parser SonarQube -> JSON pivot SecPilot.

Wrapper de compatibilité — la logique réelle vit dans sast_adapter.py.
Conservé pour symétrie avec parse_semgrep_findings.py.

Usage:
    python parse_sonarqube_findings.py issues.json [output.json]

Le fichier d'entrée doit être un export de l'API SonarQube
GET /api/issues/search au format JSON.
"""

import json
import sys
from pathlib import Path

from sast_adapter import convert


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_sonarqube_findings.py <issues.json> [output.json]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2] if len(sys.argv) > 2 else "sonarqube-findings.json")

    pivot = convert("sonarqube", input_path)
    output_path.write_text(json.dumps(pivot, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"SonarQube : {pivot['total_findings']} finding(s) détecté(s)")
    for sev, count in sorted(pivot["summary"]["by_severity"].items()):
        if count:
            print(f"  {sev} : {count}")
    print(f"Résultats écrits dans : {output_path}")


if __name__ == "__main__":
    main()
