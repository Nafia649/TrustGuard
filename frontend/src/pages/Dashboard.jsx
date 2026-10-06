import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/common/Card';
import { formatINR } from '../utils/formatters';
import { getPayments } from '../api/paymentApi';
import { getAuditLogs } from '../api/auditApi';
import {
  FileText,
  Activity,
  CheckSquare,
  Clock,
  Settings,
  BookOpen,
  ShieldCheck,
  FileUp,
  AlertTriangle,
  Database,
  ArrowRight
} from 'lucide-react';

export default function Dashboard() {
  const [payments, setPayments] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [paymentsData, auditData] = await Promise.all([
          getPayments(),
          getAuditLogs({ limit: 5 })
        ]);
        setPayments(paymentsData);
        setAuditLogs(auditData);
      } catch (err) {
        setError(err.message || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Compute metrics
  const totalPayments = payments.length;
  const pendingCount = payments.filter(p => ['PENDING_APPROVAL'].includes(p.status)).length;
  const holdCount = payments.filter(p => ['ON_HOLD'].includes(p.status)).length;
  const authorizedCount = payments.filter(p => p.status === 'AUTHORIZED').length;
  const releasedCount = payments.filter(p => p.status === 'RELEASED').length;
  const rejectedCount = payments.filter(p => p.status === 'REJECTED').length;

  // Risk buckets (for those that have a risk score)
  const lowRisk = payments.filter(p => p.risk_score !== null && p.risk_score < 30).length;
  const medRisk = payments.filter(p => p.risk_score !== null && p.risk_score >= 30 && p.risk_score < 70).length;
  const highRisk = payments.filter(p => p.risk_score !== null && p.risk_score >= 70).length;

  if (loading) {
    return <div className="p-8 text-center text-text-muted">Loading secure dashboard...</div>;
  }

  if (error) {
    return (
      <div className="p-4 bg-danger/10 text-danger rounded-md border border-danger/20 flex items-center gap-2">
        <AlertTriangle className="h-5 w-5" />
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-main">Welcome to TrustGuard</h1>
        <p className="text-sm text-text-muted mt-1">Autonomous payment security, ML fraud detection, and cryptographic approval orchestration.</p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card className="p-4 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-text-muted uppercase font-bold tracking-wider mb-1">Total</div>
          <div className="text-2xl font-bold text-text-main">{totalPayments}</div>
        </Card>
        <Card className="p-4 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-text-muted uppercase font-bold tracking-wider mb-1">Pending</div>
          <div className="text-2xl font-bold text-warning">{pendingCount}</div>
        </Card>
        <Card className="p-4 flex flex-col items-center justify-center text-center border border-danger/50 bg-danger/5">
          <div className="text-xs text-danger uppercase font-bold tracking-wider mb-1">On Hold</div>
          <div className="text-2xl font-bold text-danger">{holdCount}</div>
        </Card>
        <Card className="p-4 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-text-muted uppercase font-bold tracking-wider mb-1">Authorized</div>
          <div className="text-2xl font-bold text-primary">{authorizedCount}</div>
        </Card>
        <Card className="p-4 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-text-muted uppercase font-bold tracking-wider mb-1">Released</div>
          <div className="text-2xl font-bold text-success">{releasedCount}</div>
        </Card>
        <Card className="p-4 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-text-muted uppercase font-bold tracking-wider mb-1">Rejected</div>
          <div className="text-2xl font-bold text-text-muted line-through">{rejectedCount}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions & Risk */}
        <div className="space-y-6">
          <Card title="Quick Actions">
            <div className="grid grid-cols-2 gap-3">
              <Link to="/invoices/upload" className="bg-navy-bg border border-navy-border p-3 rounded-lg flex flex-col items-center text-center hover:bg-navy-border/50 transition-colors">
                <FileUp className="h-6 w-6 text-primary mb-2" />
                <span className="text-xs font-bold text-text-main">Upload Invoice</span>
              </Link>
              <Link to="/approval" className="bg-navy-bg border border-navy-border p-3 rounded-lg flex flex-col items-center text-center hover:bg-navy-border/50 transition-colors">
                <CheckSquare className="h-6 w-6 text-warning mb-2" />
                <span className="text-xs font-bold text-text-main">Sign Approvals</span>
              </Link>
              <Link to="/analyst" className="bg-navy-bg border border-navy-border p-3 rounded-lg flex flex-col items-center text-center hover:bg-navy-border/50 transition-colors">
                <Clock className="h-6 w-6 text-danger mb-2" />
                <span className="text-xs font-bold text-text-main">Analyst Queue</span>
              </Link>
              <Link to="/audit" className="bg-navy-bg border border-navy-border p-3 rounded-lg flex flex-col items-center text-center hover:bg-navy-border/50 transition-colors">
                <ShieldCheck className="h-6 w-6 text-success mb-2" />
                <span className="text-xs font-bold text-text-main">Audit Log</span>
              </Link>
              <Link to="/policy" className="bg-navy-bg border border-navy-border p-3 rounded-lg flex flex-col items-center text-center hover:bg-navy-border/50 transition-colors">
                <Settings className="h-6 w-6 text-secondary mb-2" />
                <span className="text-xs font-bold text-text-main">Policy Rules</span>
              </Link>
              <Link to="/ledger" className="bg-navy-bg border border-navy-border p-3 rounded-lg flex flex-col items-center text-center hover:bg-navy-border/50 transition-colors">
                <BookOpen className="h-6 w-6 text-text-muted mb-2" />
                <span className="text-xs font-bold text-text-main">Mock Ledger</span>
              </Link>
            </div>
          </Card>

          <Card title="Active Risk Distribution">
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-xs font-bold text-text-muted mb-1">
                  <span>Low Risk (Auto)</span>
                  <span className="text-success">{lowRisk}</span>
                </div>
                <div className="w-full bg-navy-bg rounded-full h-2">
                  <div className="bg-success h-2 rounded-full" style={{ width: totalPayments ? `${(lowRisk / totalPayments) * 100}%` : '0%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs font-bold text-text-muted mb-1">
                  <span>Medium Risk (Manual)</span>
                  <span className="text-warning">{medRisk}</span>
                </div>
                <div className="w-full bg-navy-bg rounded-full h-2">
                  <div className="bg-warning h-2 rounded-full" style={{ width: totalPayments ? `${(medRisk / totalPayments) * 100}%` : '0%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs font-bold text-text-muted mb-1">
                  <span>High Risk (Hold)</span>
                  <span className="text-danger">{highRisk}</span>
                </div>
                <div className="w-full bg-navy-bg rounded-full h-2">
                  <div className="bg-danger h-2 rounded-full" style={{ width: totalPayments ? `${(highRisk / totalPayments) * 100}%` : '0%' }}></div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Recent Payments */}
        <div className="lg:col-span-2 space-y-6">
          <Card title="Recent Payment Requests">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="text-xs text-text-muted uppercase border-b border-navy-border">
                  <tr>
                    <th className="pb-3 font-semibold px-4">Request ID</th>
                    <th className="pb-3 font-semibold px-4">Vendor</th>
                    <th className="pb-3 font-semibold px-4">Amount</th>
                    <th className="pb-3 font-semibold px-4">Score</th>
                    <th className="pb-3 font-semibold px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-border/50">
                  {payments.slice(0, 5).map((p) => (
                    <tr key={p.request_id} className="hover:bg-navy-bg/50 transition-colors">
                      <td className="py-3 px-4 font-mono text-primary font-bold">
                        <Link to={`/payments/${p.request_id}`} className="hover:underline">
                          {p.request_id}
                        </Link>
                      </td>
                      <td className="py-3 px-4 text-text-main">{p.vendor_id}</td>
                      <td className="py-3 px-4 text-text-main font-bold">{formatINR(p.amount)}</td>
                      <td className="py-3 px-4">
                        {p.risk_score !== null ? (
                          <span className={`font-bold ${p.risk_score >= 90 ? 'text-danger' : p.risk_score >= 50 ? 'text-warning' : 'text-success'}`}>
                            {p.risk_score}
                          </span>
                        ) : (
                          <span className="text-text-muted">-</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-[10px] px-2 py-0.5 rounded font-bold border ${
                          p.status === 'ON_HOLD' ? 'bg-danger/20 text-danger border-danger/30' : 
                          p.status === 'PENDING_APPROVAL' ? 'bg-warning/20 text-warning border-warning/30' : 
                          p.status === 'AUTHORIZED' ? 'bg-primary/20 text-primary border-primary/30' :
                          p.status === 'RELEASED' ? 'bg-success/20 text-success border-success/30' :
                          'bg-navy-border text-text-muted border-navy-border'
                        }`}>
                          {p.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {payments.length === 0 && (
                    <tr>
                      <td colSpan="5" className="py-8 text-center text-text-muted">No payments found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
              {payments.length > 5 && (
                <div className="pt-3 pb-1 px-4 text-right">
                  <Link to="/payments" className="text-xs text-primary font-bold hover:underline inline-flex items-center gap-1">
                    View all payments <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              )}
            </div>
          </Card>

          {/* Real Audit Logs */}
          <Card title="Live Audit Telemetry">
            <div className="divide-y divide-navy-border/50">
              {auditLogs.map((log) => (
                <div key={log.log_id} className="p-4 flex gap-4 hover:bg-navy-bg/50 transition-colors">
                  <div className="mt-0.5">
                    <Database className="h-5 w-5 text-secondary" />
                  </div>
                  <div className="flex-1">
                    <div className="flex justify-between items-start mb-1">
                      <span className="text-sm font-bold text-text-main">{log.action}</span>
                      <span className="text-xs font-mono text-text-muted">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-text-muted">Actor: <span className="font-mono text-primary">{log.user_id}</span></span>
                      {log.request_id && (
                        <span className="font-mono text-text-muted">{log.request_id}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {auditLogs.length === 0 && (
                <div className="p-6 text-center text-text-muted">No audit logs found.</div>
              )}
            </div>
            <div className="pt-2 pb-3 px-4 border-t border-navy-border/50 bg-navy-bg/50">
              <Link to="/audit" className="text-xs text-secondary font-bold hover:underline inline-flex items-center gap-1">
                View complete cryptographic chain <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
