import React, { useState, useEffect } from 'react';
import { getPayments, getPayment, submitAnalystDecision } from '../api/paymentApi';
import { ShieldAlert, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';
import Card from '../components/common/Card';
import { formatINR } from '../utils/formatters';

export default function AnalystReview() {
  const [payments, setPayments] = useState([]);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const fetchHolds = async () => {
    try {
      setLoading(true);
      const data = await getPayments('ON_HOLD');
      setPayments(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHolds();
  }, []);

  const handleSelect = async (id) => {
    try {
      const data = await getPayment(id);
      setSelectedPayment(data);
      setError(null);
      setSuccess(null);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDecision = async (decision) => {
    if (!selectedPayment) return;
    
    try {
      setActionLoading(true);
      setError(null);
      await submitAnalystDecision(selectedPayment.request_id, decision);
      setSuccess(`Payment successfully marked as ${decision}`);
      setSelectedPayment(null);
      await fetchHolds();
    } catch (err) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <ShieldAlert className="h-8 w-8 text-danger" />
          <h1 className="text-2xl font-bold text-text-main">Analyst Review</h1>
        </div>
        <p className="text-sm text-text-muted">Review payments that have been routed to ON HOLD.</p>
      </div>

      {error && (
        <div className="p-4 bg-danger/10 text-danger rounded-md border border-danger/20 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {error}
        </div>
      )}
      
      {success && (
        <div className="p-4 bg-success/10 text-success rounded-md border border-success/20 flex items-center gap-2">
          <CheckCircle className="w-5 h-5" />
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Queue List */}
        <div className="lg:col-span-1 bg-navy-surface rounded-xl border border-navy-border flex flex-col h-[600px]">
          <div className="p-4 border-b border-navy-border flex justify-between items-center bg-navy-bg/50">
            <h2 className="font-semibold text-text-main">Held Payments</h2>
            <span className="bg-danger/20 text-danger text-[10px] font-bold px-2 py-0.5 rounded border border-danger/30">
              {payments.length} pending
            </span>
          </div>
          
          <div className="divide-y divide-navy-border/50 overflow-y-auto flex-1">
            {loading ? (
              <div className="p-8 text-center text-text-muted">Loading queue...</div>
            ) : payments.length === 0 ? (
              <div className="p-8 text-center text-text-muted">No payments on hold.</div>
            ) : (
              payments.map(p => (
                <div 
                  key={p.request_id}
                  onClick={() => handleSelect(p.request_id)}
                  className={`p-4 cursor-pointer hover:bg-navy-border/30 transition-colors ${selectedPayment?.request_id === p.request_id ? 'bg-primary/5 border-l-4 border-primary' : 'border-l-4 border-transparent'}`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-mono text-sm font-bold text-primary">{p.request_id}</span>
                    <span className="text-xs font-bold text-danger">Risk {p.risk_score}</span>
                  </div>
                  <div className="text-sm text-text-muted mb-2">Vendor: {p.vendor_id}</div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">{new Date(p.timestamp).toLocaleDateString()}</span>
                    <span className="bg-danger/20 text-danger px-2 py-0.5 rounded font-bold border border-danger/30">{p.status}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Payment Details */}
        <div className="lg:col-span-2">
          {selectedPayment ? (
            <div className="bg-navy-surface rounded-xl border border-navy-border">
              <div className="p-6">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-2xl font-bold text-text-main mb-1">{selectedPayment.vendor_id}</h2>
                    <p className="text-text-muted font-mono text-sm">Invoice: {selectedPayment.invoice_id} | Payment: {selectedPayment.request_id}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-text-main">
                      {formatINR ? formatINR(selectedPayment.amount) : `${selectedPayment.amount.toLocaleString()} ${selectedPayment.currency}`}
                    </div>
                    <p className="text-sm text-text-muted mt-1">PO: {selectedPayment.po_id || 'None'}</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-danger/10 p-4 rounded-lg border border-danger/20 text-center">
                    <div className="text-sm text-danger font-medium mb-1">Risk Score</div>
                    <div className="text-3xl font-bold text-danger">{selectedPayment.risk_score}</div>
                  </div>
                  <div className="bg-warning/10 p-4 rounded-lg border border-warning/20 text-center">
                    <div className="text-sm text-warning font-medium mb-1">Routing Tier</div>
                    <div className="text-xl font-bold text-warning mt-2">{selectedPayment.routing_tier}</div>
                  </div>
                  <div className="bg-navy-border/30 p-4 rounded-lg border border-navy-border text-center">
                    <div className="text-sm text-text-muted font-medium mb-1">Status</div>
                    <div className="text-xl font-bold text-text-main mt-2">{selectedPayment.status}</div>
                  </div>
                </div>

                <h3 className="text-lg font-semibold text-text-main mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-warning" />
                  Top Risk Factors (SHAP)
                </h3>
                <ul className="space-y-2 mb-6 bg-navy-bg border border-navy-border rounded-lg p-4">
                  {selectedPayment.risk_reasons ? (
                    JSON.parse(selectedPayment.risk_reasons).map((reason, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-text-muted">
                        <span className="text-danger mt-0.5">•</span>
                        {reason}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-text-muted">No ML explanation available.</li>
                  )}
                </ul>
                
                <h3 className="text-lg font-semibold text-text-main mb-3 flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-primary" />
                  Analyst Decision
                </h3>
                
                <div className="flex gap-4">
                  <button
                    onClick={() => handleDecision('ALLOW')}
                    disabled={actionLoading}
                    className="flex-1 bg-success hover:bg-success/80 text-navy-bg font-bold py-3 px-4 rounded transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <CheckCircle className="h-5 w-5" />
                    Allow & Route for Approval
                  </button>
                  <button
                    onClick={() => handleDecision('BLOCK')}
                    disabled={actionLoading}
                    className="flex-1 bg-danger hover:bg-danger/80 text-white font-bold py-3 px-4 rounded transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <XCircle className="h-5 w-5" />
                    Block / Reject Payment
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-navy-surface rounded-xl border border-navy-border h-[600px] flex items-center justify-center text-text-muted flex-col gap-3">
              <Clock className="h-12 w-12 opacity-50" />
              <p>Select a payment from the queue to review</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
