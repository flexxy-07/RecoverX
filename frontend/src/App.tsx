import React, { useEffect, useState } from 'react';
import { collection, getDocs, query } from 'firebase/firestore';
import { db } from './lib/firebase';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Info,
  ShieldAlert,
  UserCog,
  X,
  Terminal,
  ChevronDown,
  ChevronUp,
  Brain,
  Shield,
  Zap,
  GitBranch,
  Clock,
} from 'lucide-react';

interface AuditEvent {
  node: string;
  event: string;
  timestamp?: string;
  [key: string]: any;
}

interface TransactionRecord {
  transaction_id: string;
  batch_run_id?: string;
  timestamp: any;
  outcome: string;
  guardrail_result: string;
  proposed_action: string;
  order_status?: string;
  diagnosis: {
    root_cause: string;
    confidence: number;
    explanation: string;
  };
  execution_result?: {
    action: string;
    status: string;
    payment_link_id?: string;
    short_url?: string;
    error?: string;
    note?: string;
  };
  audit_trail: AuditEvent[];
}

// ── Helpers ────────────────────────────────────────────────────────────────

const NODE_ICONS: Record<string, React.ReactNode> = {
  ingest: <GitBranch className="w-3.5 h-3.5" />,
  classify: <Brain className="w-3.5 h-3.5" />,
  decide: <Zap className="w-3.5 h-3.5" />,
  guardrails: <Shield className="w-3.5 h-3.5" />,
  order_status_check: <CheckCircle2 className="w-3.5 h-3.5" />,
  execute: <Activity className="w-3.5 h-3.5" />,
};

function getStatusBadge(outcome: string) {
  const base = "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-xs font-semibold tracking-wide uppercase border";
  switch (outcome) {
    case 'recovery_link_created':
      return <span className={`${base} bg-emerald-500/10 text-emerald-400 border-emerald-500/20`}><CheckCircle2 className="w-3 h-3" /> Recovered</span>;
    case 'retry_scheduled':
      return <span className={`${base} bg-blue-500/10 text-blue-400 border-blue-500/20`}><Activity className="w-3 h-3" /> Scheduled</span>;
    case 'customer_notified':
      return <span className={`${base} bg-blue-500/10 text-blue-400 border-blue-500/20`}><Info className="w-3 h-3" /> Notified</span>;
    case 'human_review':
    case 'recovery_link_failed':
      return <span className={`${base} bg-amber-500/10 text-amber-400 border-amber-500/20`}><UserCog className="w-3 h-3" /> Review</span>;
    case 'blocked':
      return <span className={`${base} bg-red-500/10 text-red-400 border-red-500/20`}><ShieldAlert className="w-3 h-3" /> Blocked</span>;
    default:
      return <span className={`${base} bg-zinc-800 text-zinc-400 border-zinc-700`}><AlertTriangle className="w-3 h-3" /> {outcome}</span>;
  }
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-400">{value.toFixed(2)}</span>
    </div>
  );
}

function EvidencePanel({ record, onClose }: { record: TransactionRecord; onClose: () => void }) {
  const diagnosis = (record.diagnosis || {}) as TransactionRecord['diagnosis'];
  const execution = (record.execution_result || {}) as NonNullable<TransactionRecord['execution_result']>;

  return (
    <div className="fixed inset-0 z-50 flex bg-black/75" onClick={onClose}>
      <div
        className="ml-auto w-full max-w-xl h-full bg-zinc-950 border-l border-zinc-800 overflow-y-auto flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 bg-zinc-950 border-b border-zinc-800">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-100">Evidence Panel</h3>
            <p className="text-xs font-mono text-zinc-500 mt-0.5">{record.transaction_id}</p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-100 transition-colors p-1.5 hover:bg-zinc-800 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 p-6 space-y-6">

          {/* Outcome Banner */}
          <div className="flex items-center justify-between p-4 bg-zinc-900 border border-zinc-800 rounded-sm">
            <span className="text-xs text-zinc-500 uppercase tracking-wider font-semibold">Final Outcome</span>
            {getStatusBadge(record.outcome)}
          </div>

          {/* Section 1 — Diagnosis */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-3.5 h-3.5 text-blue-400" />
              <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-400">AI Diagnosis</h4>
            </div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-sm p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-xs text-zinc-500 mb-1">Root Cause</p>
                  <p className="text-sm font-semibold text-zinc-100">{diagnosis.root_cause}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-zinc-500 mb-1">Confidence</p>
                  <ConfidenceBar value={diagnosis.confidence || 0} />
                </div>
              </div>
              {diagnosis.explanation && (
                <div>
                  <p className="text-xs text-zinc-500 mb-1">Reasoning</p>
                  <p className="text-sm text-zinc-300 leading-relaxed">{diagnosis.explanation}</p>
                </div>
              )}
            </div>
          </section>

          {/* Section 2 — Policy Decision */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Policy Decision</h4>
            </div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-sm p-4">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-xs text-zinc-500 mb-1">Proposed Action</p>
                  <p className="text-sm font-mono font-semibold text-zinc-100">{record.proposed_action || 'N/A'}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-zinc-500 mb-1">Guardrail</p>
                  <span className={`text-xs font-bold uppercase tracking-wider ${record.guardrail_result === 'BLOCKED' ? 'text-red-400' : 'text-emerald-400'}`}>
                    {record.guardrail_result || 'N/A'}
                  </span>
                </div>
              </div>
              {record.order_status && (
                <div className="mt-3 pt-3 border-t border-zinc-800">
                  <p className="text-xs text-zinc-500 mb-1">Order Status at Execution</p>
                  <p className="text-sm font-mono text-zinc-100">{record.order_status}</p>
                </div>
              )}
            </div>
          </section>

          {/* Section 3 — Execution Result */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Execution Result</h4>
            </div>
            <div className="bg-zinc-900 border border-zinc-800 rounded-sm p-4 space-y-2">
              <div className="flex justify-between">
                <p className="text-xs text-zinc-500">Status</p>
                <p className="text-xs font-mono text-zinc-100">{execution.status || 'N/A'}</p>
              </div>
              {execution.short_url && (
                <div className="flex justify-between items-center">
                  <p className="text-xs text-zinc-500">Recovery URL</p>
                  <a href={execution.short_url} target="_blank" rel="noopener noreferrer"
                    className="text-xs font-mono text-blue-400 hover:text-blue-300 underline underline-offset-2 truncate max-w-[200px]">
                    {execution.short_url}
                  </a>
                </div>
              )}
              {execution.error && (
                <div className="mt-2 p-3 bg-red-950/30 border border-red-900/40 rounded-sm">
                  <p className="text-xs text-red-400 font-mono leading-relaxed">{execution.error}</p>
                </div>
              )}
              {execution.note && (
                <p className="text-xs text-zinc-500 italic">{execution.note}</p>
              )}
            </div>
          </section>

          {/* Section 4 — Audit Timeline */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Terminal className="w-3.5 h-3.5 text-zinc-400" />
              <h4 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Step Timeline</h4>
            </div>
            <div className="space-y-0">
              {record.audit_trail?.map((step, idx) => (
                <div key={idx} className="relative pl-6">
                  {/* Timeline line */}
                  {idx < record.audit_trail.length - 1 && (
                    <div className="absolute left-[7px] top-5 bottom-0 w-px bg-zinc-800" />
                  )}
                  {/* Dot */}
                  <div className="absolute left-[3px] top-[14px] w-2 h-2 rounded-full bg-zinc-700 border border-zinc-600" />

                  <div className="py-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-zinc-400">{NODE_ICONS[step.node] || <Terminal className="w-3.5 h-3.5" />}</span>
                      <span className="text-xs font-bold text-zinc-200 uppercase tracking-wide">{step.node}</span>
                      <span className="text-xs text-zinc-600">/</span>
                      <span className="text-xs text-zinc-500">{step.event}</span>
                      {step.timestamp && (
                        <span className="ml-auto text-xs font-mono text-zinc-600 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(step.timestamp).toLocaleTimeString()}
                        </span>
                      )}
                    </div>
                    {/* Key fields */}
                    <div className="bg-zinc-900 border border-zinc-800 rounded-sm p-2.5 space-y-1 font-mono text-xs">
                      {Object.entries(step)
                        .filter(([k]) => !['node', 'event', 'timestamp', 'result'].includes(k))
                        .map(([k, v]) => (
                          <div key={k} className="flex gap-2">
                            <span className="text-zinc-600 shrink-0">{k}:</span>
                            <span className="text-zinc-300 break-all">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                          </div>
                        ))}
                      {step.result && (
                        <div className="pt-1 mt-1 border-t border-zinc-800">
                          {Object.entries(step.result).map(([k, v]) => (
                            <div key={k} className="flex gap-2">
                              <span className="text-zinc-600 shrink-0">result.{k}:</span>
                              <span className="text-zinc-300 break-all">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────

function App() {
  const [records, setRecords] = useState<TransactionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<TransactionRecord | null>(null);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const snapshot = await getDocs(query(collection(db, 'recovery_runs')));
        const data = snapshot.docs.map(doc => doc.data() as TransactionRecord);
        data.sort((a, b) => a.transaction_id.localeCompare(b.transaction_id));
        setRecords(data);
      } catch (err: any) {
        setError(err.message || "Failed to load records");
      } finally {
        setLoading(false);
      }
    };
    fetchRecords();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-zinc-950">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-sm tracking-tight">
          <Activity className="animate-spin w-4 h-4 text-blue-500" />
          LOADING_RECOVERX_SYSTEM...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 bg-zinc-950 text-zinc-100">
        <ShieldAlert className="w-10 h-10 text-red-500" />
        <p className="text-sm text-zinc-400 max-w-md text-center">{error}</p>
      </div>
    );
  }

  const total = records.length;
  const recovered = records.filter(r => r.outcome === 'recovery_link_created').length;
  const notified = records.filter(r => r.outcome === 'customer_notified').length;
  const humanReview = records.filter(r => r.outcome === 'human_review' || r.outcome === 'recovery_link_failed').length;
  const blocked = records.filter(r => r.outcome === 'blocked').length;

  const metrics = [
    { label: 'Total Processed', value: total, color: 'text-zinc-100' },
    { label: 'Auto-Recovered', value: recovered, color: 'text-emerald-400' },
    { label: 'Customer Notified', value: notified, color: 'text-blue-400' },
    { label: 'Human Review', value: humanReview, color: 'text-amber-400' },
    { label: 'Blocked / Risk', value: blocked, color: 'text-red-400' },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      <div className="max-w-7xl mx-auto p-6 lg:p-10">

        {/* Header */}
        <header className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-10 border-b border-zinc-800 pb-6">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] uppercase text-zinc-500 mb-1">Revenue Recovery</p>
            <h1 className="text-2xl font-bold tracking-tight">RecoverX</h1>
          </div>
          <div className="mt-4 sm:mt-0 text-xs font-mono text-zinc-600 bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-sm">
            BATCH: {records[0]?.batch_run_id?.substring(0, 8) ?? 'N/A'}
          </div>
        </header>

        {/* Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-10">
          {metrics.map(m => (
            <div key={m.label} className="bg-zinc-900 border border-zinc-800 rounded-sm p-4 flex flex-col gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">{m.label}</span>
              <span className={`text-3xl font-bold tracking-tight ${m.color}`}>{m.value}</span>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-sm overflow-hidden">
          <div className="px-6 py-3.5 border-b border-zinc-800 flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Transaction Output Log</h2>
            <span className="text-xs text-zinc-600">{total} records · click row to inspect</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-zinc-500 bg-zinc-950/50">
                  <th className="px-6 py-3 font-medium border-b border-zinc-800">ID</th>
                  <th className="px-6 py-3 font-medium border-b border-zinc-800">Root Cause</th>
                  <th className="px-6 py-3 font-medium border-b border-zinc-800">Confidence</th>
                  <th className="px-6 py-3 font-medium border-b border-zinc-800">Action</th>
                  <th className="px-6 py-3 font-medium border-b border-zinc-800">Outcome</th>
                  <th className="px-6 py-3 font-medium border-b border-zinc-800"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {records.map((record) => (
                  <tr
                    key={record.transaction_id}
                    className="hover:bg-zinc-800/30 transition-colors cursor-pointer"
                    onClick={() => setSelectedRecord(record)}
                  >
                    <td className="px-6 py-3.5 font-mono text-xs text-zinc-400">{record.transaction_id}</td>
                    <td className="px-6 py-3.5 text-zinc-200 font-medium">{record.diagnosis?.root_cause ?? 'unknown'}</td>
                    <td className="px-6 py-3.5">
                      <ConfidenceBar value={record.diagnosis?.confidence ?? 0} />
                    </td>
                    <td className="px-6 py-3.5 font-mono text-xs text-zinc-400">{record.proposed_action ?? 'N/A'}</td>
                    <td className="px-6 py-3.5">{getStatusBadge(record.outcome)}</td>
                    <td className="px-6 py-3.5 text-zinc-600">
                      <Info className="w-3.5 h-3.5" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Evidence Panel (slide-in) */}
      {selectedRecord && (
        <EvidencePanel record={selectedRecord} onClose={() => setSelectedRecord(null)} />
      )}
    </div>
  );
}

export default App;
