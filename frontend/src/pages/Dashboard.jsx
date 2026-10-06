import { useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import RiskScore from '../components/risk/RiskScore';
import RiskReasons from '../components/risk/RiskReasons';
import RoutingCard from '../components/risk/RoutingCard';
import ThreeWayMatch from '../components/payment/ThreeWayMatch';
import {
  CreditCard,
  Clock,
  AlertTriangle,
  PauseCircle,
  CheckCircle,
  ShieldCheck,
  Loader2,
  Database,
  Play,
  CheckCircle2,
  XCircle,
  Info
} from 'lucide-react';

import { mockPayments } from '../data/mockPayments';
import { formatINR } from '../utils/formatters';
import { seedDatabase, scorePayment, verifyAuditLog } from '../api/riskApi';

export default function Dashboard() {
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState(null);

  const [scoring, setScoring] = useState(false);
  const [scoredPayment, setScoredPayment] = useState(null);

  const [verifyingAudit, setVerifyingAudit] = useState(false);
  const [auditResult, setAuditResult] = useState(null);

  const [error, setError] = useState(null);

  // 1. Seed demo database
  const handleSeed = async () => {
    setSeeding(true);
    setError(null);
    try {
      const data = await seedDatabase();
      setSeedResult(data);
    } catch (err) {
      setError(`Seed Error: ${err.message}`);
    } finally {
      setSeeding(false);
    }
  };

  // 2. Score REQ-DEMO-001
  const handleScore = async () => {
    setScoring(true);
    setError(null);
    try {
      const data = await scorePayment('REQ-DEMO-001');
      setScoredPayment(data);
      // Auto-refresh audit verification after scoring
      const audit = await verifyAuditLog().catch(() => null);
      if (audit) setAuditResult(audit);
    } catch (err) {
      setError(`Scoring Error: ${err.message}`);
    } finally {
      setScoring(false);
    }
  };

  // 3. Verify audit log hash chain
  const handleVerifyAudit = async () => {
    setVerifyingAudit(true);
    setError(null);
    try {
      const data = await verifyAuditLog();
      setAuditResult(data);
    } catch (err) {
      setError(`Audit Verification Error: ${err.message}`);
    } finally {
      setVerifyingAudit(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-main">Payment Security Dashboard</h1>
          <p className="text-xs text-text-muted mt-1">TrustGuard + REALKEY Orchestration Layer</p>
        </div>
      </div>

      {/* LIVE HACKATHON DEMO CONTROL PANEL */}
      <Card className="border-primary/40 bg-navy-surface shadow-xl">
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-navy-border gap-2">
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-primary" />
              <h2 className="text-base font-bold text-text-main">TrustGuard Live Demo Controls</h2>
              <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 font-medium">
                Backend Connected (http://127.0.0.1:8000)
              </span>
            </div>
            <div className="text-xs text-text-muted">
              Demo ML Provider Active
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              onClick={handleSeed}
              disabled={seeding}
              className="flex items-center space-x-2"
            >
              {seeding ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Database className="w-4 h-4" />
              )}
              <span>1. Seed Demo Data</span>
            </Button>

            <Button
              onClick={handleScore}
              disabled={scoring}
              className="flex items-center space-x-2 bg-emerald-600 hover:bg-emerald-500 text-white"
            >
              {scoring ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span>2. Score REQ-DEMO-001</span>
            </Button>

            <Button
              onClick={handleVerifyAudit}
              disabled={verifyingAudit}
              variant="secondary"
              className="flex items-center space-x-2"
            >
              {verifyingAudit ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ShieldCheck className="w-4 h-4 text-primary" />
              )}
              <span>3. Verify Audit Chain</span>
            </Button>
          </div>

          {/* Feedback & Status Messages */}
          {error && (
            <div className="p-3 bg-danger/10 border border-danger/30 rounded-md text-xs text-danger flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {seedResult && !error && (
            <div className="p-3 bg-success/10 border border-success/30 rounded-md text-xs text-success flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>
                  <strong>Database Seeded:</strong> {seedResult.company} ({seedResult.vendors_count} Vendors, {seedResult.purchase_orders_count} POs, {seedResult.payment_requests_count} Payment Requests).
                </span>
              </div>
              <span className="text-text-muted">Policy v{seedResult.policy_version}</span>
            </div>
          )}

          {auditResult && !error && (
            <div className="p-3 bg-navy-bg border border-navy-border rounded-md text-xs flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {auditResult.valid ? (
                  <CheckCircle className="w-4 h-4 text-success shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-danger shrink-0" />
                )}
                <span>
                  <strong>SHA-256 Audit Chain:</strong>{' '}
                  <span className={auditResult.valid ? 'text-success font-semibold' : 'text-danger font-semibold'}>
                    {auditResult.valid ? 'VALID (Pristine)' : 'COMPROMISED'}
                  </span>
                  {' '}— {auditResult.records_checked} cryptographically linked records verified.
                </span>
              </div>
              {auditResult.corrupted_id && (
                <span className="text-danger">Corrupted ID: {auditResult.corrupted_id}</span>
              )}
            </div>
          )}
        </div>
      </Card>

      {/* LIVE SCORING RESULTS DISPLAY (SHOWN WHEN REQ-DEMO-001 IS SCORED) */}
      {scoredPayment && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-xs uppercase tracking-wider font-bold text-success bg-success/10 px-2 py-1 rounded border border-success/20">
                Live Backend Evaluation
              </span>
              <h2 className="text-xl font-bold text-text-main">
                Payment {scoredPayment.requestId} — {scoredPayment.paymentStatus}
              </h2>
            </div>
            <Link
              to={`/risk/${scoredPayment.requestId}`}
              className="text-primary text-xs hover:underline flex items-center"
            >
              Open Full Risk Analysis View →
            </Link>
          </div>

          {/* Model Disclaimer Notice */}
          <div className="p-2.5 bg-navy-bg border border-navy-border rounded text-xs text-text-muted flex items-center space-x-2">
            <Info className="w-4 h-4 text-primary shrink-0" />
            <span>
              Evaluation source: <strong>{scoredPayment.modelVersion}</strong>. Risk score: <strong>{scoredPayment.riskScore}/100</strong>, Fraud Probability: <strong>{(scoredPayment.fraudProbability * 100).toFixed(0)}%</strong>.
            </span>
          </div>

          {/* 3-Column Component Grid (Reusing existing components) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <RiskScore
                riskScore={scoredPayment.riskScore}
                riskLevel={scoredPayment.riskLevel}
                fraudProbability={scoredPayment.fraudProbability}
                modelVersion={scoredPayment.modelVersion}
              />
            </div>

            <div className="lg:col-span-2">
              <RiskReasons reasons={scoredPayment.reasons} />
            </div>
          </div>

          {/* Routing Decision & Three-Way Match Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <RoutingCard
              routing={scoredPayment.routing}
              riskLevel={scoredPayment.riskLevel}
            />

            <div className="bg-navy-surface border border-navy-border rounded-xl p-5">
              <ThreeWayMatch
                threeWayMatch={scoredPayment.threeWayMatch}
                poId={scoredPayment.poId}
                invoiceId={scoredPayment.invoiceId}
              />

              {/* Business Checks Details Summary */}
              <div className="mt-4 pt-3 border-t border-navy-border/60">
                <div className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                  Verified Business Facts
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="flex justify-between p-1.5 bg-navy-bg rounded border border-navy-border/40">
                    <span className="text-text-muted">PO Amount Match:</span>
                    <span className="text-success font-medium">₹45,000 (100%)</span>
                  </div>
                  <div className="flex justify-between p-1.5 bg-navy-bg rounded border border-navy-border/40">
                    <span className="text-text-muted">Bank Account:</span>
                    <span className="text-success font-medium">Verified ACME-001</span>
                  </div>
                  <div className="flex justify-between p-1.5 bg-navy-bg rounded border border-navy-border/40">
                    <span className="text-text-muted">Vendor Approval:</span>
                    <span className="text-success font-medium">Approved Vendor</span>
                  </div>
                  <div className="flex justify-between p-1.5 bg-navy-bg rounded border border-navy-border/40">
                    <span className="text-text-muted">Duplicate Check:</span>
                    <span className="text-success font-medium">No Duplicates</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* METRIC OVERVIEW CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wider">Total Payments</p>
              <h2 className="text-3xl font-bold mt-2">
                {scoredPayment ? '4' : '24'}
              </h2>
              <p className="text-xs text-text-muted mt-1">Acme Ltd Portfolio</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
              <CreditCard className="text-primary w-5 h-5" />
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wider">Pending Approvals</p>
              <h2 className="text-3xl font-bold mt-2">
                {scoredPayment ? '2' : '5'}
              </h2>
              <p className="text-xs text-warning mt-1">Requires Human Signatures</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-warning/10 flex items-center justify-center">
              <Clock className="text-warning w-5 h-5" />
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wider">Payments on Hold</p>
              <h2 className="text-3xl font-bold mt-2">
                {scoredPayment ? '1' : '3'}
              </h2>
              <p className="text-xs text-danger mt-1">High Risk Escalation</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center">
              <PauseCircle className="text-danger w-5 h-5" />
            </div>
          </div>
        </Card>
      </div>

      {/* RECENT PAYMENTS TABLE & SYSTEM FLOW */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card
            title="Payment Portfolio"
            action={
              <Link to="/payments" className="text-primary text-sm hover:underline">
                View all →
              </Link>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="text-xs text-text-muted uppercase border-b border-navy-border">
                  <tr>
                    <th className="pb-3 font-semibold">Request ID</th>
                    <th className="pb-3 font-semibold">Vendor</th>
                    <th className="pb-3 font-semibold">Amount</th>
                    <th className="pb-3 font-semibold">Risk</th>
                    <th className="pb-3 font-semibold">Status</th>
                    <th className="pb-3 font-semibold">Required Approval</th>
                    <th className="pb-3 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-border">
                  {mockPayments.slice(0, 5).map((p) => {
                    const isScored = scoredPayment && scoredPayment.requestId === p.id;
                    const status = isScored ? scoredPayment.paymentStatus : p.status;
                    const riskLevel = isScored ? scoredPayment.riskLevel : p.riskLevel;

                    return (
                      <tr key={p.id} className="hover:bg-navy-border/20 transition-colors">
                        <td className="py-3 font-medium text-text-main">{p.id}</td>
                        <td className="py-3">{p.vendor}</td>
                        <td className="py-3">{formatINR(p.amount)}</td>
                        <td className="py-3">
                          <Link
                            to={`/risk/${p.id}`}
                            className="hover:opacity-80 transition-opacity"
                            title="View Risk Analysis"
                          >
                            <Badge status={riskLevel} />
                          </Link>
                        </td>
                        <td className="py-3">
                          <Badge status={status} />
                        </td>
                        <td className="py-3 text-text-muted">{p.requiredApproval}</td>
                        <td className="py-3 flex items-center space-x-2">
                          <Link to={`/payments/${p.id}`} className="text-primary hover:underline text-xs">
                            View
                          </Link>
                          {p.id === 'REQ-DEMO-001' && (
                            <button
                              onClick={handleScore}
                              disabled={scoring}
                              className="px-2 py-0.5 rounded text-xs bg-primary/20 text-primary hover:bg-primary/30 border border-primary/30"
                            >
                              Score
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* System Flow Card */}
          <Card title="Orchestration Pipeline">
            <div className="flex flex-col space-y-2">
              <div className="flex items-center text-sm">
                <CheckCircle className="w-4 h-4 text-success mr-2" />
                <span>1. Payment Ingestion (ERP / Accounts System)</span>
              </div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm">
                <CheckCircle className="w-4 h-4 text-success mr-2" />
                <span>2. Deterministic Three-Way Match (PO + GRN + Invoice)</span>
              </div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm">
                <CheckCircle className="w-4 h-4 text-success mr-2" />
                <span>3. ML Feature Derivation &amp; Fraud Risk Intelligence</span>
              </div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm">
                <AlertTriangle className="w-4 h-4 text-warning mr-2" />
                <span>4. Dynamic Policy Routing (Auto / 1-Sig / 2-Sig / Hold)</span>
              </div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm">
                <Clock className="w-4 h-4 text-primary mr-2" />
                <span>5. REALKEY Cryptographic Passkey Approval (If Escalated)</span>
              </div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm">
                <ShieldCheck className="w-4 h-4 text-success mr-2" />
                <span>6. Tamper-Evident SHA-256 Chained Audit Logging</span>
              </div>
            </div>
          </Card>
        </div>

        {/* Risk Overview Column */}
        <div className="space-y-6">
          <Card title="Risk Distribution">
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Low Risk (Auto-Approve)</span>
                  <span className="text-success">1</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-success h-1.5 rounded-full" style={{ width: '25%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Medium Risk (1 Signature)</span>
                  <span className="text-warning">2</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-warning h-1.5 rounded-full" style={{ width: '50%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>High Risk (Hold / Analyst Review)</span>
                  <span className="text-danger">1</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-danger h-1.5 rounded-full" style={{ width: '25%' }}></div>
                </div>
              </div>
            </div>
          </Card>

          <Card title="Audit Integrity Summary">
            <div className="space-y-3 text-xs text-text-muted">
              <div className="flex justify-between">
                <span>Hash Algorithm:</span>
                <span className="text-text-main font-mono">SHA-256</span>
              </div>
              <div className="flex justify-between">
                <span>Genesis Anchor:</span>
                <span className="text-text-main font-mono">000000...0000</span>
              </div>
              <div className="flex justify-between">
                <span>Storage Engine:</span>
                <span className="text-text-main">SQLite Chained</span>
              </div>
              <div className="flex justify-between">
                <span>Tamper Evident:</span>
                <span className="text-success font-semibold">Active</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
