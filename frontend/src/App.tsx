import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  ChevronLeft,
  FileSpreadsheet,
  RotateCcw,
  StopCircle,
} from "lucide-react";
import { BusinessTopologyView } from "./components/BusinessTopology";
import { InputPanel } from "./components/InputPanel";
import { ResultPanel } from "./components/ResultPanel";
import { StageRail } from "./components/StageRail";
import {
  cancelDiagnosis,
  fetchDiagnosis,
  fetchDiagnosisEvents,
  loadDemoExample,
  preflightSample,
  startDiagnosis,
  submitReview,
  subscribeToDiagnosis,
} from "./lib/api";
import type {
  BusinessTopology,
  DemoExample,
  DiagnosisEvent,
  DiagnosisResult,
  DiagnosisSession,
  PreflightResult,
  ReviewState,
  WorkbenchStatus,
} from "./lib/types";

const SESSION_KEY = "optirca.active-session";

function emptyReview(): ReviewState {
  return { status: "unreviewed" };
}

function statusFromSession(session: DiagnosisSession): WorkbenchStatus {
  return session.status === "running" ? "running" : session.status;
}

function topologyFrom(result: DiagnosisResult | null, preflight: PreflightResult | null): BusinessTopology | null {
  return result?.input.topology ?? preflight?.topology ?? null;
}

export function App() {
  const [alarmFile, setAlarmFile] = useState<File | null>(null);
  const [topologyFile, setTopologyFile] = useState<File | null>(null);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [status, setStatus] = useState<WorkbenchStatus>("idle");
  const [session, setSession] = useState<DiagnosisSession | null>(null);
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [review, setReview] = useState<ReviewState>(emptyReview);
  const [events, setEvents] = useState<DiagnosisEvent[]>([]);
  const [displayEvents, setDisplayEvents] = useState<DiagnosisEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoExample | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replaying, setReplaying] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const preflightRequest = useRef(0);

  const runPreflight = useCallback(async (csv: File, topology: File | null) => {
    const requestId = ++preflightRequest.current;
    setStatus("preflighting");
    setError(null);
    setPreflight(null);
    try {
      const next = await preflightSample(csv, topology);
      if (requestId !== preflightRequest.current) return;
      setPreflight(next);
      setStatus(next.status);
    } catch (nextError) {
      if (requestId !== preflightRequest.current) return;
      setStatus("error");
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }, []);

  const handleAlarmFile = useCallback(
    (file: File | null) => {
      setAlarmFile(file);
      setDemo(null);
      if (file) void runPreflight(file, topologyFile);
      else {
        setPreflight(null);
        setStatus("idle");
      }
    },
    [runPreflight, topologyFile],
  );

  const handleTopologyFile = useCallback(
    (file: File | null) => {
      setTopologyFile(file);
      setDemo(null);
      if (alarmFile) void runPreflight(alarmFile, file);
    },
    [alarmFile, runPreflight],
  );

  const handleDemo = useCallback(async () => {
    setStatus("preflighting");
    setError(null);
    try {
      const example = await loadDemoExample();
      const csv = new File([example.alarm_content], example.alarm_filename, { type: "text/csv" });
      const topology = new File([JSON.stringify(example.topology)], example.topology_filename, {
        type: "application/json",
      });
      setDemo(example);
      setAlarmFile(csv);
      setTopologyFile(topology);
      await runPreflight(csv, topology);
    } catch (nextError) {
      setStatus("error");
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }, [runPreflight]);

  const applyEvent = useCallback((event: DiagnosisEvent) => {
    setEvents((current) => [...current, event]);
    setDisplayEvents((current) => [...current, event]);
    if (event.type === "diagnosis.completed" || event.type === "diagnosis.degraded") {
      setResult(event.result);
      setStatus(event.result.status);
      setSession((current) => current ? { ...current, status: event.result.status, result: event.result } : current);
      localStorage.setItem(SESSION_KEY, event.result.session_id);
    } else if (event.type === "diagnosis.cancelled") {
      setStatus("cancelled");
      setSession((current) => current ? { ...current, status: "cancelled" } : current);
      localStorage.removeItem(SESSION_KEY);
    }
  }, []);

  useEffect(() => {
    if (!session || session.status !== "running") return;
    const close = subscribeToDiagnosis(
      session.session_id,
      applyEvent,
      () => {
        void fetchDiagnosis(session.session_id).then((recovered) => {
          setSession(recovered);
          setReview(recovered.review ?? emptyReview());
          if (recovered.result) setResult(recovered.result);
          setStatus(statusFromSession(recovered));
        });
      },
    );
    return close;
  }, [applyEvent, session]);

  useEffect(() => {
    const savedSession = localStorage.getItem(SESSION_KEY);
    if (!savedSession) return;
    void fetchDiagnosis(savedSession)
      .then(async (recovered) => {
        setSession(recovered);
        setReview(recovered.review ?? emptyReview());
        if (recovered.result) setResult(recovered.result);
        setStatus(statusFromSession(recovered));
        if (recovered.status !== "running") {
          const persistedEvents = await fetchDiagnosisEvents(savedSession);
          setEvents(persistedEvents);
          setDisplayEvents(persistedEvents);
        }
      })
      .catch(() => localStorage.removeItem(SESSION_KEY));
  }, []);

  useEffect(() => {
    if (status !== "running") return;
    const started = performance.now();
    const timer = window.setInterval(() => setElapsedSeconds((performance.now() - started) / 1000), 200);
    return () => window.clearInterval(timer);
  }, [status]);

  const handleStart = useCallback(async () => {
    if (!preflight || preflight.status !== "ready" || status === "running") return;
    setError(null);
    setEvents([]);
    setDisplayEvents([]);
    setResult(null);
    setReview(emptyReview());
    setElapsedSeconds(0);
    try {
      const created = await startDiagnosis(preflight.preflight_id);
      setSession(created);
      setStatus("running");
      localStorage.setItem(SESSION_KEY, created.session_id);
    } catch (nextError) {
      setStatus("error");
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }, [preflight, status]);

  const handleCancel = useCallback(async () => {
    if (!session) return;
    try {
      await cancelDiagnosis(session.session_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    }
  }, [session]);

  const handleReview = useCallback(
    async (
      decision: "confirmed" | "corrected" | "expert_review_requested",
      notes: string,
      rootCause?: string,
    ) => {
      if (!session) return;
      const response = await submitReview(session.session_id, decision, notes, rootCause);
      setReview(response.review);
    },
    [session],
  );

  const handleReplay = useCallback(() => {
    if (!events.length || replaying) return;
    setReplaying(true);
    setDisplayEvents([]);
    let index = 0;
    const timer = window.setInterval(() => {
      index += 1;
      setDisplayEvents(events.slice(0, index));
      if (index >= events.length) {
        window.clearInterval(timer);
        setReplaying(false);
      }
    }, 220);
  }, [events, replaying]);

  const handleNewSample = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    setAlarmFile(null);
    setTopologyFile(null);
    setPreflight(null);
    setStatus("idle");
    setSession(null);
    setResult(null);
    setReview(emptyReview());
    setEvents([]);
    setDisplayEvents([]);
    setDemo(null);
    setError(null);
  }, []);

  const topology = useMemo(() => topologyFrom(result, preflight), [preflight, result]);
  const showingRun = status === "running" || Boolean(result);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand__mark"><Activity size={20} /></span>
          <div><strong>OptiRCA Lite</strong><span>光网络告警根因诊断工作台</span></div>
        </div>
        <div className="header-status">
          <span className="system-dot" /> 本地推理服务已连接
          {showingRun && (
            <button type="button" onClick={handleNewSample}><RotateCcw size={14} /> 新诊断</button>
          )}
        </div>
      </header>

      {!showingRun ? (
        <InputPanel
          alarmFile={alarmFile}
          topologyFile={topologyFile}
          status={status}
          preflight={preflight}
          onAlarmFile={handleAlarmFile}
          onTopologyFile={handleTopologyFile}
          onLoadDemo={handleDemo}
          onStart={handleStart}
        />
      ) : (
        <div className="workbench">
          <div className="run-header">
            <div>
              <button type="button" className="back-button" onClick={handleNewSample}><ChevronLeft size={15} /> 新样本</button>
              <span className="run-file"><FileSpreadsheet size={15} /> {alarmFile?.name ?? result?.input.filename ?? "已恢复的诊断样本"}</span>
              {topology && (
                <span className={`topology-source ${topology.source}`}>
                  {topology.source === "provided" ? "权威拓扑" : `推断拓扑 ${Math.round(topology.confidence * 100)}%`}
                </span>
              )}
            </div>
            {status === "running" && (
              <div className="running-state">
                <span>诊断运行中 · {elapsedSeconds.toFixed(1)}s</span>
                <button type="button" onClick={handleCancel}><StopCircle size={15} /> 取消诊断</button>
              </div>
            )}
          </div>

          <StageRail events={displayEvents} running={status === "running"} replaying={replaying} onReplay={handleReplay} />

          <div className={`workbench-grid${result ? " has-result" : ""}`}>
            <section className="topology-panel">
              <div className="panel-heading">
                <div><span className="eyebrow">BUSINESS TOPOLOGY</span><h1>业务拓扑与告警传播</h1></div>
                {preflight && <span>{preflight.sample_summary.alarm_count} 条告警 · {preflight.sample_summary.device_count} 台异常设备</span>}
              </div>
              {topology && (
                <BusinessTopologyView
                  key={result ? "result-layout" : "running-layout"}
                  topology={topology}
                  result={result}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              )}
              {status === "running" && (
                <div className="run-overlay-note">
                  <span className="scan-line" />
                  <strong>正在依据真实 Agent 事件更新诊断</strong>
                  <span>{displayEvents[displayEvents.length - 1]?.type ?? "diagnosis.started"}</span>
                </div>
              )}
            </section>

            {result && (
              <ResultPanel
                result={result}
                events={displayEvents}
                review={review}
                demoExpectedRoot={demo?.expected.root_cause}
                onReview={handleReview}
              />
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="toast-error" role="alert"><AlertCircle size={17} /><span>{error}</span></div>
      )}
    </div>
  );
}
