"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { fetchMgmtGraph, type MgmtFlowGraph } from "@/lib/management";

function MgmtNode({ data }: { data: { label: string; status: string; stale: boolean; entityType: string } }) {
  const tone = data.stale ? "stale" : data.status;
  return (
    <div className={`mgmt-flow-node mgmt-flow-${data.entityType} mgmt-flow-status-${tone}`}>
      <div className="mgmt-flow-node-type">{data.entityType}</div>
      <div className="mgmt-flow-node-label">{data.label}</div>
    </div>
  );
}

const nodeTypes = { mgmtNode: MgmtNode };

export function ManagementMap() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const graph: MgmtFlowGraph = await fetchMgmtGraph();
      setNodes(graph.nodes as Node[]);
      setEdges(
        graph.edges.map((e) => ({
          ...e,
          type: "smoothstep",
          label: e.label,
        })) as Edge[]
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки карты");
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <p className="muted">Загрузка карты…</p>;
  if (err) return <p className="warn">{err}</p>;

  return (
    <div className="mgmt-flow-wrap">
      {nodes.length === 0 ? (
        <p className="muted mgmt-flow-empty">
          Пока пусто. Добавьте цели и задачи в режиме «Эксперт» или пройдите мастер (U2).
        </p>
      ) : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <MiniMap />
        <Controls />
        <Background gap={16} />
      </ReactFlow>
      <button type="button" className="btn-secondary mgmt-reload" onClick={() => void load()}>
        Обновить карту
      </button>
    </div>
  );
}
