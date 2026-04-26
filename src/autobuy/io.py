from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.is_absolute():
        json_path = (PROJECT_ROOT / json_path).resolve()

    with json_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    json_path = Path(path)
    if not json_path.is_absolute():
        json_path = (PROJECT_ROOT / json_path).resolve()

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _resolve_config_ref(folder: str, ref: str) -> Path:
    raw = Path(ref)
    if raw.is_absolute():
        return raw

    direct = CONFIG_DIR / folder / ref
    if direct.exists():
        return direct

    if raw.suffix == "":
        with_suffix = direct.with_suffix(".json")
        if with_suffix.exists():
            return with_suffix

    repo_relative = PROJECT_ROOT / ref
    if repo_relative.exists():
        return repo_relative

    if raw.suffix == "":
        repo_relative_json = repo_relative.with_suffix(".json")
        if repo_relative_json.exists():
            return repo_relative_json

    return direct


def load_manifest(kind: str) -> dict[str, Any]:
    if kind not in {"vehicle", "scenario"}:
        raise ValueError("kind must be 'vehicle' or 'scenario'.")
    return load_json(CONFIG_DIR / "manifests" / f"{kind}_input_manifest.json")


def build_template_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    template: dict[str, Any] = {}
    for section in manifest.get("sections", []):
        section_name = section["name"]
        template[section_name] = {}
        for field in section.get("fields", []):
            value = field.get("example")
            template[section_name][field["name"]] = value
    return template


def validate_against_manifest(payload: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for section in manifest.get("sections", []):
        section_name = section["name"]
        section_payload = payload.get(section_name)
        if section.get("required", True) and not isinstance(section_payload, dict):
            missing.append(section_name)
            continue

        if not isinstance(section_payload, dict):
            continue

        for field in section.get("fields", []):
            if field.get("required", False) and field["name"] not in section_payload:
                missing.append(f"{section_name}.{field['name']}")

    return missing


def load_local_constants(ref: str | Path) -> dict[str, Any]:
    if isinstance(ref, Path):
        return load_json(ref)
    return load_json(_resolve_config_ref("local", ref))


def load_vehicle(ref: str | Path) -> dict[str, Any]:
    payload = load_json(_resolve_config_ref("vehicles", str(ref)) if not isinstance(ref, Path) else ref)
    missing = validate_against_manifest(payload, load_manifest("vehicle"))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Vehicle config is missing required fields: {joined}")
    return payload


def load_scenario(ref: str | Path) -> dict[str, Any]:
    payload = load_json(_resolve_config_ref("scenarios", str(ref)) if not isinstance(ref, Path) else ref)
    missing = validate_against_manifest(payload, load_manifest("scenario"))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Scenario config is missing required fields: {joined}")
    return payload


def load_scenario_bundle(ref: str | Path) -> dict[str, Any]:
    scenario_path = _resolve_config_ref("scenarios", str(ref)) if not isinstance(ref, Path) else ref
    scenario = load_scenario(scenario_path)
    references = scenario["references"]

    return {
        "scenario_path": str(Path(scenario_path).resolve()),
        "scenario": scenario,
        "vehicle": load_vehicle(references["vehicle"]),
        "local_constants": load_local_constants(references["local_constants"]),
    }
