import { useEffect, useState } from 'react';
import { collection, getDocs, query } from 'firebase/firestore';
import { db } from './lib/firebase';
import { Activity, AlertTriangle, CheckCircle2, Info, ShieldAlert, UserCog, X, Terminal } from 'lucide-react';

interface TransactionRecord {
  transaction_id: string;
  batch_run_id?: string;
  timestamp: string;
  outcome: string;
  guardrail_result: string;
  proposed_action: string;
  diagnosis: {
    root_cause: string;
    confidence: number;
    explanation: string;
  };
  audit_trail: any[];
}

function App() {
  const [records, setRecords] = useState<TransactionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<TransactionRecord | null>(null);

  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const q = query(collection(db, 'recovery_runs'));
        const snapshot = await getDocs(q);
        const data = snapshot.docs.map(doc => doc.data() as TransactionRecord);
        data.sort((a, b) => a.transaction_id.localeCompare(b.transaction_id));
        setRecords(data);
      } catch (err: any) {
        console.error("Error fetching records:", err);
        setError(err.message || "Failed to load records from Firestore");
      } finally {
        setLoading(false);
      }
    };

    fetchRecords();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#09090b]">
        <div className="flex items-center gap-3 text-[#a1a1aa] font-mono text-sm tracking-tight">
          <Activity className="animate-spin w-4 h-4 text-[#2563eb]" />
          LOADING_RECOVERX_SYSTEM...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 bg-[#09090b] text-[#f4f4f5]">
        <ShieldAlert className="w-12 h-12 text-[#ef4444]" />
        <h2 className="text-xl font-bold tracking-tight">Connection Failed</h2>
        <p className="text-[#a1a1aa] text-center max-w-md text-sm leading-relaxed">
          {error}<br/><br/>
          Check Firebase Web App config in <code className="bg-[#18181b] px-1.5 py-0.5 rounded border border-[#27272a] font-mono">.env</code>.
        </p>
      </div>
    );
  }

  const total = records.length;
  const recovered = records.filter(r => r.outcome === 'recovery_link_created').length;
  const notified = records.filter(r => r.outcome === 'customer_notified').length;
  const humanReview = records.filter(r => r.outcome === 'human_review' || r.outcome === 'recovery_link_failed').length;
  const blocked = records.filter(r => r.outcome === 'blocked').length;

  const getStatusBadge = (outcome: string) => {
    const baseClasses = "inline-flex items-center px-2 py-1 rounded-sm text-xs font-medium tracking-wide uppercase border";
    switch (outcome) {
      case 'recovery_link_created':
        return <span className={`${baseClasses} bg-[#10b981]/10 text-[#10b981] border-[#10b981]/20`}><CheckCircle2 className="w-3 h-3 mr-1.5"/> Recovered</span>;
      case 'retry_scheduled':
        return <span className={`${baseClasses} bg-[#3b82f6]/10 text-[#3b82f6] border-[#3b82f6]/20`}><Activity className="w-3 h-3 mr-1.5"/> Scheduled</span>;
      case 'customer_notified':
        return <span className={`${baseClasses} bg-[#3b82f6]/10 text-[#3b82f6] border-[#3b82f6]/20`}><Info className="w-3 h-3 mr-1.5"/> Notified</span>;
      case 'human_review':
      case 'recovery_link_failed':
        return <span className={`${baseClasses} bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/20`}><UserCog className="w-3 h-3 mr-1.5"/> Review</span>;
      case 'blocked':
        return <span className={`${baseClasses} bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/20`}><ShieldAlert className="w-3 h-3 mr-1.5"/> Blocked</span>;
      default:
        return <span className={`${baseClasses} bg-[#27272a] text-[#a1a1aa] border-[#27272a]`}><AlertTriangle className="w-3 h-3 mr-1.5"/> {outcome}</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-[#f4f4f5] p-6 lg:p-12 font-sans">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <header className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-12 border-b border-[#27272a] pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight mb-1">RecoverX</h1>
            <p className="text-sm text-[#a1a1aa] font-medium tracking-wide uppercase">Revenue Recovery Ledger</p>
          </div>
          <div className="mt-4 sm:mt-0 flex items-center gap-3">
            <span className="text-xs text-[#a1a1aa] font-mono bg-[#18181b] border border-[#27272a] px-3 py-1.5 rounded-sm">
              BATCH: {records[0]?.batch_run_id?.substring(0,8) || 'N/A'}
            </span>
          </div>
        </header>

        {/* Metrics Grid */}
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-12">
          {[
            { label: 'Total Processed', value: total, color: 'text-[#f4f4f5]' },
            { label: 'Auto-Recovered', value: recovered, color: 'text-[#10b981]' },
            { label: 'Customer Notified', value: notified, color: 'text-[#3b82f6]' },
            { label: 'Human Review', value: humanReview, color: 'text-[#f59e0b]' },
            { label: 'Blocked / Risk', value: blocked, color: 'text-[#ef4444]' },
          ].map((metric) => (
            <div key={metric.label} className="bg-[#18181b] border border-[#27272a] p-5 rounded-sm flex flex-col justify-between h-28">
              <span className="text-xs font-semibold tracking-wider text-[#a1a1aa] uppercase">{metric.label}</span>
              <span className={`text-3xl font-bold tracking-tight ${metric.color}`}>{metric.value}</span>
            </div>
          ))}
        </section>

        {/* Ledger Table */}
        <section className="bg-[#18181b] border border-[#27272a] rounded-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-[#27272a] bg-[#18181b]">
            <h2 className="text-sm font-semibold tracking-wide uppercase text-[#f4f4f5]">Transaction Output Log</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-[#09090b] text-[#a1a1aa] text-xs uppercase tracking-wider">
                  <th className="px-6 py-3 font-medium border-b border-[#27272a]">Transaction ID</th>
                  <th className="px-6 py-3 font-medium border-b border-[#27272a]">Root Cause (AI)</th>
                  <th className="px-6 py-3 font-medium border-b border-[#27272a]">Confidence</th>
                  <th className="px-6 py-3 font-medium border-b border-[#27272a]">Proposed Action</th>
                  <th className="px-6 py-3 font-medium border-b border-[#27272a]">Final Outcome</th>
                </tr>
              </thead>
              <tbody className="text-sm divide-y divide-[#27272a]">
                {records.map((record) => (
                  <tr 
                    key={record.transaction_id} 
                    className="hover:bg-[#27272a]/30 transition-colors cursor-pointer"
                    onClick={() => setSelectedRecord(record)}
                  >
                    <td className="px-6 py-4 font-mono text-xs text-[#a1a1aa]">{record.transaction_id}</td>
                    <td className="px-6 py-4 font-medium">{record.diagnosis?.root_cause || 'unknown'}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-1 bg-[#27272a] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-[#2563eb]" 
                            style={{ width: `${(record.diagnosis?.confidence || 0) * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-[#a1a1aa]">{(record.diagnosis?.confidence || 0).toFixed(2)}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs text-[#a1a1aa]">{record.proposed_action || 'N/A'}</td>
                    <td className="px-6 py-4">{getStatusBadge(record.outcome)}</td>
                  </tr>
                ))}
                {records.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-[#a1a1aa] text-sm">
                      No records found in Firestore. Run the batch script.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Audit Trail Modal */}
        {selectedRecord && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80" onClick={() => setSelectedRecord(null)}>
            <div className="bg-[#09090b] border border-[#27272a] w-full max-w-3xl max-h-[85vh] rounded-sm flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
              
              <div className="flex items-center justify-between px-6 py-4 border-b border-[#27272a] bg-[#18181b]">
                <div className="flex items-center gap-3">
                  <Terminal className="w-4 h-4 text-[#2563eb]" />
                  <h3 className="text-sm font-semibold tracking-wide uppercase">Audit Trail</h3>
                  <span className="text-xs font-mono text-[#a1a1aa] bg-[#09090b] px-2 py-1 rounded-sm border border-[#27272a] ml-2">
                    {selectedRecord.transaction_id}
                  </span>
                </div>
                <button 
                  className="text-[#a1a1aa] hover:text-[#f4f4f5] transition-colors p-1"
                  onClick={() => setSelectedRecord(null)}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              
              <div className="p-6 overflow-y-auto font-mono text-xs text-[#a1a1aa] space-y-6">
                {selectedRecord.audit_trail?.map((step, idx) => (
                  <div key={idx} className="relative pl-6">
                    <div className="absolute left-0 top-1.5 w-1.5 h-1.5 bg-[#2563eb] rounded-full ring-4 ring-[#09090b]"></div>
                    {idx !== selectedRecord.audit_trail.length - 1 && (
                      <div className="absolute left-[2px] top-4 bottom-[-1.5rem] w-px bg-[#27272a]"></div>
                    )}
                    
                    <div className="font-semibold text-[#f4f4f5] mb-2 uppercase tracking-wide flex items-center gap-2">
                      <span className="text-[#2563eb]">{step.node}</span>
                      <span className="text-[#a1a1aa]/50">/</span>
                      <span className="text-[#a1a1aa]">{step.event}</span>
                    </div>
                    
                    <pre className="bg-[#18181b] border border-[#27272a] p-4 rounded-sm overflow-x-auto whitespace-pre-wrap leading-relaxed">
                      {JSON.stringify(step, null, 2)}
                    </pre>
                  </div>
                ))}
                {(!selectedRecord.audit_trail || selectedRecord.audit_trail.length === 0) && (
                  <div className="italic text-center py-8">No audit events found.</div>
                )}
              </div>
              
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
