from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .batch_pipeline import PricingInput
from .decision_graph import DecisionGraph
from .decision_models import RoundingPolicy
from .project import CrowProject, ProjectRun


class ProjectTransaction(Protocol):
    def save_project(self, project: CrowProject) -> None: ...

    def save_graph(self, graph_id: str, graph: DecisionGraph) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class ProjectUnitOfWork(Protocol):
    def begin(self) -> ProjectTransaction: ...


@dataclass(frozen=True, slots=True)
class TransactionalExecutionResult:
    project: CrowProject
    run: ProjectRun
    graph_ids: tuple[str, ...]


def execute_project_transactionally(
    project: CrowProject,
    *,
    run_id: str,
    pricing_by_conflict_key: dict[tuple[str, str, str], PricingInput],
    rounding: RoundingPolicy,
    unit_of_work: ProjectUnitOfWork,
    actor: str = "system",
) -> TransactionalExecutionResult:
    transaction = unit_of_work.begin()
    try:
        updated, run, graphs = project.execute(
            run_id=run_id,
            pricing_by_conflict_key=pricing_by_conflict_key,
            rounding=rounding,
            actor=actor,
        )
        transaction.save_project(updated)
        for graph_id, graph in zip(run.graph_ids, graphs, strict=True):
            transaction.save_graph(graph_id, graph)
        transaction.commit()
        return TransactionalExecutionResult(updated, run, run.graph_ids)
    except Exception:
        transaction.rollback()
        raise


class InMemoryProjectUnitOfWork:
    def __init__(self, *, fail_on_commit: bool = False) -> None:
        self.projects: dict[str, CrowProject] = {}
        self.graphs: dict[str, DecisionGraph] = {}
        self.fail_on_commit = fail_on_commit
        self.rollbacks = 0
        self.commits = 0

    def begin(self) -> _InMemoryTransaction:
        return _InMemoryTransaction(self)


class _InMemoryTransaction:
    def __init__(self, owner: InMemoryProjectUnitOfWork) -> None:
        self._owner = owner
        self._projects: dict[str, CrowProject] = {}
        self._graphs: dict[str, DecisionGraph] = {}
        self._closed = False

    def save_project(self, project: CrowProject) -> None:
        self._ensure_open()
        self._projects[project.id] = project

    def save_graph(self, graph_id: str, graph: DecisionGraph) -> None:
        self._ensure_open()
        self._graphs[graph_id] = graph

    def commit(self) -> None:
        self._ensure_open()
        if self._owner.fail_on_commit:
            raise RuntimeError("Simulated transaction commit failure")
        self._owner.projects.update(self._projects)
        self._owner.graphs.update(self._graphs)
        self._owner.commits += 1
        self._closed = True

    def rollback(self) -> None:
        if not self._closed:
            self._projects.clear()
            self._graphs.clear()
            self._owner.rollbacks += 1
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Transaction is already closed")
