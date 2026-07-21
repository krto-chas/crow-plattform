from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VERSION_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)\s*(?P<op>>=|==)?\s*(?P<version>[0-9]+(?:\.[0-9]+){0,2})?$"
)


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0, 0, 0])[:3])  # type: ignore[return-value]


@dataclass(frozen=True)
class PackValidation:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class KnowledgePackRuntime:
    """Loads, validates and registers data-only Crow knowledge packs."""

    def __init__(
        self, root: Path, *, platform_version: str = "0.7.0", building_graph_version: str = "1.0.0"
    ):
        self.root = root
        self.versions = {
            "crow.platform": platform_version,
            "building_graph": building_graph_version,
        }

    def discover(self) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        packs: list[dict[str, Any]] = []
        for directory in sorted(path for path in self.root.iterdir() if path.is_dir()):
            try:
                pack = self.load(directory)
                validation = self.validate(pack)
                packs.append(self._summary(pack, validation))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                packs.append(
                    {
                        "id": directory.name,
                        "path": str(directory),
                        "status": "invalid",
                        "errors": [str(exc)],
                    }
                )
        return packs

    def load(self, directory: Path) -> dict[str, Any]:
        manifest_path = directory / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"Manifest saknas: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pack: dict[str, Any] = {"manifest": manifest, "path": str(directory)}
        for key in ("ontology", "symbols", "rules", "recommendations", "glossary", "dimensions"):
            filename = manifest.get(key)
            if filename:
                path = directory / str(filename)
                if not path.exists():
                    raise ValueError(f"Refererad fil saknas: {filename}")
                pack[key] = json.loads(path.read_text(encoding="utf-8"))
            else:
                pack[key] = {} if key in {"ontology", "symbols", "glossary", "dimensions"} else []
        return pack

    def validate(self, pack: dict[str, Any]) -> PackValidation:
        errors: list[str] = []
        warnings: list[str] = []
        manifest = pack.get("manifest", {})
        for key in ("id", "name", "version"):
            if not manifest.get(key):
                errors.append(f"Manifestfält saknas: {key}")
        errors.extend(self._validate_dependencies(manifest.get("requires", [])))
        errors.extend(self._validate_ontology(pack.get("ontology", {})))
        rules = pack.get("rules", [])
        if isinstance(rules, dict):
            rules = rules.get("rules", [])
        rule_ids = {str(rule.get("id")) for rule in rules if rule.get("id")}
        for recommendation in pack.get("recommendations", []):
            rule_id = recommendation.get("rule_id")
            if rule_id and rule_id not in rule_ids:
                errors.append(f"Rekommendation refererar okänd regel: {rule_id}")
        symbols = pack.get("symbols", {})
        if isinstance(symbols, dict) and not symbols:
            warnings.append("Symbolbiblioteket är tomt")
        return PackValidation(not errors, tuple(errors), tuple(warnings))

    def registry(self) -> dict[str, Any]:
        packs = self.discover()
        return {
            "schema": "crow-knowledge-registry-v0.1",
            "pack_count": len(packs),
            "active_count": sum(1 for pack in packs if pack.get("status") == "active"),
            "packs": packs,
        }

    def rules(self, pack_id: str) -> list[dict[str, Any]]:
        pack = self._get(pack_id)
        validation = self.validate(pack)
        if not validation.valid:
            raise ValueError("Kunskapspaketet är inte giltigt: " + "; ".join(validation.errors))
        rules = pack.get("rules", [])
        return list(rules.get("rules", [])) if isinstance(rules, dict) else list(rules)

    def _get(self, pack_id: str) -> dict[str, Any]:
        for directory in self.root.iterdir() if self.root.exists() else ():
            if directory.is_dir():
                pack = self.load(directory)
                if pack.get("manifest", {}).get("id") == pack_id:
                    return pack
        raise KeyError(pack_id)

    def _validate_dependencies(self, requirements: list[str]) -> list[str]:
        errors: list[str] = []
        for raw in requirements:
            match = _VERSION_RE.match(str(raw).strip())
            if not match:
                errors.append(f"Ogiltigt beroendekrav: {raw}")
                continue
            name = match.group("name")
            installed = self.versions.get(name)
            if installed is None:
                errors.append(f"Beroende saknas: {name}")
                continue
            required = match.group("version")
            operator = match.group("op")
            if (
                required
                and operator == ">="
                and _version_tuple(installed) < _version_tuple(required)
            ):
                errors.append(f"{name} {installed} uppfyller inte >= {required}")
            if (
                required
                and operator == "=="
                and _version_tuple(installed) != _version_tuple(required)
            ):
                errors.append(f"{name} {installed} uppfyller inte == {required}")
        return errors

    @staticmethod
    def _validate_ontology(ontology: dict[str, Any]) -> list[str]:
        classes = ontology.get("classes", []) if isinstance(ontology, dict) else []
        parents = {str(item["id"]): item.get("parent") for item in classes if item.get("id")}
        errors: list[str] = []
        for node in parents:
            seen: set[str] = set()
            current: str | None = node
            while current:
                if current in seen:
                    errors.append(f"Cykel i ontologi vid {node}")
                    break
                seen.add(current)
                parent = parents.get(current)
                if parent and parent not in parents:
                    errors.append(f"Okänd överklass {parent} för {current}")
                    break
                current = str(parent) if parent else None
        return sorted(set(errors))

    @staticmethod
    def _summary(pack: dict[str, Any], validation: PackValidation) -> dict[str, Any]:
        manifest = pack["manifest"]
        rules = pack.get("rules", [])
        rules = rules.get("rules", []) if isinstance(rules, dict) else rules
        ontology = pack.get("ontology", {})
        symbols = pack.get("symbols", {})
        return {
            "id": manifest.get("id"),
            "name": manifest.get("name"),
            "version": manifest.get("version"),
            "status": "active" if validation.valid else "invalid",
            "requires": manifest.get("requires", []),
            "rule_count": len(rules),
            "ontology_class_count": len(ontology.get("classes", [])),
            "symbol_count": len(symbols.get("symbols", []))
            if isinstance(symbols, dict)
            else len(symbols),
            "recommendation_count": len(pack.get("recommendations", [])),
            "errors": list(validation.errors),
            "warnings": list(validation.warnings),
        }
