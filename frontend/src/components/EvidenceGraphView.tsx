import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { EvidenceEdge, EvidenceGraph, EvidenceNode } from "../lib/types";
import { AlarmDot, DefaultNode, DeviceNode, LinkNode, PortNode } from "./EvidenceNodes";
import type { StageId } from "./StageTimeline";

interface Props {
  graph: EvidenceGraph;
  rootCause?: string;
  currentStage?: StageId | null;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
}

const NODE_WIDTH = 150;
const NODE_HEIGHT = 64;

function nodeColor(type: EvidenceNode["type"]) {
  switch (type) {
    case "Device":
      return "#2563eb";
    case "Port":
      return "#64748b";
    case "Link":
      return "#0891b2";
    case "Alarm":
      return "#dc2626";
    default:
      return "#475569";
  }
}

function layerForType(type: EvidenceNode["type"]) {
  switch (type) {
    case "Device":
      return 0;
    case "Port":
      return 1;
    case "Link":
      return 2;
    case "Alarm":
      return 3;
    default:
      return 4;
  }
}

function buildReactFlowNodes(
  graph: EvidenceGraph,
  rootCause?: string,
  selectedId?: string | null,
): Node[] {
  const byLayer: Record<number, EvidenceNode[]> = {};
  for (const node of graph.nodes) {
    const layer = layerForType(node.type);
    byLayer[layer] = byLayer[layer] ?? [];
    byLayer[layer].push(node);
  }

  const positions = new Map<string, { x: number; y: number }>();
  const layerKeys = Object.keys(byLayer)
    .map(Number)
    .sort((a, b) => a - b);

  let currentX = 0;
  for (const layer of layerKeys) {
    const nodes = byLayer[layer];
    const layerHeight = nodes.length * (NODE_HEIGHT + 24);
    nodes.forEach((node, index) => {
      positions.set(node.id, {
        x: currentX,
        y: index * (NODE_HEIGHT + 24) - layerHeight / 2,
      });
    });
    currentX += NODE_WIDTH + 80;
  }

  return graph.nodes.map((node) => ({
    id: node.id,
    type: node.type.toLowerCase(),
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    data: { ...node, isRoot: rootCause ? node.id === rootCause : false, selected: node.id === selectedId },
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
  }));
}

function buildReactFlowEdges(edges: EvidenceEdge[], revealedTypes?: Set<EvidenceEdge["type"]>): Edge[] {
  return edges.map((edge, index) => {
    const revealed = !revealedTypes || revealedTypes.has(edge.type);
    return {
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: edge.type === "PROPAGATES",
      hidden: !revealed,
      style: {
        opacity: revealed ? 1 : 0,
        stroke:
          edge.type === "TOPOLOGY"
            ? "#475569"
            : edge.type === "BELONGS_TO"
              ? "#f59e0b"
              : edge.type === "PROPAGATES"
                ? "#f43f5e"
                : "#64748b",
        strokeWidth: edge.type === "PROPAGATES" ? 2.5 : 1.5,
        strokeDasharray: edge.type === "PROPAGATES" ? "6 4" : edge.type === "BELONGS_TO" ? "4 4" : undefined,
      },
    };
  });
}

function revealedEdgeTypesForStage(stage: StageId | null): Set<EvidenceEdge["type"]> {
  if (!stage) return new Set();
  switch (stage) {
    case "perception":
      return new Set();
    case "topology":
      return new Set(["TOPOLOGY"]);
    case "judge":
    case "rank":
      return new Set(["TOPOLOGY", "BELONGS_TO", "PROPAGATES"]);
    case "critic":
    case "assemble":
      return new Set(["TOPOLOGY", "BELONGS_TO", "PROPAGATES", "CARRIES"]);
    default:
      return new Set();
  }
}

export function EvidenceGraphView({ graph, rootCause, currentStage, selectedId, onSelect }: Props) {
  const [selected, setSelected] = useState<string | null>(selectedId ?? null);

  useEffect(() => {
    setSelected(selectedId ?? null);
  }, [selectedId]);

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      const next = selected === node.id ? null : node.id;
      setSelected(next);
      onSelect?.(next);
    },
    [selected, onSelect],
  );

  const onPaneClick = useCallback(() => {
    setSelected(null);
    onSelect?.(null);
  }, [onSelect]);

  const revealedTypes = useMemo(() => revealedEdgeTypesForStage(currentStage ?? null), [currentStage]);

  const initialNodes = useMemo(
    () => buildReactFlowNodes(graph, rootCause, selected),
    [graph, rootCause, selected],
  );
  const initialEdges = useMemo(
    () => buildReactFlowEdges(graph.edges, revealedTypes),
    [graph.edges, revealedTypes],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const nodeTypes = useMemo(
    () => ({
      device: DeviceNode,
      port: PortNode,
      link: LinkNode,
      alarm: AlarmDot,
      service: DefaultNode,
    }),
    [],
  );

  if (graph.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        暂无证据图数据
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Background color="#334155" gap={24} size={1} />
        <Controls />
        <MiniMap
          nodeColor={(node) => nodeColor((node.data as EvidenceNode).type)}
          maskColor="rgba(15, 23, 42, 0.7)"
          className="!bg-slate-900/80"
        />
      </ReactFlow>
    </div>
  );
}
