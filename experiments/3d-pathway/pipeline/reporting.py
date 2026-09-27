"""Human-readable reports without mixing incompatible task metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Any


LABELS = {
    "geometry": "Geometry metrics",
    "rendering": "Rendering metrics",
    "generative": "Generative metrics",
}


def _format_metric(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def module_report(module: dict[str, Any], result: dict[str, Any]) -> str:
    banner = (
        "CONTROLLED FIXTURE — synthetic teaching measurements, not a third-party benchmark reproduction."
        if result["measurement_kind"] == "controlled_fixture"
        else "REUSED MEASURED RESULT — copied from the hash-locked repository benchmark."
    )
    lines = [
        f"# Module {module['id']}: {module['title']}",
        "",
        f"> **{banner}**",
        "",
        f"Profile: `{result['profile']}`. Inference: `{module['inference']}`.",
        "",
    ]
    for family, heading in LABELS.items():
        lines.extend([f"## {heading}", ""])
        metrics = result["metrics"].get(family, {})
        if metrics:
            lines.extend(f"- `{name}`: {_format_metric(value)}" for name, value in sorted(metrics.items()))
        else:
            lines.append("- Not applicable for this module.")
        lines.append("")
    sweep_heading = (
        "Recorded seed outcomes"
        if result["measurement_kind"] == "reused_measured_result"
        else "Controlled failure sweep"
    )
    lines.extend([f"## {sweep_heading}", ""])
    lines.extend(
        f"- {row['parameter']}={row['value']}: {row['metric']}={_format_metric(row['measurement'])}"
        for row in result["failure_sweep"]
    )
    lines.extend(["", "## Interpretation", ""])
    lines.extend(f"- {item}" for item in result.get("observations", []))
    lines.append("")
    return "\n".join(lines)


def aggregate_report(run_id: str, module_results: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    kinds = sorted({result["measurement_kind"] for _, result in module_results})
    lines = [f"# 3D reconstruction pathway: {run_id}", "", f"> Measurement provenance: {', '.join(kinds)}.", ""]
    for family, heading in LABELS.items():
        lines.extend([f"## {heading}", ""])
        found = False
        for module, result in module_results:
            metrics = result["metrics"].get(family, {})
            if not metrics:
                continue
            found = True
            rendered = ", ".join(f"{key}={_format_metric(value)}" for key, value in sorted(metrics.items()))
            lines.append(f"- **{module['id']} {module['title']}**: {rendered}")
        if not found:
            lines.append("- No applicable results in this run.")
        lines.append("")
    lines.extend([
        "Metrics from different task families are intentionally not collapsed into a single ranking.",
        "",
    ])
    return "\n".join(lines)
