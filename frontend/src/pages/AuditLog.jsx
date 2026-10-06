import React, { useState, useEffect } from 'react';
import { getAuditLogs, verifyAuditChain } from '../api/auditApi';
import { ShieldCheck, ShieldAlert, Search, Link as LinkIcon, Clock, User, FileText, Database } from 'lucide-react';
import Card from '../components/common/Card';

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [selectedLog, setSelectedLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verification, setVerification] = useState(null);
  const [error, setError] = useState(null);

  // Filters
  const [filters, setFilters] = useState({
    action: '',
    request_id: '',
    user_id: ''
  });

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [logsData, verifyData] = await Promise.all([
        getAuditLogs(filters),
        verifyAuditChain()
      ]);
      
      setLogs(logsData);
      setVerification(verifyData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [filters]);

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({ ...prev, [field]: value }));
  };

  const truncateHash = (hash) => {
    if (!hash) return 'N/A';
    if (hash === 'GENESIS') return 'GENESIS';
    return `${hash.substring(0, 8)}...${hash.substring(hash.length - 8)}`;
  };

  const inputClass = "w-full pl-9 bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-text-main placeholder-text-muted/50 focus:outline-none focus:border-primary";
  const inputClassNoIcon = "w-full bg-navy-bg border border-navy-border rounded-md px-3 py-2 text-text-main placeholder-text-muted/50 focus:outline-none focus:border-primary";

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-end mb-2">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Database className="h-8 w-8 text-secondary" />
            <h1 className="text-2xl font-bold text-text-main">Audit Log</h1>
          </div>
          <p className="text-sm text-text-muted max-w-2xl">
            TrustGuard maintains a tamper-evident audit chain. Each event is linked to the previous event using cryptographic hashing. This log is read-only and immutable.
          </p>
        </div>
        
        {/* Integrity Badge */}
        {verification && (
          <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-sm ${verification.valid ? 'bg-success/10 border-success/30 text-success' : 'bg-danger/10 border-danger/30 text-danger'}`}>
            {verification.valid ? (
              <>
                <ShieldCheck className="h-6 w-6" />
                <div>
                  <div className="font-bold text-sm">Audit Chain Verified</div>
                  <div className="text-xs opacity-80">{verification.records_checked} records checked</div>
                </div>
              </>
            ) : (
              <>
                <ShieldAlert className="h-6 w-6" />
                <div>
                  <div className="font-bold text-sm">Integrity Check Failed</div>
                  <div className="text-xs opacity-80">Corrupted ID: {verification.corrupted_id}</div>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-danger/10 text-danger rounded-md border border-danger/20">
          {error}
        </div>
      )}

      {/* Filters */}
      <Card className="p-4 flex gap-4 items-center">
        <div className="flex-1 relative">
          <Search className="h-4 w-4 absolute left-3 top-3 text-text-muted" />
          <input
            type="text"
            placeholder="Filter by Payment ID..."
            value={filters.request_id}
            onChange={(e) => handleFilterChange('request_id', e.target.value)}
            className={inputClass}
          />
        </div>
        <div className="flex-1">
          <input
            type="text"
            placeholder="Filter by Event Type (e.g., PAYMENT_CREATED)..."
            value={filters.action}
            onChange={(e) => handleFilterChange('action', e.target.value)}
            className={inputClassNoIcon}
          />
        </div>
        <div className="flex-1">
          <input
            type="text"
            placeholder="Filter by Actor..."
            value={filters.user_id}
            onChange={(e) => handleFilterChange('user_id', e.target.value)}
            className={inputClassNoIcon}
          />
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Timeline Table */}
        <div className="lg:col-span-2 bg-navy-surface rounded-xl border border-navy-border overflow-hidden">
          <div className="overflow-x-auto h-[600px] overflow-y-auto">
            <table className="min-w-full divide-y divide-navy-border/50">
              <thead className="bg-navy-bg/50 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-bold text-text-muted uppercase tracking-wider">Time</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-text-muted uppercase tracking-wider">Event</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-text-muted uppercase tracking-wider">Actor</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-text-muted uppercase tracking-wider">Payment ID</th>
                  <th className="px-4 py-3 text-left text-xs font-bold text-text-muted uppercase tracking-wider">Hash Chain</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-border/50">
                {loading ? (
                  <tr>
                    <td colSpan="5" className="px-4 py-8 text-center text-text-muted">Loading audit records...</td>
                  </tr>
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-4 py-8 text-center text-text-muted">No records found matching filters.</td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr 
                      key={log.log_id} 
                      onClick={() => setSelectedLog(log)}
                      className={`cursor-pointer hover:bg-navy-border/30 transition-colors ${selectedLog?.log_id === log.log_id ? 'bg-primary/5' : ''}`}
                    >
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-text-muted font-mono">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-sm font-bold text-text-main">{log.action}</span>
                        <div className="text-[10px] text-text-muted uppercase">{log.result}</div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-text-muted font-mono">
                        {log.user_id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-primary font-mono font-bold">
                        {log.request_id || '-'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-text-muted font-mono flex items-center gap-2">
                        <LinkIcon className="h-3 w-3 text-secondary" />
                        {truncateHash(log.current_hash)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected Event Details */}
        <div className="lg:col-span-1">
          {selectedLog ? (
            <div className="bg-navy-surface rounded-xl border border-navy-border overflow-hidden sticky top-6">
              <div className="p-4 border-b border-navy-border bg-navy-bg/50 flex items-center gap-2">
                <FileText className="h-5 w-5 text-secondary" />
                <h2 className="font-bold text-text-main">Event Details</h2>
              </div>
              <div className="p-5 space-y-5">
                
                <div>
                  <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">Event Type</div>
                  <div className="font-bold text-text-main text-lg flex items-center gap-2">
                    {selectedLog.action}
                    <span className={`text-[10px] px-2 py-0.5 rounded border font-bold ${selectedLog.result === 'SUCCESS' ? 'bg-success/20 text-success border-success/30' : 'bg-danger/20 text-danger border-danger/30'}`}>
                      {selectedLog.result}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 border-t border-navy-border/50 pt-4">
                  <div>
                    <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider flex items-center gap-1 mb-1">
                      <Clock className="h-3 w-3" /> Time
                    </div>
                    <div className="text-sm text-text-main font-mono">{new Date(selectedLog.timestamp).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider flex items-center gap-1 mb-1">
                      <User className="h-3 w-3" /> Actor
                    </div>
                    <div className="text-sm font-mono text-primary">{selectedLog.user_id}</div>
                  </div>
                </div>

                {selectedLog.request_id && (
                  <div className="border-t border-navy-border/50 pt-4">
                    <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">Payment ID</div>
                    <div className="text-sm font-mono font-bold text-primary bg-primary/10 px-2 py-1 rounded border border-primary/20 inline-block">
                      {selectedLog.request_id}
                    </div>
                  </div>
                )}

                <div className="border-t border-navy-border/50 pt-4">
                  <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-2">Cryptographic Proof</div>
                  <div className="bg-navy-bg/80 p-3 rounded border border-navy-border text-xs font-mono break-all space-y-3">
                    <div>
                      <span className="text-text-muted block mb-1">Previous Hash:</span>
                      <span className="text-text-main">{selectedLog.previous_hash}</span>
                    </div>
                    <div className="flex justify-center text-secondary">↓</div>
                    <div>
                      <span className="text-text-muted block mb-1">Current Hash:</span>
                      <span className="text-success font-bold">{selectedLog.current_hash}</span>
                    </div>
                  </div>
                </div>

                {selectedLog.details && Object.keys(selectedLog.details).length > 0 && (
                  <div className="border-t border-navy-border/50 pt-4">
                    <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-2">Metadata Details</div>
                    <pre className="text-xs bg-navy-bg/80 p-3 rounded border border-navy-border overflow-x-auto text-primary font-mono">
                      {JSON.stringify(selectedLog.details, null, 2)}
                    </pre>
                  </div>
                )}
                
                <div className="text-[10px] text-text-muted text-right pt-2 font-mono">
                  ID: {selectedLog.log_id} (Seq: {selectedLog.sequence || '-'})
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-navy-surface rounded-xl border border-navy-border h-[600px] flex items-center justify-center text-text-muted flex-col gap-3">
              <Database className="h-12 w-12 opacity-30" />
              <p>Select an event from the timeline to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
