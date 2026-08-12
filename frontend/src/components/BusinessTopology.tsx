import { memo, useCallback, useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CircleAlert, Server } from "lucide-react";
import type { BusinessTopology, DiagnosisResult } from "../lib/types";

type DeviceState = "root" | "direct" | "affected" | "normal";

interface DeviceData extends Record<string, unknown> {
  label: string;
  deviceType?: string;
  state: DeviceState;
  alarmCount: number;
}

const STATE_LABEL: Record<DeviceState, string> = {
  root: "根因设备",
  direct: "首发告警",
  affected: "受影响",
  normal: "未见异常",
};

const DeviceNode = memo(function DeviceNode({ data, selected }: NodeProps<Node<DeviceData>>) {
  return (
    <div className={`business-node business-node--${data.state}${selected ? " is-selected" : ""}`}>
      <Handle type="target" position={Position.Left} className="business-handle" />
      <div className="business-node__icon">
        <Server size={17} aria-hidden />
      </div>
      <div className="business-node__body">
        <strong>{data.label}</strong>
        <span>{data.deviceType || "光网络设备"}</span>
      </div>
      {data.alarmCount > 0 && (
        <span className="business-node__alarm" aria-label={`${data.alarmCount} 条告警`}>
          <CircleAlert size={12} /> {data.alarmCount}
        </span>
      )}
      <span className="business-node__state">{STATE_LABEL[data.state]}</span>
      <Handle type="source" position={Position.Right} className="business-handle" />
    </div>
  );
});

const NODE_TYPES = { device: DeviceNode };

function deviceState(
  deviceId: string,
  result: DiagnosisResult | null,
  directDevices: Set<string>,
  alarmDevices: Set<string>,
): DeviceState {
  const root = "root_cause" in (result?.root_cause ?? {}) ? result?.root_cause.root_cause : "";
  if (root === `dev:${deviceId}`) return "root";
  if (directDevices.has(deviceId)) return "direct";
  if (alarmDevices.has(deviceId)) return "affected";
  return "normal";
}

function layout(devices: BusinessTopology["devices"]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const count = devices.length;
  const radiusX = Math.max(220, count * 54);
  const radiusY = Math.max(145, count * 25);
  devices.forEach((device, index) => {
    const angle = -Math.PI / 2 + (index / Math.max(count, 1)) * Math.PI * 2;
    positions.set(device.device_id, {
      x: radiusX + Math.cos(angle) * radiusX,
      y: radiusY + Math.sin(angle) * radiusY,
    });
  });
  return positions;
}

interface Props {
  topology: BusinessTopology;
  result: DiagnosisResult | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function BusinessTopologyView({ topology, result, selectedId, onSelect }: Props) {
  const alarmNodes = useMemo(
    () => result?.evidence_graph.nodes.filter((node) => node.type === "Alarm") ?? [],
    [result],
  );
  const alarmCountByDevice = useMemo(() => {
    const counts = new Map<string, number>();
    alarmNodes.forEach((alarm) => {
      if (alarm.device_id) counts.set(alarm.device_id, (counts.get(alarm.device_id) ?? 0) + 1);
    });
    return counts;
  }, [alarmNodes]);
  const alarmDevices = useMemo(() => new Set(alarmCountByDevice.keys()), [alarmCountByDevice]);
  const directDevices = useMemo(
    () =>
      new Set(
        alarmNodes
          .filter((alarm) => ["OTS_LOS", "OSC_LOS", "MUT_LOS"].includes(alarm.alarm_type ?? ""))
          .map((alarm) => alarm.device_id)
          .filter((id): id is string => Boolean(id)),
      ),
    [alarmNodes],
  );
  const portDevices = useMemo(
    () => new Map(topology.ports.map((port) => [port.port_id, port.device_id])),
    [topology.ports],
  );
  const positions = useMemo(() => layout(topology.devices), [topology.devices]);

  const nodes = useMemo<Node<DeviceData>[]>(
    () =>
      topology.devices.map((device) => ({
        id: `dev:${device.device_id}`,
        type: "device",
        position: positions.get(device.device_id) ?? { x: 0, y: 0 },
        selected: selectedId === `dev:${device.device_id}`,
        data: {
          label: device.device_id,
          deviceType: device.type,
          state: deviceState(device.device_id, result, directDevices, alarmDevices),
          alarmCount: alarmCountByDevice.get(device.device_id) ?? 0,
        },
      })),
    [alarmCountByDevice, alarmDevices, directDevices, positions, result, selectedId, topology.devices],
  );

  const edges = useMemo<Edge[]>(() => {
    const root = "root_cause" in (result?.root_cause ?? {}) ? result?.root_cause.root_cause : "";
    return topology.links.flatMap((link) => {
      const sourceDevice = portDevices.get(link.endpoint_a);
      const targetDevice = portDevices.get(link.endpoint_b);
      if (!sourceDevice || !targetDevice) return [];
      const isRoot = root === `link:${link.link_id}`;
      return [
        {
          id: `link:${link.link_id}`,
          source: `dev:${sourceDevice}`,
          target: `dev:${targetDevice}`,
          label: isRoot ? `${link.link_id} · 疑似故障` : link.link_id,
          markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
          className: isRoot ? "business-edge business-edge--root" : "business-edge",
          style: {
            stroke: isRoot ? "#c73542" : "#9aa9b8",
            strokeWidth: isRoot ? 3 : 1.6,
            strokeDasharray: link.inferred ? "6 5" : undefined,
          },
          labelStyle: { fill: isRoot ? "#a72834" : "#5f7082", fontSize: 11, fontWeight: 650 },
          labelBgStyle: { fill: "#ffffff", fillOpacity: 0.92 },
          data: { ...link },
        },
      ];
    });
  }, [portDevices, result, topology.links]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => onSelect(node.id),
    [onSelect],
  );
  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => onSelect(edge.id),
    [onSelect],
  );

  return (
    <div className="topology-canvas" data-testid="business-topology">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={() => onSelect(null)}
        fitView
        fitViewOptions={{ padding: 0.3, maxZoom: 1.18 }}
        minZoom={0.45}
        maxZoom={1.7}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#dde5ec" gap={24} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
      <div className="topology-legend" aria-label="拓扑状态图例">
        <span><i className="legend-dot root" />根因</span>
        <span><i className="legend-dot direct" />首发告警</span>
        <span><i className="legend-dot affected" />受影响</span>
        <span><i className="legend-dot normal" />未见异常</span>
        <span><i className="legend-line inferred" />推断链路</span>
      </div>
    </div>
  );
}
