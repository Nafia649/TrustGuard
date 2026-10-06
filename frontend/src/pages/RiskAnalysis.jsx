import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getMockPayment } from '../data/mockPayments';
import { getRiskAnalysis, verifyAuditLog } from '../api/riskApi';
import RiskScore from '../components/risk/RiskScore';
import RiskReasons from '../components/risk/RiskReasons';
import RoutingCard from '../components/risk/RoutingCard';
import ThreeWayMatch from '../components/payment/ThreeWayMatch';
import { formatINR } from '../utils/formatters';
import { ArrowLeft, Loader2, AlertTriangle, CheckCircle, ShieldCheck, Info } from 'lucide-react';
import clsx from 'clsx';

export default function RiskAnalysis() {
  const { id } = useParams();
  const payment = getMockPayment(id);
  const [riskData, setRiskData] = useState(null);
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      getRiskAnalysis(id),
      verifyAuditLog().catch(() => null),
    ])
      .then(([risk, audit]) => {
        setRiskData(risk);
        setAuditData(audit);
      })
      .catch((err) => {
        console.error('Error fetching risk analysis:', err);
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [id]);

  const paymentObj = payment || {
    id: id,
    vendor: riskData?.raw?.vendor_id || 'Acme Industrial Supplies',
    amount: riskData?.raw?.business_checks?.details?.invoice_amount || 45000,
    currency: 'INR',
    poId: riskData?.poId || 'PO-2026-001',
    invoiceId: riskData?.invoiceId || 'INV-2026-001',
    threeWayMatch: riskData?.threeWayMatch || { po_match: true, grn_match: true, invoice_match: true },
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-3">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
        <span className="text-sm text-text-muted">Evaluating payment risk with TrustGuard...</span>
      </div>
    );
  }

  if (error || !riskData) {
    return (
      <div className="text-center py-12 space-y-4">
        <AlertTriangle className="w-10 h-10 text-danger mx-auto" />
        <h2 className="text-xl font-bold text-text-main">Risk Analysis Unavailable</h2>
        <p className="text-sm text-text-muted">{error || 'Could not evaluate risk for this payment.'}</p>
        <Link to="/payments" className="text-primary mt-4 inline-block hover:underline">
          ← Back to Payments
        </Link>
      </div>
    );
  }

  const getBannerColor = (level) => {
    switch (level) {
      case 'LOW':
        return 'bg-success/10 border-success/30 text-success';
      case 'MEDIUM':
        return 'bg-warning/10 border-warning/30 text-warning';
      case 'HIGH':
        return 'bg-danger/10 border-danger/30 text-danger';
      case 'CRITICAL':
        return 'bg-danger/20 border-danger text-danger';
      default:
        return 'bg-navy-surface border-navy-border text-text-muted';
    }
  };

  const Icon = riskData.riskLevel === 'LOW' ? CheckCircle : AlertTriangle;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to={`/payments/${id}`} className="text-text-muted hover:text-text-main">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-2xl font-bold text-text-main">Detailed Risk Analysis: {paymentObj.id}</h1>
        </div>
        <div className="text-xs text-text-muted">
          Status: <strong className="text-text-main">{riskData.paymentStatus}</strong>
        </div>
      </div>

      {/* Risk Banner */}
      <div className={clsx('p-4 border rounded-lg flex items-center shadow-lg', getBannerColor(riskData.riskLevel))}>
        <Icon className="w-6 h-6 mr-3 shrink-0" />
        <div className="flex-1">
          <h2 className="font-bold text-lg">{riskData.riskLevel} RISK</h2>
          <p className="text-sm opacity-90">
            Payment of {formatINR(paymentObj.amount)} to {paymentObj.vendor} ({paymentObj.id})
          </p>
        </div>
        <div className="text-xs font-semibold px-2.5 py-1 rounded bg-navy-bg border border-current">
          Routing: {riskData.routing.tier}
        </div>
      </div>

      {/* Demo notice */}
      <div className="p-3 bg-navy-bg border border-navy-border rounded-md text-xs text-text-muted flex items-center space-x-2">
        <Info className="w-4 h-4 text-primary shrink-0" />
        <span>
          Evaluated via <strong>{riskData.modelVersion}</strong>. Score: <strong>{riskData.riskScore}/100</strong>, Fraud Probability: <strong>{(riskData.fraudProbability * 100).toFixed(0)}%</strong>.
        </span>
      </div>

      {/* Grid with Score & Reasons */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <RiskScore
            riskScore={riskData.riskScore}
            riskLevel={riskData.riskLevel}
            fraudProbability={riskData.fraudProbability}
            modelVersion={riskData.modelVersion}
          />
        </div>
        <div className="lg:col-span-2">
          <RiskReasons reasons={riskData.reasons} />
        </div>
      </div>

      {/* Routing Card & Three-Way Match */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RoutingCard routing={riskData.routing} riskLevel={riskData.riskLevel} />
        <div className="bg-navy-surface border border-navy-border rounded-xl p-5">
          <ThreeWayMatch
            threeWayMatch={riskData.threeWayMatch || paymentObj.threeWayMatch}
            poId={paymentObj.poId}
            invoiceId={paymentObj.invoiceId}
          />
        </div>
      </div>

      {/* Cryptographic Audit Chain Verification */}
      {auditData && (
        <div className="p-4 bg-navy-surface border border-navy-border rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <ShieldCheck className="w-5 h-5 text-success" />
            <div>
              <div className="text-sm font-semibold text-text-main">
                Tamper-Evident SHA-256 Audit Chain:{' '}
                <span className={auditData.valid ? 'text-success' : 'text-danger'}>
                  {auditData.valid ? 'VALID' : 'CORRUPTED'}
                </span>
              </div>
              <div className="text-xs text-text-muted">
                {auditData.records_checked} immutable event records verified from genesis anchor.
              </div>
            </div>
          </div>
          <Link to="/dashboard" className="text-primary text-xs hover:underline">
            View in Dashboard →
          </Link>
        </div>
      )}
    </div>
  );
}
