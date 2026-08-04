"""Tests for Topology Builder weak inference and edge confidence."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from optirc_lite.api.main import app
from optirc_lite.storage.evidence_graph import EvidenceGraph, NodeType, EdgeType


client = TestClient(app)


@pytest.fixture
def temp_graph():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence_graph.json"
        graph = EvidenceGraph(path=path)
        graph.init()
        yield graph


def _topology_with_internal_ports():
    return {
        "devices": [{"device_id": "ROADM-X", "type": "ROADM"}],
        "ports": [
            {"port_id": "ROADM-X:west", "device_id": "ROADM-X", "direction": "out"},
            {"port_id": "ROADM-X:east", "device_id": "ROADM-X", "direction": "in"},
        ],
        "links": [],
    }


def test_topology_builds_explicit_link_with_full_confidence(temp_graph, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", temp_graph.path)
    from optirc_lite.skills.topology import TopologyBuilderSkill

    topology = {
        "devices": [{"device_id": "OLT-A", "type": "OLT"}],
        "ports": [
            {"port_id": "OLT-A:1", "device_id": "OLT-A", "direction": "out"},
        ],
        "links": [],
    }
    state = {
        "perception": {"alarm_count": 0, "alarms": []},
        "topology": topology,
    }
    skill = TopologyBuilderSkill()
    import asyncio
    asyncio.run(skill.run(state, None))

    edges = temp_graph.get_edges(EdgeType.TOPOLOGY)
    device_port_edges = [e for e in edges if e.source.startswith("dev:")]
    assert len(device_port_edges) == 1
    assert device_port_edges[0].confidence == 1.0
    assert device_port_edges[0].properties.get("inferred") is False


def test_topology_infers_internal_link(temp_graph, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", temp_graph.path)
    from optirc_lite.skills.topology import TopologyBuilderSkill

    state = {
        "perception": {"alarm_count": 0, "alarms": []},
        "topology": _topology_with_internal_ports(),
    }
    skill = TopologyBuilderSkill()
    import asyncio
    asyncio.run(skill.run(state, None))

    link_nodes = [n for n in temp_graph.get_nodes(NodeType.LINK) if n.properties.get("inferred")]
    assert len(link_nodes) == 1
    link = link_nodes[0]
    assert link.properties["confidence"] == 0.6
    assert link.properties["inferred"] is True

    edges = temp_graph.get_edges(EdgeType.TOPOLOGY)
    inferred_edges = [e for e in edges if e.properties.get("inferred")]
    assert len(inferred_edges) == 2
    assert all(e.properties["confidence"] == 0.6 for e in inferred_edges)


def test_topology_marks_isolated_nodes(temp_graph, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", temp_graph.path)
    from optirc_lite.skills.topology import TopologyBuilderSkill

    topology = {
        "devices": [
            {"device_id": "OLT-A", "type": "OLT"},
            {"device_id": "OLT-B", "type": "OLT"},
        ],
        "ports": [
            {"port_id": "OLT-A:1", "device_id": "OLT-A", "direction": "out"},
        ],
        "links": [],
    }
    state = {
        "perception": {"alarm_count": 0, "alarms": []},
        "topology": topology,
    }
    skill = TopologyBuilderSkill()
    import asyncio
    asyncio.run(skill.run(state, None))

    nodes_by_id = {n.id: n for n in temp_graph.get_nodes()}
    assert nodes_by_id["dev:OLT-A"].properties.get("isolated") is False
    assert nodes_by_id["port:OLT-A:1"].properties.get("isolated") is False
    assert nodes_by_id["dev:OLT-B"].properties.get("isolated") is True


def test_inferred_link_appears_in_diagnose(tmp_path, monkeypatch):
    monkeypatch.setattr("optirc_lite.config.settings.evidence_graph_path", tmp_path / "evidence_graph.json")
    monkeypatch.setattr("optirc_lite.config.settings.lancedb_path", tmp_path / "lancedb")
    EvidenceGraph(path=tmp_path / "evidence_graph.json").init()

    csv_path = tmp_path / "alarms.csv"
    csv_path.write_text(
        "告警源,名称,定位信息,级别,时间\n"
        "ROADM-X,MUT_LOS,核心机房,critical,2026-08-04T10:00:00Z\n",
        encoding="utf-8",
    )
    topology = _topology_with_internal_ports()

    with csv_path.open("rb") as f:
        response = client.post(
            "/api/v1/diagnose",
            files={"alarms": ("alarms.csv", f, "text/csv")},
            data={"topology": json.dumps(topology, ensure_ascii=False)},
        )

    assert response.status_code == 200
    body = response.json()
    evidence_graph = body["evidence_graph"]
    inferred_links = [
        n for n in evidence_graph.get("nodes", [])
        if n.get("type") == "Link" and n.get("inferred")
    ]
    assert len(inferred_links) == 1
    assert inferred_links[0].get("confidence") == 0.6

    isolated_nodes = [n for n in evidence_graph.get("nodes", []) if n.get("isolated")]
    assert len(isolated_nodes) == 0
