from __future__ import annotations

from typing import TYPE_CHECKING

from .decision_graph import DecisionGraph, GraphEdge, GraphNode, Relation
from .decision_models import Conflict
from .models import Claim

if TYPE_CHECKING:
    from .pipeline import DecisionPipelineResult


def build_decision_graph(
    claims: tuple[Claim, ...],
    conflict: Conflict,
    result: DecisionPipelineResult,
) -> DecisionGraph:
    graph = DecisionGraph()
    claim_node_ids = {claim.id for claim in claims}

    for claim in claims:
        graph.add_node(GraphNode(claim.id, "claim"))

    graph.add_node(GraphNode(conflict.id, "conflict"))
    for claim_id in conflict.claim_ids:
        graph.add_edge(GraphEdge(claim_id, Relation.CONTRADICTS, conflict.id))

    decision = result.authority_decision
    graph.add_node(GraphNode(decision.id, "authority_decision"))
    graph.add_edge(GraphEdge(conflict.id, Relation.CREATES, decision.id))

    if decision.selected_claim_id:
        graph.add_edge(GraphEdge(decision.selected_claim_id, Relation.SUPPORTS, decision.id))
    for rejected_claim_id in decision.rejected_claim_ids:
        graph.add_edge(GraphEdge(rejected_claim_id, Relation.REJECTS, decision.id))

    if result.accepted_claim is not None:
        graph.add_node(GraphNode(result.accepted_claim.id, "accepted_claim"))
        graph.add_edge(GraphEdge(decision.id, Relation.CREATES, result.accepted_claim.id))
        graph.add_edge(
            GraphEdge(result.accepted_claim.claim.id, Relation.SELECTS, result.accepted_claim.id)
        )

    previous_id = result.accepted_claim.id if result.accepted_claim else decision.id
    ordered_objects = (
        (result.technical_delta, "technical_delta"),
        (result.commercial_impact, "commercial_impact"),
        (result.ata_opportunity, "ata_opportunity"),
        (result.estimate_line, "estimate_line"),
        (result.client_question, "client_question"),
        (result.reservation, "reservation"),
    )
    for obj, node_type in ordered_objects:
        if obj is None:
            continue
        graph.add_node(GraphNode(obj.id, node_type))
        relation = Relation.PRICES if node_type == "commercial_impact" else Relation.CREATES
        graph.add_edge(GraphEdge(previous_id, relation, obj.id))
        previous_id = obj.id

    for item in result.evidence:
        graph.add_node(GraphNode(item.id, "evidence"))
        for claim_id in item.source_claim_ids:
            if claim_id in claim_node_ids:
                graph.add_edge(GraphEdge(claim_id, Relation.SUPPORTS, item.id))
        if item.rule_id:
            rule_node_id = f"rule:{item.rule_id}"
            graph.add_node(GraphNode(rule_node_id, "rule"))
            graph.add_edge(GraphEdge(rule_node_id, Relation.EXPLAINS, item.id))

    return graph
