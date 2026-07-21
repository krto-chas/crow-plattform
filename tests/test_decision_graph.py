from crow_module_sdk.decision_graph import DecisionGraph, GraphEdge, GraphNode, Relation


def test_graph_traces_estimate_line_back_to_claim() -> None:
    graph = DecisionGraph()
    graph.add_node(GraphNode("claim-1", "claim"))
    graph.add_node(GraphNode("decision-1", "authority_decision"))
    graph.add_node(GraphNode("estimate-1", "estimate_line"))
    graph.add_edge(GraphEdge("claim-1", Relation.SUPPORTS, "decision-1"))
    graph.add_edge(GraphEdge("decision-1", Relation.CREATES, "estimate-1"))
    trace = graph.trace_to("estimate-1")
    assert len(trace) == 2
