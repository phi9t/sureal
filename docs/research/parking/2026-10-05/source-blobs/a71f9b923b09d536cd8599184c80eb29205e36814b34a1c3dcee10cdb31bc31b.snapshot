"""Human-readable reports without mixing incompatible task metrics."""

from __future__ import annotations

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
    controlled_suite = result.get("controlled_suite")
    if controlled_suite is not None:
        renderer = controlled_suite["renderer"]
        views = controlled_suite["views"]
        lines.extend(
            [
                "## Shared Blender controlled suite",
                "",
                f"- Episode: `{controlled_suite['episode_id']}`; manifest SHA-256: "
                f"`{controlled_suite['episode_manifest_sha256']}`.",
                f"- Renderer: Blender {renderer['blender_version']} / Cycles "
                f"{renderer['cycles_version']}, {renderer['samples']} samples on "
                f"{renderer['device']}.",
                f"- Evidence: {views['context']} context views and "
                f"{views['target_per_hypothesis']} targets per hidden-scene hypothesis, "
                "with metric depth/range, normals, IDs, albedo, visibility, and "
                "deterministic active-sensor simulations.",
                "",
            ]
        )
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
    resources = result["resources"]
    lines.extend(
        [
            "",
            "## Runtime measurement contract",
            "",
            f"- `network_isolation={resources['network_isolation']}`",
            f"- `cpu_memory_scope={resources['cpu_memory_scope']}`",
        ]
    )
    lines.append("")
    return "\n".join(lines)


def _numeric_metric_leaves(value: Any, prefix: str = "") -> list[tuple[str, int | float]]:
    leaves: list[tuple[str, int | float]] = []
    if isinstance(value, dict):
        for name, child in sorted(value.items()):
            child_prefix = f"{prefix}.{name}" if prefix else name
            leaves.extend(_numeric_metric_leaves(child, child_prefix))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        leaves.append((prefix, value))
    return leaves


def _reference_contract(record: dict[str, Any]) -> str:
    contract = record.get("model_contract", {})
    preferred = (
        "method",
        "methods",
        "inference",
        "optimization",
        "completion_claim",
        "posterior_sampling_claim",
    )
    values = []
    for name in preferred:
        if name in contract:
            value = contract[name]
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            values.append(f"{name}={value}")
    return "; ".join(values) or "See the hash-locked adapter registry."


def aggregate_report(
    run_id: str,
    module_results: list[tuple[dict[str, Any], dict[str, Any]]],
    reference_results: list[tuple[dict[str, Any], dict[str, Any]]] | None = None,
) -> str:
    reference_results = reference_results or []
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

    lines.extend(["## Controlled-lab resources", ""])
    for module, result in module_results:
        resources = result.get("resources", {})
        lines.append(
            f"- **{module['id']} {module['title']}**: "
            f"runtime_seconds={_format_metric(resources.get('runtime_seconds', 'unavailable'))}, "
            f"peak_cpu_bytes={_format_metric(resources.get('peak_cpu_bytes', 'unavailable'))}, "
            f"peak_gpu_bytes={_format_metric(resources.get('peak_gpu_bytes', 'unavailable'))}, "
            f"network_isolation={_format_metric(resources.get('network_isolation', 'unavailable'))}, "
            f"cpu_memory_scope={_format_metric(resources.get('cpu_memory_scope', 'unavailable'))}"
        )
    lines.append("")

    lines.extend(["## Maintained reference measurements", ""])
    if not reference_results:
        lines.append("- Not executed in this run. Full acceptance requires every landed adapter.")
        lines.append("")
    for record, result in reference_results:
        module_ids = ", ".join(result["module_ids"])
        metrics = _numeric_metric_leaves(result.get("metrics", {}))
        rendered_metrics = ", ".join(
            f"{name}={_format_metric(value)}" for name, value in metrics
        )
        resources = result.get("resources", {})
        rendered_resources = ", ".join(
            f"{name}={_format_metric(resources[name])}"
            for name in (
                "runtime_seconds",
                "peak_cpu_memory_bytes",
                "peak_gpu_compute_memory_bytes",
            )
            if name in resources
        )
        lines.extend(
            [
                f"### Modules {module_ids}: {result['adapter']}",
                "",
                f"- Metrics: {rendered_metrics or 'No scalar metric leaves.'}",
                f"- Resources: {rendered_resources or 'Unavailable.'}",
                f"- Assumptions: {_reference_contract(record)}",
                f"- Failure boundary: {record.get('measurement_note', 'See the adapter evaluation contract.')}",
                "",
            ]
        )

    lines.extend(["## Assumptions and failure boundaries", ""])
    lines.extend(
        [
            "- Metrics from geometry, rendering, and generative tasks are not interchangeable.",
            "- Controlled fixtures teach observability and failure mechanisms; maintained adapters carry measured implementation evidence.",
        ]
    )
    for module, result in module_results:
        for observation in result.get("observations", []):
            lines.append(f"- **{module['id']}**: {observation}")
    lines.append("")
    lines.extend([
        "Metrics from different task families are intentionally not collapsed into a single ranking.",
        "",
    ])
    return "\n".join(lines)
