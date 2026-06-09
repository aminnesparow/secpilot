#!/usr/bin/env python3
"""
Collecteur de métriques opérationnelles SecPilot.

Mesure et persiste les KPI clés du pipeline pour démontrer la valeur produit :
  - Taux de One-Shot success (% de findings corrigés à la 1ère tentative)
  - Temps moyen par fix (MTTR — Mean Time To Remediation)
  - Nombre de tentatives moyennes par finding
  - Ratio de Pull Requests créées vs rejetées

Les métriques sont persistées en JSONL (une ligne par run) pour permettre
l'agrégation dans le temps, et exportées en résumé Markdown pour la
soutenance.

Usage:
    # Enregistrer une nouvelle exécution
    python metrics_collector.py record \\
        --findings 41 --fixed 38 --attempts 1.2 --duration 312.5 \\
        --pr-created 35 --pr-rejected 3

    # Afficher le résumé global
    python metrics_collector.py summary

    # Exporter en Markdown pour le writeup
    python metrics_collector.py export --output metrics.md
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

METRICS_FILE = Path(__file__).parent.parent / "data" / "metrics.jsonl"


def record(args):
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings": args.findings,
        "fixed": args.fixed,
        "avg_attempts": args.attempts,
        "duration_seconds": args.duration,
        "pr_created": args.pr_created,
        "pr_rejected": args.pr_rejected,
        "one_shot_rate": (args.one_shot / args.findings) if args.findings else 0.0,
    }
    with METRICS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[OK] Run enregistré dans {METRICS_FILE}")


def _load_all():
    if not METRICS_FILE.exists():
        return []
    return [json.loads(line) for line in METRICS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _aggregate(entries):
    if not entries:
        return None
    total_findings = sum(e["findings"] for e in entries)
    total_fixed = sum(e["fixed"] for e in entries)
    total_pr_created = sum(e["pr_created"] for e in entries)
    total_pr_rejected = sum(e["pr_rejected"] for e in entries)
    return {
        "runs": len(entries),
        "total_findings": total_findings,
        "total_fixed": total_fixed,
        "fix_rate": (total_fixed / total_findings) if total_findings else 0.0,
        "one_shot_rate_avg": mean(e.get("one_shot_rate", 0.0) for e in entries),
        "avg_attempts": mean(e["avg_attempts"] for e in entries),
        "avg_duration_seconds": mean(e["duration_seconds"] for e in entries),
        "pr_created": total_pr_created,
        "pr_rejected": total_pr_rejected,
        "pr_acceptance_rate": (total_pr_created / (total_pr_created + total_pr_rejected))
            if (total_pr_created + total_pr_rejected) else 0.0,
    }


def summary(args):
    entries = _load_all()
    agg = _aggregate(entries)
    if not agg:
        print("Aucune métrique enregistrée pour le moment.")
        return
    print("=== Résumé des métriques SecPilot ===")
    print(f"  Runs analysés            : {agg['runs']}")
    print(f"  Findings totaux          : {agg['total_findings']}")
    print(f"  Findings corrigés        : {agg['total_fixed']}")
    print(f"  Taux de correction       : {agg['fix_rate']:.1%}")
    print(f"  Taux One-Shot moyen      : {agg['one_shot_rate_avg']:.1%}")
    print(f"  Tentatives moyennes      : {agg['avg_attempts']:.2f}")
    print(f"  Durée moyenne par run    : {agg['avg_duration_seconds']:.1f}s")
    print(f"  PRs créées               : {agg['pr_created']}")
    print(f"  PRs rejetées             : {agg['pr_rejected']}")
    print(f"  Taux d'acceptation PR    : {agg['pr_acceptance_rate']:.1%}")


def export(args):
    entries = _load_all()
    agg = _aggregate(entries)
    if not agg:
        print("Aucune métrique à exporter.", file=sys.stderr)
        sys.exit(1)

    md = []
    md.append("# Métriques opérationnelles SecPilot\n")
    md.append(f"*Agrégation sur {agg['runs']} run(s) — généré le "
              f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n")
    md.append("| KPI | Valeur |")
    md.append("| --- | --- |")
    md.append(f"| Findings analysés (cumulé) | {agg['total_findings']} |")
    md.append(f"| Findings corrigés          | {agg['total_fixed']} |")
    md.append(f"| Taux de correction         | {agg['fix_rate']:.1%} |")
    md.append(f"| Taux de One-Shot success   | {agg['one_shot_rate_avg']:.1%} |")
    md.append(f"| Tentatives moyennes / fix  | {agg['avg_attempts']:.2f} |")
    md.append(f"| Durée moyenne par run      | {agg['avg_duration_seconds']:.1f}s |")
    md.append(f"| Pull Requests créées       | {agg['pr_created']} |")
    md.append(f"| Pull Requests rejetées     | {agg['pr_rejected']} |")
    md.append(f"| Taux d'acceptation des PR  | {agg['pr_acceptance_rate']:.1%} |")

    Path(args.output).write_text("\n".join(md), encoding="utf-8")
    print(f"[OK] Métriques exportées vers {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Collecteur de métriques SecPilot.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="Enregistre une nouvelle exécution.")
    rec.add_argument("--findings", type=int, required=True, help="Nombre de findings analysés.")
    rec.add_argument("--fixed", type=int, required=True, help="Nombre de findings effectivement corrigés.")
    rec.add_argument("--one-shot", type=int, default=0, help="Findings corrigés à la 1ère tentative.")
    rec.add_argument("--attempts", type=float, required=True, help="Tentatives moyennes par finding.")
    rec.add_argument("--duration", type=float, required=True, help="Durée totale du run en secondes.")
    rec.add_argument("--pr-created", type=int, required=True)
    rec.add_argument("--pr-rejected", type=int, default=0)
    rec.set_defaults(func=record)

    summ = sub.add_parser("summary", help="Affiche l'agrégation actuelle.")
    summ.set_defaults(func=summary)

    exp = sub.add_parser("export", help="Exporte l'agrégation en Markdown.")
    exp.add_argument("--output", required=True)
    exp.set_defaults(func=export)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
