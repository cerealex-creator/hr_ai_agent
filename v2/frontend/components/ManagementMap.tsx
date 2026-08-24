"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type OnNodeDrag,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  approveMgmtGate,
  fetchMgmtGateSummary,
  fetchMgmtGraph,
  rejectMgmtGate,
  saveMgmtGraphLayout,
  type MgmtFlowGraph,
  type MgmtGateSummary,
} from "@/lib/management";

type NodeData = {
  label: string;
  status: string;
  stale: boolean;
  entityType: string;
  entityId: string;
};

function MgmtNode({ data }: { data: NodeData }) {
  const tone = data.stale ? "stale" : data.status;
  return (
    <div className={`mgmt-flow-node mgmt-flow-${data.entityType} mgmt-flow-status-${tone}`}>
      <div className="mgmt-flow-node-type">{data.entityType}</div>
      <div className="mgmt-flow-node-label">{data.label}</div>
      <div className="mgmt-flow-node-status">{data.status}</div>
    </div>
  );
}

const nodeTypes = { mgmtNode: MgmtNode };

const GATEABLE = new Set(["goal", "task", "process_map", "role", "process_step"]);
const REJECTABLE = new Set(["goal", "task"]);

export function ManagementMap() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [gateMode, setGateMode] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<NodeData | null>(null);
  const [summary, setSummary] = useState<MgmtGateSummary | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [graph, gates]: [MgmtFlowGraph, MgmtGateSummary] = await Promise.all([
        fetchMgmtGraph(),
        fetchMgmtGateSummary(),
      ]);
      setNodes(graph.nodes as Node[]);
      setEdges(
        graph.edges.map((e) => ({
          ...e,
          type: "smoothstep",
          label: e.label,
        })) as Edge[]
      );
      setSummary(gates);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка загрузки карты");
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    void load();
  }, [load]);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const data = node.data as NodeData;
      if (!GATEABLE.has(data.entityType)) {
        setSelected(null);
        return;
      }
      setSelected(data);
      setMsg(null);
      setErr(null);
    },
    []
  );

  const onNodeDragStop: OnNodeDrag = useCallback(async (_event, node) => {
    const data = node.data as NodeData;
    if (!data?.entityType || !data?.entityId) return;
    try {
      await saveMgmtGraphLayout([
        {
          node_type: data.entityType,
          node_id: data.entityId,
          x: node.position.x,
          y: node.position.y,
        },
      ]);
      setMsg("Позиция узла сохранена");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось сохранить раскладку");
    }
  }, []);

  async function onApprove() {
    if (!selected) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await approveMgmtGate(selected.entityType, selected.entityId);
      setMsg(`Утверждено: ${selected.label}`);
      setSelected(null);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка утверждения");
    } finally {
      setBusy(false);
    }
  }

  async function onReject() {
    if (!selected || !REJECTABLE.has(selected.entityType)) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await rejectMgmtGate(selected.entityType, selected.entityId);
      setMsg(`Отклонено: ${selected.label}`);
      setSelected(null);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Ошибка отклонения");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="muted">Загрузка карты…</p>;

  const canApprove =
    selected &&
    GATEABLE.has(selected.entityType) &&
    (selected.status === "draft" || selected.status === "suggested");
  const canReject =
    selected && REJECTABLE.has(selected.entityType) && (selected.status === "draft" || selected.status === "suggested");

  return (
    <div className="mgmt-flow-wrap">
      <div className="mgmt-gate-bar">
        <label className="mgmt-gate-toggle">
          <input type="checkbox" checked={gateMode} onChange={(e) => setGateMode(e.target.checked)} />
          Режим ворот (клик по узлу → утвердить). Перетащите узел — позиция сохранится.
        </label>
        {summary ? (
          <span className="muted mgmt-gate-counts">
            ждут: L0 {summary.l0_pending} · L1 {summary.l1_pending} · L2a {summary.l2a_pending} · L2b{" "}
            {summary.l2b_pending}
            {summary.suggested_goals ? ` · suggested ${summary.suggested_goals}` : ""}
          </span>
        ) : null}
      </div>
      {err ? <p className="warn">{err}</p> : null}
      {msg ? <p className="ok">{msg}</p> : null}
      {nodes.length === 0 ? (
        <p className="muted mgmt-flow-empty">
          Пока пусто. Добавьте цели и задачи в режиме «Эксперт» или пройдите мастер.
        </p>
      ) : null}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={gateMode ? onNodeClick : undefined}
        onNodeDragStop={onNodeDragStop}
        nodesDraggable
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <MiniMap />
        <Controls />
        <Background gap={16} />
      </ReactFlow>
      {selected ? (
        <aside className="mgmt-gate-panel">
          <h3>{selected.label}</h3>
          <p className="muted">
            {selected.entityType} · {selected.status}
          </p>
          <div className="mgmt-form-row">
            <button type="button" disabled={busy || !canApprove} onClick={() => void onApprove()}>
              Утвердить
            </button>
            {REJECTABLE.has(selected.entityType) ? (
              <button
                type="button"
                className="mgmt-btn-secondary"
                disabled={busy || !canReject}
                onClick={() => void onReject()}
              >
                Отклонить
              </button>
            ) : null}
            <button type="button" className="mgmt-btn-secondary" disabled={busy} onClick={() => setSelected(null)}>
              Закрыть
            </button>
          </div>
          {selected.entityType === "process_map" ? (
            <p className="muted" style={{ marginTop: 8, fontSize: "0.85rem" }}>
              L2a: все шаги процесса должны иметь роль, иначе утверждение заблокируется.
            </p>
          ) : null}
        </aside>
      ) : null}
      <button type="button" className="btn-secondary mgmt-reload" onClick={() => void load()}>
        Обновить карту
      </button>
    </div>
  );
}
