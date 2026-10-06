import { useState, useEffect } from 'react';
import { getPayments, releasePayment } from '../api/paymentApi';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import { formatINR, formatDate } from '../utils/formatters';
import { BookOpen, CheckCircle, Clock, AlertTriangle } from 'lucide-react';

export default function Ledger() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [releasingId, setReleasingId] = useState(null);
  const [releaseError, setReleaseError] = useState(null);

  const loadLedger = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPayments();
      // Sort by timestamp descending
      data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setPayments(data);
    } catch (err) {
      setError(err.message || 'Failed to load ledger');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLedger();
  }, []);

  const handleRelease = async (requestId) => {
    try {
      setReleasingId(requestId);
      setReleaseError(null);
      await releasePayment(requestId);
      // Refresh ledger after successful release
      await loadLedger();
    } catch (err) {
      setReleaseError({ id: requestId, message: err.message });
    } finally {
      setReleasingId(null);
    }
  };

  if (loading && payments.length === 0) {
    return <div className="p-12 text-center text-text-muted">Loading immutable ledger entries...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-main flex items-center">
            <BookOpen className="w-6 h-6 mr-3 text-primary" />
            Mock Settlement Ledger
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Authoritative financial ledger reflecting final payment obligations.
          </p>
        </div>
        <button 
          onClick={loadLedger}
          className="text-xs bg-navy-border hover:bg-primary/20 text-text-main px-3 py-1.5 rounded transition-colors"
        >
          Refresh Ledger
        </button>
      </div>
      
      {error && (
        <div className="bg-danger/10 border border-danger/30 text-danger p-4 rounded-md">
          <p className="font-bold">Error loading ledger</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {payments.length === 0 && !loading && !error ? (
        <Card className="p-12 text-center border-dashed border-navy-border">
          <BookOpen className="w-12 h-12 text-text-muted mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-medium text-text-muted">Ledger Empty</h3>
          <p className="text-sm text-text-muted mt-1">No payment requests have been logged yet.</p>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm whitespace-nowrap">
              <thead className="text-xs text-text-muted uppercase border-b border-navy-border bg-navy-surface-hover">
                <tr>
                  <th className="px-5 py-4 font-semibold">Payment ID</th>
                  <th className="px-5 py-4 font-semibold">Status</th>
                  <th className="px-5 py-4 font-semibold">Timestamp</th>
                  <th className="px-5 py-4 font-semibold">Beneficiary</th>
                  <th className="px-5 py-4 font-semibold">Amount</th>
                  <th className="px-5 py-4 font-semibold">Invoice Ref</th>
                  <th className="px-5 py-4 font-semibold">Settlement Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-border/50">
                {payments.map(p => {
                  const isReleased = p.status === 'RELEASED';
                  const isAuthorized = p.status === 'AUTHORIZED';
                  
                  return (
                    <tr key={p.request_id} className={`hover:bg-navy-border/20 transition-colors ${isReleased ? 'bg-success/5' : ''}`}>
                      <td className="px-5 py-4 font-mono font-medium text-text-main">{p.request_id}</td>
                      <td className="px-5 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                          isReleased ? 'bg-success/10 text-success border-success/30' :
                          isAuthorized ? 'bg-primary/10 text-primary border-primary/30' :
                          'bg-warning/10 text-warning border-warning/30'
                        }`}>
                          {p.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-text-muted text-xs">{formatDate(p.timestamp)}</td>
                      <td className="px-5 py-4">
                        <div className="font-medium text-text-main">{p.vendor_id}</div>
                        <div className="text-xs text-text-muted">{p.bank_account}</div>
                      </td>
                      <td className="px-5 py-4 font-bold text-text-main">{formatINR(p.amount)} {p.currency}</td>
                      <td className="px-5 py-4 text-text-muted font-mono text-xs">{p.invoice_id}</td>
                      <td className="px-5 py-4">
                        {isReleased && (
                          <div className="flex items-center text-success text-xs font-bold">
                            <CheckCircle className="w-4 h-4 mr-1" />
                            SETTLED
                          </div>
                        )}
                        
                        {isAuthorized && (
                          <div className="flex flex-col gap-2">
                            <button
                              onClick={() => handleRelease(p.request_id)}
                              disabled={releasingId === p.request_id}
                              className="bg-primary hover:bg-primary-hover text-navy-bg font-bold py-1.5 px-4 rounded transition-colors text-xs disabled:opacity-50"
                            >
                              {releasingId === p.request_id ? 'Releasing...' : 'Release to Bank'}
                            </button>
                            {releaseError && releaseError.id === p.request_id && (
                              <div className="flex items-start text-[10px] text-danger max-w-[200px] whitespace-normal leading-tight">
                                <AlertTriangle className="w-3 h-3 mr-1 shrink-0 mt-0.5" />
                                {releaseError.message}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {!isReleased && !isAuthorized && (
                          <div className="flex items-center text-text-muted/50 text-xs font-medium">
                            <Clock className="w-4 h-4 mr-1" />
                            Awaiting Auth
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
