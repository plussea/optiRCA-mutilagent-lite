"""Tests for the heterogeneous evidence graph store."""

import json
import tempfile
from pathlib import Path

import pytest

from optirc_lite.storage.evidence_graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceEdge,
    NodeType,
    EdgeType,
)


@pytest.fixture
def temp_graph():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence_graph.json"
        graph = EvidenceGraph(path=path)
        graph.init()
        yield graph


def test_init_creates_empty_graph(temp_graph):
    assert temp_graph.path.exists()
    data = json.loads(temp_graph.path.read_text(encoding="utf-8"))
    assert data["nodes"] == []
    assert data["edges"] == []


def test_add_typed_nodes(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a", device_type="OLT"))
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1", device_id="olt-a", direction="out"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001", alarm_type="LOS", severity="Critical"))

    nodes = temp_graph.get_nodes()
    assert len(nodes) == 3
    assert {n.type for n in nodes} == {NodeType.DEVICE, NodeType.PORT, NodeType.ALARM}


def test_add_edge_with_properties(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1", device_id="olt-a"))
    temp_graph.add_edge(
        EvidenceEdge(
            source="dev:olt-a",
            target="port:olt-a:1",
            type=EdgeType.TOPOLOGY,
            confidence=1.0,
        )
    )

    edges = temp_graph.get_edges()
    assert len(edges) == 1
    assert edges[0].type == EdgeType.TOPOLOGY
    assert edges[0].confidence == 1.0


def test_rejects_propagates_from_device(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))

    with pytest.raises(ValueError, match="PROPAGATES edges cannot originate from DEVICE"):
        temp_graph.add_edge(
            EvidenceEdge(
                source="dev:olt-a",
                target="alm:001",
                type=EdgeType.PROPAGATES,
            )
        )


def test_allows_propagates_from_port_and_link(temp_graph):
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1"))
    temp_graph.add_node(EvidenceNode(id="link:ab", type=NodeType.LINK, link_id="link:ab"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))

    temp_graph.add_edge(EvidenceEdge(source="port:olt-a:1", target="alm:001", type=EdgeType.PROPAGATES))
    temp_graph.add_edge(EvidenceEdge(source="link:ab", target="alm:001", type=EdgeType.PROPAGATES))

    assert len(temp_graph.get_edges()) == 2


def test_neighbors_by_type(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))
    temp_graph.add_edge(EvidenceEdge(source="dev:olt-a", target="port:olt-a:1", type=EdgeType.TOPOLOGY))
    temp_graph.add_edge(EvidenceEdge(source="port:olt-a:1", target="alm:001", type=EdgeType.BELONGS_TO))

    result = temp_graph.neighbors(["dev:olt-a"], depth=2)
    assert len(result.nodes) == 3
    assert len(result.edges) == 2

    topo_only = temp_graph.neighbors(["dev:olt-a"], depth=2, edge_types={EdgeType.TOPOLOGY})
    assert len(topo_only.nodes) == 2
    assert len(topo_only.edges) == 1


def test_existing_lite_graph_store_still_works():
    """LiteGraphStore API continues to work for the existing /v1/sessions workflow."""
    from optirc_lite.storage.graph_store import LiteGraphStore

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "knowledge_graph.json"
        store = LiteGraphStore(path=path)
        store.init()
        store.add_case("session-123", "B-C fiber cut", ["olt-a", "olt-b"])
        result = store.neighbors(["case:session-123"], depth=1)
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2
