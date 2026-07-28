"""Tests for EvidenceGraph navigation and PROPAGATES edges."""

import json
import tempfile
from pathlib import Path

import pytest

from optirc_lite.storage.evidence_graph import (
    EdgeType,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    NodeType,
)


@pytest.fixture
def temp_graph():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence_graph.json"
        graph = EvidenceGraph(path=path)
        graph.init()
        yield graph


def test_parse_node_id(temp_graph):
    assert temp_graph.parse_node_id("dev:olt-a") == (NodeType.DEVICE, "olt-a")
    assert temp_graph.parse_node_id("port:olt-a:1") == (NodeType.PORT, "olt-a:1")
    assert temp_graph.parse_node_id("link:ab") == (NodeType.LINK, "ab")
    assert temp_graph.parse_node_id("alm:001") == (NodeType.ALARM, "001")
    assert temp_graph.parse_node_id("svc:voice") == (NodeType.SERVICE, "voice")
    assert temp_graph.parse_node_id("unknown") == (None, "unknown")


def test_get_alarms_for_node(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1", device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001", alarm_type="LOS"))
    temp_graph.add_node(EvidenceNode(id="alm:002", type=NodeType.ALARM, alarm_id="alm:002", alarm_type="LOS"))
    temp_graph.add_edge(EvidenceEdge(source="alm:001", target="port:olt-a:1", type=EdgeType.BELONGS_TO))
    temp_graph.add_edge(EvidenceEdge(source="alm:002", target="dev:olt-a", type=EdgeType.BELONGS_TO))

    alarms = temp_graph.get_alarms_for_node("dev:olt-a")
    assert {a.id for a in alarms} == {"alm:001", "alm:002"}

    alarms = temp_graph.get_alarms_for_node("port:olt-a:1")
    assert {a.id for a in alarms} == {"alm:001"}


def test_add_propagates_edge(temp_graph):
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))
    temp_graph.add_edge(EvidenceEdge(source="port:olt-a:1", target="alm:001", type=EdgeType.PROPAGATES))

    propagates = temp_graph.get_edges(EdgeType.PROPAGATES)
    assert len(propagates) == 1
    assert propagates[0].source == "port:olt-a:1"
    assert propagates[0].target == "alm:001"


def test_rejects_propagates_from_device(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))

    with pytest.raises(ValueError, match="PROPAGATES edges cannot originate from DEVICE"):
        temp_graph.add_edge(EvidenceEdge(source="dev:olt-a", target="alm:001", type=EdgeType.PROPAGATES))


def test_get_neighbors_by_type(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1", device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))
    temp_graph.add_edge(EvidenceEdge(source="dev:olt-a", target="port:olt-a:1", type=EdgeType.TOPOLOGY))
    temp_graph.add_edge(EvidenceEdge(source="alm:001", target="port:olt-a:1", type=EdgeType.BELONGS_TO))

    topo_neighbors = temp_graph.get_neighbors_by_type("dev:olt-a", EdgeType.TOPOLOGY)
    assert {n.id for n in topo_neighbors.nodes} == {"dev:olt-a", "port:olt-a:1"}
    assert len(topo_neighbors.edges) == 1

    belongs_neighbors = temp_graph.get_neighbors_by_type("port:olt-a:1", EdgeType.BELONGS_TO)
    assert {n.id for n in belongs_neighbors.nodes} == {"port:olt-a:1", "alm:001"}


def test_build_propagates_edges(temp_graph):
    temp_graph.add_node(EvidenceNode(id="dev:olt-a", type=NodeType.DEVICE, device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="port:olt-a:1", type=NodeType.PORT, port_id="olt-a:1", device_id="olt-a"))
    temp_graph.add_node(EvidenceNode(id="link:ab", type=NodeType.LINK, link_id="ab", endpoint_a="olt-a:1", endpoint_b="olt-b:1"))
    temp_graph.add_node(EvidenceNode(id="alm:001", type=NodeType.ALARM, alarm_id="alm:001"))
    temp_graph.add_edge(EvidenceEdge(source="dev:olt-a", target="port:olt-a:1", type=EdgeType.TOPOLOGY))
    temp_graph.add_edge(EvidenceEdge(source="port:olt-a:1", target="link:ab", type=EdgeType.TOPOLOGY))
    temp_graph.add_edge(EvidenceEdge(source="alm:001", target="port:olt-a:1", type=EdgeType.BELONGS_TO))

    temp_graph.build_propagates_edges()

    propagates = {(e.source, e.target) for e in temp_graph.get_edges(EdgeType.PROPAGATES)}
    assert ("port:olt-a:1", "alm:001") in propagates
    assert ("link:ab", "alm:001") in propagates
