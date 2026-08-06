"""Sync Colab Google Drive benchmark outputs into a local consolidated folder."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable


DEFAULT_LOCAL_ROOT = Path("data/benchmark/runs/colab-consolidated")
DEFAULT_DRIVE_COMMONS_ROOT = Path("time-series-commons")
REGISTRY_DIR_NAMES = ("registries", "run-registries")
FORECAST_DIR_NAME = "forecast-artifacts"


@dataclass(frozen=True)
class CampaignLayout:
    name: str
    source_root: Path
    registry_dir: Path
    forecast_dir: Path | None


@dataclass
class CopyStats:
    copied: int = 0
    skipped: int = 0
    missing_sources: int = 0


def discover_campaign_layouts(
    drive_commons_root: str | Path,
    *,
    campaign_names: Iterable[str] | None = None,
) -> list[CampaignLayout]:
    """Find Colab campaign folders that contain writable run registries."""

    root = Path(drive_commons_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Drive commons root does not exist: {root}")

    requested = {name.strip() for name in campaign_names} if campaign_names else None
    layouts: list[CampaignLayout] = []

    candidates = [root] if _looks_like_campaign_root(root) else sorted(path for path in root.iterdir() if path.is_dir())
    for candidate in candidates:
        if requested is not None and candidate.name not in requested and candidate != root:
            continue
        registry_dir = _find_child(candidate, REGISTRY_DIR_NAMES)
        if registry_dir is None:
            continue
        forecast_dir = candidate / FORECAST_DIR_NAME
        layouts.append(
            CampaignLayout(
                name=candidate.name if candidate != root else root.name,
                source_root=candidate,
                registry_dir=registry_dir,
                forecast_dir=forecast_dir if forecast_dir.is_dir() else None,
            )
        )

    if not layouts:
        raise FileNotFoundError(
            f"No Colab campaign folders with {' or '.join(REGISTRY_DIR_NAMES)} found under {root}"
        )
    return layouts


def consolidate_drive_results(
    *,
    drive_commons_root: str | Path,
    local_root: str | Path = DEFAULT_LOCAL_ROOT,
    campaign_names: Iterable[str] | None = None,
    include_forecasts: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy Drive run registries (and optional forecast artifacts) into one local tree."""

    local_root = Path(local_root).expanduser().resolve()
    local_root.mkdir(parents=True, exist_ok=True)

    layouts = discover_campaign_layouts(drive_commons_root, campaign_names=campaign_names)
    consolidated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    campaign_summaries: list[dict[str, Any]] = []

    for layout in layouts:
        destination = local_root / layout.name
        registry_destination = destination / layout.registry_dir.name
        registry_stats = _sync_directory(
            layout.registry_dir,
            registry_destination,
            overwrite=overwrite,
        )
        _rewrite_registry_artifact_paths(
            registry_destination,
            local_campaign_root=destination,
        )

        forecast_stats: CopyStats | None = None
        if include_forecasts and layout.forecast_dir is not None:
            forecast_stats = _sync_directory(
                layout.forecast_dir,
                destination / FORECAST_DIR_NAME,
                overwrite=overwrite,
            )

        campaign_summaries.append(
            {
                "campaign": layout.name,
                "source_root": str(layout.source_root),
                "local_root": str(destination),
                "registry_dir": str(registry_destination),
                "registry_files": sorted(path.name for path in registry_destination.glob("*.json")),
                "registry_copy": _copy_stats_dict(registry_stats),
                "forecast_copy": _copy_stats_dict(forecast_stats) if forecast_stats else None,
                "progress": summarize_registry_results(registry_destination),
            }
        )

    manifest = {
        "schema_version": "0.1.0",
        "consolidated_at": consolidated_at,
        "drive_commons_root": str(Path(drive_commons_root).expanduser().resolve()),
        "local_root": str(local_root),
        "campaigns": campaign_summaries,
        "progress": _aggregate_progress(campaign_summaries),
    }
    manifest_path = local_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def summarize_registry_results(registry_dir: str | Path) -> dict[str, Any]:
    statuses: Counter[str] = Counter()
    registry_count = 0
    result_count = 0

    for path in sorted(Path(registry_dir).glob("*.json")):
        if path.name == "manifest.json":
            continue
        registry_count += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        for result in payload.get("results", {}).values():
            result_count += 1
            statuses[str(result.get("status", "unknown"))] += 1

    return {
        "registry_count": registry_count,
        "result_count": result_count,
        "statuses": dict(sorted(statuses.items())),
    }


def resolve_default_drive_commons_root() -> Path | None:
    """Best-effort lookup for a synced Google Drive time-series-commons folder."""

    home = Path.home()
    candidates = [
        home / "Google Drive" / "My Drive" / DEFAULT_DRIVE_COMMONS_ROOT,
        home / "Library" / "CloudStorage",
    ]
    direct = candidates[0]
    if direct.is_dir():
        return direct

    cloud_root = candidates[1]
    if cloud_root.is_dir():
        for drive_root in sorted(cloud_root.glob("GoogleDrive-*")):
            candidate = drive_root / "My Drive" / DEFAULT_DRIVE_COMMONS_ROOT
            if candidate.is_dir():
                return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy Colab benchmark run registries and forecast artifacts from a synced "
            "Google Drive folder into a local consolidated directory."
        )
    )
    parser.add_argument(
        "--drive-commons-root",
        help=(
            "Synced Google Drive folder containing Colab campaign directories "
            "(for example .../My Drive/time-series-commons)."
        ),
    )
    parser.add_argument(
        "--campaign",
        action="append",
        help=(
            "Campaign folder name to include (repeatable). Defaults to every campaign "
            "with registries/ or run-registries/ under the drive commons root."
        ),
    )
    parser.add_argument(
        "--local-root",
        default=str(DEFAULT_LOCAL_ROOT),
        help="Destination root for consolidated benchmark outputs.",
    )
    parser.add_argument(
        "--skip-forecasts",
        action="store_true",
        help="Copy registry JSON only; skip forecast-artifacts/.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace local files even when the Drive source has the same size and mtime.",
    )
    args = parser.parse_args(argv)

    drive_root = args.drive_commons_root
    if drive_root is None:
        discovered = resolve_default_drive_commons_root()
        if discovered is None:
            parser.error(
                "Could not find a synced Google Drive time-series-commons folder. "
                "Pass --drive-commons-root explicitly."
            )
        drive_root = str(discovered)

    manifest = consolidate_drive_results(
        drive_commons_root=drive_root,
        local_root=args.local_root,
        campaign_names=args.campaign,
        include_forecasts=not args.skip_forecasts,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _looks_like_campaign_root(path: Path) -> bool:
    return _find_child(path, REGISTRY_DIR_NAMES) is not None


def _find_child(path: Path, names: Iterable[str]) -> Path | None:
    for name in names:
        candidate = path / name
        if candidate.is_dir():
            return candidate
    return None


def _sync_directory(source: Path, destination: Path, *, overwrite: bool) -> CopyStats:
    stats = CopyStats()
    if not source.exists():
        stats.missing_sources += 1
        return stats

    destination.mkdir(parents=True, exist_ok=True)
    for src_path in sorted(source.rglob("*")):
        if not src_path.is_file():
            continue
        rel_path = src_path.relative_to(source)
        dest_path = destination / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if not overwrite and dest_path.exists() and _same_file(src_path, dest_path):
            stats.skipped += 1
            continue
        shutil.copy2(src_path, dest_path)
        stats.copied += 1
    return stats


def _same_file(source: Path, destination: Path) -> bool:
    source_stat = source.stat()
    dest_stat = destination.stat()
    return source_stat.st_size == dest_stat.st_size and int(source_stat.st_mtime) == int(dest_stat.st_mtime)


def _rewrite_registry_artifact_paths(
    registry_dir: Path,
    *,
    local_campaign_root: Path,
) -> None:
    forecast_root = local_campaign_root / FORECAST_DIR_NAME

    for path in sorted(registry_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload.get("results"), dict):
            continue
        changed = False
        for result in payload["results"].values():
            changed |= _rewrite_result_artifact_paths(
                result,
                local_campaign_root=local_campaign_root,
                forecast_root=forecast_root,
            )
            for attempt in result.get("attempts", []):
                changed |= _rewrite_result_artifact_paths(
                    attempt,
                    local_campaign_root=local_campaign_root,
                    forecast_root=forecast_root,
                )
        if changed:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _rewrite_result_artifact_paths(
    result: dict[str, Any],
    *,
    local_campaign_root: Path,
    forecast_root: Path,
) -> bool:
    artifact = result.get("forecast_artifact")
    if not isinstance(artifact, dict) or "path" not in artifact:
        return False

    original = str(artifact["path"])
    candidate = Path(original)
    if candidate.is_file():
        artifact["path"] = _relative_posix(candidate.resolve(), local_campaign_root.resolve())
        return artifact["path"] != original

    normalized = original.replace("\\", "/")
    marker = f"{FORECAST_DIR_NAME}/"
    if marker in normalized:
        artifact["path"] = normalized[normalized.index(marker) :]
        return artifact["path"] != original

    file_name = Path(normalized).name
    if forecast_root.is_dir():
        matches = sorted(forecast_root.rglob(file_name))
        if len(matches) == 1:
            artifact["path"] = _relative_posix(matches[0].resolve(), local_campaign_root.resolve())
            return artifact["path"] != original
    return False


def _relative_posix(path: Path, base: Path) -> str:
    return os.path.relpath(path, base).replace("\\", "/")


def _copy_stats_dict(stats: CopyStats | None) -> dict[str, int] | None:
    if stats is None:
        return None
    return {
        "copied": stats.copied,
        "skipped": stats.skipped,
        "missing_sources": stats.missing_sources,
    }


def _aggregate_progress(campaign_summaries: list[dict[str, Any]]) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for campaign in campaign_summaries:
        for status, count in campaign["progress"].get("statuses", {}).items():
            totals[status] += count
    return dict(sorted(totals.items()))


if __name__ == "__main__":
    raise SystemExit(main())
