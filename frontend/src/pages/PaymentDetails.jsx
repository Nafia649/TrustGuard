import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getPayment } from '../api/paymentApi';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import PaymentSummary from '../components/payment/PaymentSummary';
import { formatINR, formatDate } from '../utils/formatters';
import { CheckCircle, AlertTriangle, ArrowLeft, ArrowRight, Loader2, Info } from 'lucide-react';

export default function PaymentDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [payment, setPayment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPayment = async () => {
      try {
        setLoading(true);
        const data = await getPayment(id);
        setPayment(data);
      } catch (err) {
        setError(err.message || 'Failed to fetch payment details');
      } finally {
        setLoading(false);
      }
    };
    fetchPayment();
  }, [id]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64 text-text-muted">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    );
  }

  if (error || !payment) {
    return (
      <div className="p-4 bg-danger/10 text-danger rounded-md border border-danger/20 flex items-center gap-2">
        <AlertTriangle className="h-5 w-5" />
        {error || 'Payment not found'}
      </div>
    );
  }

  const riskReasons = Array.isArray(payment.risk_reasons)
    ? payment.risk_reasons
    : (typeof payment.risk_reasons === 'string' 
        ? JSON.parse(payment.risk_reasons) 
        : []);
  
  // Create mock objects for the components that expect them, populated with real data
  const threeWayMatch = {
    po_match: payment.three_way_match?.po_match ?? true,
    grn_match: payment.three_way_match?.grn_match ?? true,
    invoice_match: payment.three_way_match?.invoice_match ?? true
  };
  
  const paymentSummaryObj = {
    id: payment.request_id,
    vendorId: payment.vendor_id,
    vendor: payment.vendor_id,
    amount: payment.amount,
    currency: payment.currency,
    poId: payment.po_id,
    invoiceId: payment.invoice_id,
    status: payment.status
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <Link to="/payments" className="text-text-muted hover:text-text-main">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <h1 className="text-2xl font-bold text-text-main">Payment Details: {payment.request_id}</h1>
        </div>
        {(payment.status === 'PENDING_APPROVAL' || payment.status === 'ON_HOLD') && (
          <Button onClick={() => navigate(`/payments/${id}/approve`)}>Review & Approve</Button>
        )}
      </div>

      <Card className="bg-navy-surface border-primary/20">
        <PaymentSummary payment={paymentSummaryObj} />
      </Card>

      {/* 3-Way Match Simple View */}
      <Card title="Three-Way Match Details">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
           <div className={`p-4 rounded-xl border flex items-start space-x-3 ${threeWayMatch.po_match ? 'bg-success/5 border-success/20' : 'bg-danger/5 border-danger/20'}`}>
              {threeWayMatch.po_match ? <CheckCircle className="w-6 h-6 text-success" /> : <AlertTriangle className="w-6 h-6 text-danger" />}
              <div>
                <h4 className="font-semibold text-text-main">Purchase Order</h4>
                <p className="text-xs text-text-muted mt-1">{threeWayMatch.po_match ? 'Matches PO amounts' : 'PO mismatch detected'}</p>
              </div>
           </div>
           <div className={`p-4 rounded-xl border flex items-start space-x-3 ${threeWayMatch.grn_match ? 'bg-success/5 border-success/20' : 'bg-danger/5 border-danger/20'}`}>
              {threeWayMatch.grn_match ? <CheckCircle className="w-6 h-6 text-success" /> : <AlertTriangle className="w-6 h-6 text-danger" />}
              <div>
                <h4 className="font-semibold text-text-main">Goods Receipt</h4>
                <p className="text-xs text-text-muted mt-1">{threeWayMatch.grn_match ? 'Goods confirmed received' : 'Missing or invalid GRN'}</p>
              </div>
           </div>
           <div className={`p-4 rounded-xl border flex items-start space-x-3 ${threeWayMatch.invoice_match ? 'bg-success/5 border-success/20' : 'bg-danger/5 border-danger/20'}`}>
              {threeWayMatch.invoice_match ? <CheckCircle className="w-6 h-6 text-success" /> : <AlertTriangle className="w-6 h-6 text-danger" />}
              <div>
                <h4 className="font-semibold text-text-main">Invoice Validation</h4>
                <p className="text-xs text-text-muted mt-1">{threeWayMatch.invoice_match ? 'Invoice correctly formatted' : 'Invoice validation failed'}</p>
              </div>
           </div>
        </div>
      </Card>

      {/* Risk Analysis Section */}
      <Card title="ML Risk Analysis (XGBoost + SHAP)">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 flex flex-col space-y-6">
            <div className="bg-navy-bg p-6 rounded-xl border border-navy-border flex flex-col items-center justify-center text-center">
              <div className="text-sm font-semibold text-text-muted mb-2">Fraud Risk Score</div>
              <div className={`text-5xl font-bold mb-2 ${payment.risk_score >= 90 ? 'text-danger' : payment.risk_score >= 50 ? 'text-warning' : 'text-success'}`}>
                {payment.risk_score || '0'}
              </div>
              <div className="text-xs text-text-muted uppercase tracking-wider">{payment.routing_tier}</div>
            </div>
          </div>
          <div className="lg:col-span-2 space-y-4">
            <h4 className="text-sm font-bold text-text-muted uppercase mb-2">Top Risk Factors</h4>
            {riskReasons.length > 0 ? (
              <ul className="space-y-2 bg-navy-bg border border-navy-border rounded-lg p-4">
                {riskReasons.map((reason, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-text-muted">
                    <span className="text-danger mt-0.5">•</span>
                    {reason}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="p-4 bg-navy-bg border border-navy-border rounded-lg text-sm text-text-muted">
                No major risk factors detected.
              </div>
            )}
            <div className="text-xs text-text-muted flex items-center gap-1 mt-4">
              <Info className="w-3 h-3" />
              This analysis was generated by the TrustGuard XGBoost ML model.
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Core Details">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-text-muted mb-1 text-xs uppercase font-bold">Request ID</p><p className="font-mono text-primary font-bold">{payment.request_id}</p></div>
              <div><p className="text-text-muted mb-1 text-xs uppercase font-bold">Created</p><p className="font-mono text-text-main">{new Date(payment.timestamp).toLocaleString()}</p></div>
              <div><p className="text-text-muted mb-1 text-xs uppercase font-bold">Amount</p><p className="font-bold text-text-main">{formatINR(payment.amount)} {payment.currency}</p></div>
              <div><p className="text-text-muted mb-1 text-xs uppercase font-bold">Bank Account</p><p className="font-mono text-text-main">{payment.bank_account_id || 'N/A'}</p></div>
            </div>
          </div>
        </Card>

        <div className="space-y-6">
          <Card title="Vendor & Approvals">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-text-muted mb-1 text-xs uppercase font-bold">Vendor ID</p><p className="font-mono text-text-main">{payment.vendor_id}</p></div>
              <div><p className="text-text-muted mb-1 text-xs uppercase font-bold">Required Signatures</p><p className="font-bold text-text-main">{payment.required_signatures || 0}</p></div>
              <div className="col-span-2"><p className="text-text-muted mb-1 text-xs uppercase font-bold">Current Status</p><p className="font-bold text-text-main">{payment.status}</p></div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
