import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPayment } from '../api/paymentApi';
import { getRiskAnalysis } from '../api/riskApi';
import { verifyAuditChain } from '../api/auditApi';
import RiskScore from '../components/risk/RiskScore';
import { formatINR } from '../utils/formatters';
import { ArrowLeft, Loader2, AlertTriangle, CheckCircle, ShieldCheck, Info } from 'lucide-react';
import clsx from 'clsx';
import Card from '../components/common/Card';

export default function RiskAnalysis() {
  const { id } = useParams();
  const [payment, setPayment] = useState(null);
  const [auditData, setAuditData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const scoringRef = useRef(false);

  useEffect(() => {
    let isMounted = true;
    
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        let paymentData = await getPayment(id);
        
        // If the payment is unscored, call the POST /score endpoint via getRiskAnalysis
        if (paymentData.risk_score === null && !scoringRef.current) {
          scoringRef.current = true;
          try {
            await getRiskAnalysis(id);
          } finally {
            scoringRef.current = false;
          }
          // Refetch to get the updated payment with the score and routing applied to DB
          paymentData = await getPayment(id);
        } else if (paymentData.risk_score === null && scoringRef.current) {
            // If another effect is scoring it, poll until scoring finishes
            while (scoringRef.current) {
              await new Promise(r => setTimeout(r, 500));
            }
            paymentData = await getPayment(id);
        }
        
        const audit = await verifyAuditChain().catch(() => null);
        
        if (isMounted) {
          setPayment(paymentData);
          setAuditData(audit);
          setLoading(false);
        }
      } catch (err) {
        console.error('Error fetching risk analysis:', err);
        if (isMounted) {
          setError(err.message || 'Failed to load risk data');
          setLoading(false);
        }
      }
    };

    loadData();
    
    return () => {
      isMounted = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-3">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
        <span className="text-sm text-text-muted">Scoring payment and generating SHAP analysis...</span>
      </div>
    );
  }

  if (error || !payment) {
    return (
      <div className="text-center py-12 space-y-4">
        <AlertTriangle className="w-10 h-10 text-danger mx-auto" />
        <h2 className="text-xl font-bold text-text-main">Risk Analysis Unavailable</h2>
        <p className="text-sm text-text-muted">{error || 'Could not evaluate risk for this payment.'}</p>
        <Link to="/payments" className="text-primary mt-4 inline-block hover:underline">
          &larr; Back to Payments
        </Link>
      </div>
    );
  }

  // At this point, if risk_score is strictly null (e.g. backend error where it didn't update), prevent false "0"
  if (payment.risk_score === null) {
     return (
      <div className="text-center py-12 space-y-4">
        <AlertTriangle className="w-10 h-10 text-warning mx-auto" />
        <h2 className="text-xl font-bold text-text-main">Payment Not Scored</h2>
        <p className="text-sm text-text-muted">The backend failed to assign a numeric risk score.</p>
        <Link to="/payments" className="text-primary mt-4 inline-block hover:underline">
          &larr; Back to Payments
        </Link>
      </div>
    );
  }

  const riskLevel = payment.risk_score >= 90 ? 'CRITICAL' : payment.risk_score >= 70 ? 'HIGH' : payment.risk_score >= 30 ? 'MEDIUM' : 'LOW';
  
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

  const Icon = riskLevel === 'LOW' ? CheckCircle : AlertTriangle;
  const reasons = payment.risk_reasons ? (typeof payment.risk_reasons === 'string' ? JSON.parse(payment.risk_reasons) : payment.risk_reasons) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to={`/payments/${id}`} className="text-text-muted hover:text-text-main">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-2xl font-bold text-text-main">Detailed Risk Analysis: {payment.request_id}</h1>
        </div>
        <div className="text-xs text-text-muted">
          Status: <strong className="text-text-main">{payment.status}</strong>
        </div>
      </div>

      {/* Risk Banner */}
      <div className={clsx('p-4 border rounded-lg flex items-center shadow-lg', getBannerColor(riskLevel))}>
        <Icon className="w-6 h-6 mr-3 shrink-0" />
        <div className="flex-1">
          <h2 className="font-bold text-lg">{riskLevel} RISK</h2>
          <p className="text-sm opacity-90">
            Payment of {formatINR(payment.amount)} to {payment.vendor_id} ({payment.request_id})
          </p>
        </div>
        <div className="text-xs font-semibold px-2.5 py-1 rounded bg-navy-bg border border-current">
          Routing: {payment.routing_tier}
        </div>
      </div>

      {/* Model notice */}
      <div className="p-3 bg-navy-bg border border-navy-border rounded-md text-xs text-text-muted flex items-center space-x-2">
        <Info className="w-4 h-4 text-primary shrink-0" />
        <span>
          Evaluated via <strong>XGBoost Model (Realtime)</strong>. Score: <strong>{payment.risk_score}/100</strong>, Fraud Probability: <strong>{((payment.fraud_probability) * 100).toFixed(2)}%</strong>.
        </span>
      </div>

      {/* Grid with Score & Reasons */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <RiskScore
            riskScore={payment.risk_score}
            riskLevel={riskLevel}
            fraudProbability={payment.fraud_probability}
            modelVersion="XGB-3.2.0"
          />
        </div>
        <div className="lg:col-span-2">
          {/* Risk Reasons manually mapped to avoid mock components */}
          <Card title="XGBoost + SHAP Explanations" className="h-full">
            <div className="space-y-4">
              <p className="text-sm text-text-muted border-b border-navy-border pb-3">
                Top features contributing to the assigned risk score.
              </p>
              
              {reasons.length > 0 ? (
                <ul className="space-y-3">
                  {reasons.map((r, i) => (
                    <li key={i} className="flex items-start bg-navy-bg/50 p-3 rounded-lg border border-navy-border">
                      <div className="mt-0.5 mr-3">
                        {payment.risk_score >= 70 ? (
                          <AlertTriangle className="w-5 h-5 text-danger" />
                        ) : (
                          <CheckCircle className="w-5 h-5 text-success" />
                        )}
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-text-main">
                          {typeof r === 'string' ? r : r.description || r.feature}
                        </h4>
                        {typeof r !== 'string' && r.impact && (
                          <p className="text-xs text-text-muted mt-1">Impact: {r.impact}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-center py-8 text-text-muted">
                  <CheckCircle className="w-8 h-8 text-success mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No anomalous SHAP values detected.</p>
                </div>
              )}
            </div>
          </Card>
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
          <Link to="/audit" className="text-primary text-xs hover:underline">
            View in Audit Log &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}
