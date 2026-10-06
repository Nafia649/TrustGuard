import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import { getPayments } from '../api/paymentApi';
import { formatINR } from '../utils/formatters';
import { ArrowRight, AlertTriangle } from 'lucide-react';

export default function Payments() {
  const navigate = useNavigate();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        setLoading(true);
        const data = await getPayments();
        setPayments(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-main">Payment Requests</h1>
          <p className="text-sm text-text-muted mt-1">Review and manage payment authorization requests.</p>
        </div>
        <Button onClick={() => navigate('/invoices/upload')}>Upload Invoice</Button>
      </div>

      {error && (
        <div className="p-4 bg-danger/10 text-danger rounded-md border border-danger/20 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          {error}
        </div>
      )}

      <Card>
        <div className="overflow-x-auto min-h-[400px]">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="text-xs text-text-muted uppercase border-b border-navy-border bg-navy-bg/50">
              <tr>
                <th className="py-3 px-4 font-bold">Request ID</th>
                <th className="py-3 px-4 font-bold">Invoice</th>
                <th className="py-3 px-4 font-bold">Vendor</th>
                <th className="py-3 px-4 font-bold">Amount</th>
                <th className="py-3 px-4 font-bold">Risk Score</th>
                <th className="py-3 px-4 font-bold">Status</th>
                <th className="py-3 px-4 font-bold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-border/50">
              {loading ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-text-muted">Loading payments...</td>
                </tr>
              ) : payments.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-text-muted">No payments found.</td>
                </tr>
              ) : (
                payments.map((p) => (
                  <tr key={p.request_id} className="hover:bg-navy-bg/50 transition-colors">
                    <td className="py-3 px-4 font-mono text-primary font-bold">{p.request_id}</td>
                    <td className="py-3 px-4 text-text-muted font-mono">{p.invoice_id}</td>
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
                    <td className="py-3 px-4 text-right">
                      <Link to={`/payments/${p.request_id}`} className="text-secondary hover:underline text-xs font-bold inline-flex items-center gap-1">
                        View <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
