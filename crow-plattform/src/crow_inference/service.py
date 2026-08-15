from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from crow_building_graph.repository import GraphRepository
from crow_building_graph.service import BuildingGraphService

from .engine import DEFAULT_RULES, InferenceEngine
from .models import InferenceRule


class InferenceService:
    """Persistent lifecycle for reproducible inference runs.

    Explicit graph facts remain in graph.json. Current derived facts are stored in
    inferences.json and immutable run metadata/diffs in inference-runs.json.
    """

    def __init__(
        self,
        graph_path: Path,
        result_path: Path | None = None,
        history_path: Path | None = None,
    ):
        self.repository = GraphRepository(graph_path)
        self.graph_path = graph_path
        self.result_path = result_path or graph_path.with_name("inferences.json")
        self.history_path = history_path or graph_path.with_name("inference-runs.json")
        self.review_path = graph_path.with_name("inference-reviews.json")

    def run(
        self,
        rules: list[dict[str, Any]] | None = None,
        *,
        persist: bool = True,
        max_iterations: int = 8,
        force: bool = False,
    ) -> dict[str, Any]:
        graph = self.repository.load()
        fingerprint = self._graph_fingerprint(graph)
        selected = (
            tuple(InferenceRule(**item) for item in rules) if rules is not None else DEFAULT_RULES
        )
        rule_fingerprint = self._rule_fingerprint(selected, max_iterations=max_iterations)
        previous = self._read_json(self.result_path)

        if (
            not force
            and previous
            and previous.get("graph_fingerprint") == fingerprint
            and previous.get("rule_fingerprint") == rule_fingerprint
        ):
            cached = dict(previous)
            cached["cache"] = {"hit": True, "reason": "graph_and_rules_unchanged"}
            return cached

        result = InferenceEngine(graph).infer(selected, max_iterations=max_iterations)
        run_number = self._next_run_number()
        created_at = datetime.now(UTC).isoformat()
        run_id = f"inference-run-{run_number:06d}"
        diff = self._diff(previous, result)
        result.update(
            {
                "schema": "crow-inference-v0.3",
                "run_id": run_id,
                "run_number": run_number,
                "created_at": created_at,
                "graph_fingerprint": fingerprint,
                "rule_fingerprint": rule_fingerprint,
                "lifecycle_status": "current",
                "cache": {"hit": False},
                "diff": diff,
            }
        )
        if persist:
            self._atomic_write(self.result_path, result)
            history = self._history_document()
            history["runs"].append(
                {
                    "run_id": run_id,
                    "run_number": run_number,
                    "created_at": created_at,
                    "graph_revision": result.get("graph_revision"),
                    "graph_fingerprint": fingerprint,
                    "rule_fingerprint": rule_fingerprint,
                    "summary": result.get("summary", {}),
                    "diff": diff,
                }
            )
            self._atomic_write(self.history_path, history)
        return result

    def status(self) -> dict[str, Any]:
        graph = self.repository.load()
        current_fingerprint = self._graph_fingerprint(graph)
        result = self._read_json(self.result_path)
        if not result:
            return {
                "schema": "crow-inference-status-v0.1",
                "status": "missing",
                "graph_fingerprint": current_fingerprint,
                "reason": "no_persisted_inference_run",
            }
        stale = (
            result.get("graph_fingerprint") != current_fingerprint
            or result.get("lifecycle_status") == "stale"
        )
        reason = (
            result.get("invalidation_reason")
            if result.get("lifecycle_status") == "stale"
            else ("graph_changed" if stale else "graph_unchanged")
        )
        return {
            "schema": "crow-inference-status-v0.1",
            "status": "stale" if stale else "current",
            "run_id": result.get("run_id"),
            "run_number": result.get("run_number"),
            "stored_graph_fingerprint": result.get("graph_fingerprint"),
            "graph_fingerprint": current_fingerprint,
            "graph_revision": graph.get("revision", 1),
            "reason": reason,
        }

    def invalidate(self, *, reason: str = "manual") -> dict[str, Any]:
        result = self._read_json(self.result_path)
        if not result:
            return {"status": "missing", "invalidated": False}
        result["lifecycle_status"] = "stale"
        result["invalidated_at"] = datetime.now(UTC).isoformat()
        result["invalidation_reason"] = reason
        self._atomic_write(self.result_path, result)
        return {
            "status": "stale",
            "invalidated": True,
            "run_id": result.get("run_id"),
            "reason": reason,
        }

    def history(self) -> dict[str, Any]:
        return self._history_document()

    def diff(self, from_run: int | None = None, to_run: int | None = None) -> dict[str, Any]:
        history = self._history_document().get("runs", [])
        if not history:
            return {
                "schema": "crow-inference-diff-v0.1",
                "from_run": None,
                "to_run": None,
                "diff": self._empty_diff(),
            }
        target = history[-1] if to_run is None else self._find_run(history, to_run)
        if from_run is None:
            previous = next(
                (item for item in reversed(history) if item["run_number"] < target["run_number"]),
                None,
            )
            return {
                "schema": "crow-inference-diff-v0.1",
                "from_run": previous["run_number"] if previous else None,
                "to_run": target["run_number"],
                "diff": target.get("diff", self._empty_diff()),
            }
        source = self._find_run(history, from_run)
        if source["run_number"] + 1 == target["run_number"]:
            comparison = target.get("diff", self._empty_diff())
        else:
            comparison = {
                "available": False,
                "reason": "non_adjacent_run_payloads_are_not_archived",
            }
        return {
            "schema": "crow-inference-diff-v0.1",
            "from_run": source["run_number"],
            "to_run": target["run_number"],
            "diff": comparison,
        }

    def list(self, *, refresh: bool = False) -> dict[str, Any]:
        if refresh or not self.result_path.exists():
            return self.run(force=refresh)
        result = self._read_json(self.result_path)
        current = self.status()
        result["lifecycle_status"] = current["status"]
        return result

    def query(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        minimum_confidence: float = 0.0,
        refresh: bool = False,
    ) -> dict[str, Any]:
        result = self.list(refresh=refresh)
        matches = InferenceEngine(self.repository.load()).query(
            result,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            minimum_confidence=minimum_confidence,
        )
        return {
            "schema": result.get("schema"),
            "matches": matches,
            "count": len(matches),
            "lifecycle_status": result.get("lifecycle_status"),
        }

    def conflicts(self, *, refresh: bool = False) -> dict[str, Any]:
        result = self.list(refresh=refresh)
        conflicts = result.get("conflicts", [])
        return {
            "schema": result.get("schema"),
            "conflicts": conflicts,
            "count": len(conflicts),
            "lifecycle_status": result.get("lifecycle_status"),
        }

    def explain(self, relation_id: str, *, refresh: bool = False) -> dict[str, Any]:
        result = self.list(refresh=refresh)
        for relation in result.get("derived_relations", []):
            if relation["id"] == relation_id:
                return {
                    **relation,
                    "run_id": result.get("run_id"),
                    "lifecycle_status": result.get("lifecycle_status"),
                }
        raise KeyError(relation_id)

    def reviews(self, *, status: str | None = None) -> dict[str, Any]:
        document = self._review_document()
        items = document["reviews"]
        if status is not None:
            items = [item for item in items if item.get("status") == status]
        return {
            "schema": document["schema"],
            "reviews": items,
            "count": len(items),
            "summary": self._review_summary(document["reviews"]),
        }

    def review_relation(
        self,
        relation_id: str,
        *,
        decision: str,
        actor: str = "system",
        note: str | None = None,
    ) -> dict[str, Any]:
        if decision not in {"accepted", "rejected"}:
            raise ValueError("decision måste vara accepted eller rejected")
        document = self._review_document()
        item = next(
            (entry for entry in document["reviews"] if entry["relation_id"] == relation_id), None
        )
        if item is not None and item.get("status") == "promoted":
            raise ValueError("Promoterad inferens kan inte omprövas")
        relation = self.explain(relation_id)
        if relation.get("lifecycle_status") != "current":
            raise ValueError("Inaktuell inferens kan inte granskas")
        timestamp = datetime.now(UTC).isoformat()
        event = {"status": decision, "actor": actor, "note": note, "created_at": timestamp}
        if item is None:
            item = {
                "relation_id": relation_id,
                "run_id": relation.get("run_id"),
                "status": decision,
                "actor": actor,
                "note": note,
                "created_at": timestamp,
                "updated_at": timestamp,
                "history": [event],
            }
            document["reviews"].append(item)
        else:
            if item.get("status") == "promoted":
                raise ValueError("Promoterad inferens kan inte omprövas")
            item.update({"status": decision, "actor": actor, "note": note, "updated_at": timestamp})
            item.setdefault("history", []).append(event)
        self._atomic_write(self.review_path, document)
        return item

    def promote_relation(
        self,
        relation_id: str,
        *,
        actor: str = "system",
        note: str | None = None,
    ) -> dict[str, Any]:
        relation = self.explain(relation_id)
        if relation.get("lifecycle_status") != "current":
            raise ValueError("Inaktuell inferens kan inte promoveras")
        document = self._review_document()
        review = next(
            (entry for entry in document["reviews"] if entry["relation_id"] == relation_id), None
        )
        if review is None or review.get("status") != "accepted":
            raise ValueError("Inferensen måste vara accepterad före promotion")
        existing = next(
            (
                item
                for item in self.repository.load()["relations"]
                if (item["source_id"], item["relation_type"], item["target_id"])
                == (relation["source_id"], relation["relation_type"], relation["target_id"])
            ),
            None,
        )
        if existing is None:
            graph_service = BuildingGraphService(self.repository)
            promoted = graph_service.create_relation(
                source_id=relation["source_id"],
                relation_type=relation["relation_type"],
                target_id=relation["target_id"],
                evidence_ids=list(relation.get("evidence_ids", [])),
                confidence=float(relation.get("confidence", 0.0)),
                metadata={
                    "promoted_from_inference": relation_id,
                    "inference_run_id": relation.get("run_id"),
                    "inference_rule_id": relation.get("rule_id"),
                    "review_actor": actor,
                    "review_note": note,
                },
            )
        else:
            promoted = existing
        timestamp = datetime.now(UTC).isoformat()
        review.update(
            {
                "status": "promoted",
                "promoted_relation_id": promoted["id"],
                "promoted_at": timestamp,
                "promoted_by": actor,
                "updated_at": timestamp,
            }
        )
        review.setdefault("history", []).append(
            {
                "status": "promoted",
                "actor": actor,
                "note": note,
                "created_at": timestamp,
                "promoted_relation_id": promoted["id"],
            }
        )
        self._atomic_write(self.review_path, document)
        self.invalidate(reason=f"promoted:{relation_id}")
        return {"review": review, "relation": promoted, "inference_status": "stale"}

    def _review_document(self) -> dict[str, Any]:
        data = self._read_json(self.review_path)
        if not data:
            return {"schema": "crow-inference-review-v0.1", "reviews": []}
        data.setdefault("schema", "crow-inference-review-v0.1")
        data.setdefault("reviews", [])
        return data

    @staticmethod
    def _review_summary(items: list[dict[str, Any]]) -> dict[str, int]:
        summary = {"accepted": 0, "rejected": 0, "promoted": 0}
        for item in items:
            status = str(item.get("status", ""))
            if status in summary:
                summary[status] += 1
        summary["total"] = len(items)
        return summary

    @staticmethod
    def _graph_fingerprint(graph: dict[str, Any]) -> str:
        canonical = json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _rule_fingerprint(rules: tuple[InferenceRule, ...], *, max_iterations: int) -> str:
        payload = {"max_iterations": max_iterations, "rules": [rule.__dict__ for rule in rules]}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _diff(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
        old = {item["id"]: item for item in (previous or {}).get("derived_relations", [])}
        new = {item["id"]: item for item in current.get("derived_relations", [])}
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(key for key in set(old) & set(new) if old[key] != new[key])
        old_conflicts = {item["id"] for item in (previous or {}).get("conflicts", [])}
        new_conflicts = {item["id"] for item in current.get("conflicts", [])}
        return {
            "added_relation_ids": added,
            "removed_relation_ids": removed,
            "changed_relation_ids": changed,
            "added_conflict_ids": sorted(new_conflicts - old_conflicts),
            "removed_conflict_ids": sorted(old_conflicts - new_conflicts),
            "counts": {
                "added_relations": len(added),
                "removed_relations": len(removed),
                "changed_relations": len(changed),
                "added_conflicts": len(new_conflicts - old_conflicts),
                "removed_conflicts": len(old_conflicts - new_conflicts),
            },
        }

    @staticmethod
    def _empty_diff() -> dict[str, Any]:
        return {
            "added_relation_ids": [],
            "removed_relation_ids": [],
            "changed_relation_ids": [],
            "added_conflict_ids": [],
            "removed_conflict_ids": [],
            "counts": {
                "added_relations": 0,
                "removed_relations": 0,
                "changed_relations": 0,
                "added_conflicts": 0,
                "removed_conflicts": 0,
            },
        }

    def _history_document(self) -> dict[str, Any]:
        return self._read_json(self.history_path) or {
            "schema": "crow-inference-runs-v0.1",
            "runs": [],
        }

    def _next_run_number(self) -> int:
        runs = self._history_document().get("runs", [])
        return max((int(item.get("run_number", 0)) for item in runs), default=0) + 1

    @staticmethod
    def _find_run(history: list[dict[str, Any]], run_number: int) -> dict[str, Any]:
        for item in history:
            if int(item.get("run_number", -1)) == run_number:
                return item
        raise KeyError(run_number)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
