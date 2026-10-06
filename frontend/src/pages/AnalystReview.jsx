import React, { useState, useEffect } from 'react';
import { getPayments, getPayment, submitAnalystDecision } from '../api/paymentApi';
import { ShieldAlert, CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';

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
    <div className="max-w-6xl mx-auto py-8 px-4">
      <div className="flex items-center gap-3 mb-8">
        <ShieldAlert className="h-8 w-8 text-red-600" />
        <h1 className="text-3xl font-bold text-gray-900">Analyst Review</h1>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-md border border-red-200">
          {error}
        </div>
      )}
      
      {success && (
        <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-md border border-green-200">
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Queue List */}
        <div className="lg:col-span-1 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
            <h2 className="font-semibold text-gray-700">Held Payments</h2>
            <span className="bg-red-100 text-red-800 text-xs font-medium px-2.5 py-0.5 rounded-full">
              {payments.length} pending
            </span>
          </div>
          
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
            {loading ? (
              <div className="p-8 text-center text-gray-500">Loading queue...</div>
            ) : payments.length === 0 ? (
              <div className="p-8 text-center text-gray-500">No payments on hold.</div>
            ) : (
              payments.map(p => (
                <div 
                  key={p.request_id}
                  onClick={() => handleSelect(p.request_id)}
                  className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${selectedPayment?.request_id === p.request_id ? 'bg-blue-50 border-l-4 border-blue-600' : 'border-l-4 border-transparent'}`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium text-gray-900">{p.invoice_id}</span>
                    <span className="text-sm font-bold text-red-600">Risk {p.risk_score}</span>
                  </div>
                  <div className="text-sm text-gray-600 mb-2">{p.vendor_id}</div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-gray-500">{new Date(p.timestamp).toLocaleDateString()}</span>
                    <span className="bg-red-100 text-red-800 px-2 py-1 rounded">{p.status}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Payment Details */}
        <div className="lg:col-span-2">
          {selectedPayment ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-1">{selectedPayment.vendor_id}</h2>
                    <p className="text-gray-500">Invoice: {selectedPayment.invoice_id} | Payment: {selectedPayment.request_id}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-gray-900">
                      {selectedPayment.amount.toLocaleString()} {selectedPayment.currency}
                    </div>
                    <p className="text-sm text-gray-500">PO: {selectedPayment.po_id || 'None'}</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-red-50 p-4 rounded-lg border border-red-100 text-center">
                    <div className="text-sm text-red-600 font-medium mb-1">Risk Score</div>
                    <div className="text-3xl font-bold text-red-700">{selectedPayment.risk_score}</div>
                  </div>
                  <div className="bg-orange-50 p-4 rounded-lg border border-orange-100 text-center">
                    <div className="text-sm text-orange-600 font-medium mb-1">Routing Tier</div>
                    <div className="text-xl font-bold text-orange-700 mt-2">{selectedPayment.routing_tier}</div>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 text-center">
                    <div className="text-sm text-gray-600 font-medium mb-1">Status</div>
                    <div className="text-xl font-bold text-gray-800 mt-2">{selectedPayment.status}</div>
                  </div>
                </div>

                <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-orange-500" />
                  Top Risk Factors (SHAP)
                </h3>
                <ul className="space-y-2 mb-6 bg-white border border-gray-200 rounded-lg p-4">
                  {selectedPayment.risk_reasons ? (
                    JSON.parse(selectedPayment.risk_reasons).map((reason, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                        <span className="text-red-500 mt-0.5">•</span>
                        {reason}
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-gray-500">No ML explanation available.</li>
                  )}
                </ul>

                <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-blue-500" />
                  Analyst Decision
                </h3>
                
                <div className="flex gap-4">
                  <button
                    onClick={() => handleDecision('ALLOW')}
                    disabled={actionLoading}
                    className="flex-1 bg-green-600 hover:bg-green-700 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <CheckCircle className="h-5 w-5" />
                    Allow & Route for Approval
                  </button>
                  <button
                    onClick={() => handleDecision('BLOCK')}
                    disabled={actionLoading}
                    className="flex-1 bg-red-600 hover:bg-red-700 text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <XCircle className="h-5 w-5" />
                    Block / Reject Payment
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-xl border border-gray-200 h-full min-h-[400px] flex items-center justify-center text-gray-400 flex-col gap-3">
              <Clock className="h-12 w-12" />
              <p>Select a payment from the queue to review</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
