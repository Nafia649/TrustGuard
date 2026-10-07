import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card from '../components/common/Card';
import { getPayments } from '../api/paymentApi';
import { formatINR } from '../utils/formatters';
import { ShieldCheck } from 'lucide-react';

export default function Approvals() {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPayments().then(data => {
      // Filter payments that need approval or are on hold
      const requiresApproval = data.filter(p => 
        (p.routing_tier === 'ONE_SIGNATURE' || p.routing_tier === 'TWO_SIGNATURES' || p.routing_tier === 'HOLD') && 
        p.status !== 'RELEASED' && p.status !== 'AUTHORIZED'
      );
      setPayments(requiresApproval);
    }).catch(err => {
      console.error(err);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-8 text-center text-text-muted">Loading approvals...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-main">Pending Approvals</h1>
        <p className="text-sm text-text-muted mt-1">Review and authorize payments that require manual oversight.</p>
      </div>
      
      {payments.length === 0 ? (
        <Card className="p-12 text-center border-dashed border-navy-border">
          <ShieldCheck className="w-12 h-12 text-success mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-medium text-text-muted">All caught up</h3>
          <p className="text-sm text-text-muted mt-1">There are no payments currently requiring your approval.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {payments.map(payment => {
            const isHold = payment.routing_tier === 'HOLD';
            const riskColor = payment.risk_score >= 90 ? 'text-danger' : payment.risk_score >= 50 ? 'text-warning' : 'text-success';
            
            return (
              <Card key={payment.request_id} className="p-5 hover:border-primary/50 transition-colors flex flex-col">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-sm font-bold text-primary">{payment.request_id}</span>
                      {isHold && <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-danger/20 text-danger border border-danger/30">ON HOLD</span>}
                      {!isHold && <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-warning/20 text-warning border border-warning/30">{payment.routing_tier}</span>}
                    </div>
                    <h3 className="text-lg font-bold text-text-main">{formatINR(payment.amount)}</h3>
                  </div>
                  <div className="text-right">
                    <div className={`text-2xl font-bold ${riskColor}`}>{Math.round(payment.risk_score || 0)}</div>
                    <div className="text-xs text-text-muted">Risk Score</div>
                  </div>
                </div>
                
                <div className="space-y-2 mb-6 flex-1 text-sm">
                  <div className="flex justify-between border-b border-navy-border/50 pb-1">
                    <span className="text-text-muted">Vendor</span>
                    <span className="font-medium text-text-main">{payment.vendor_id}</span>
                  </div>
                  <div className="flex justify-between border-b border-navy-border/50 pb-1">
                    <span className="text-text-muted">Invoice</span>
                    <span className="font-medium text-text-main">{payment.invoice_id}</span>
                  </div>
                  <div className="flex justify-between border-b border-navy-border/50 pb-1">
                    <span className="text-text-muted">PO</span>
                    <span className="font-medium text-text-main">{payment.po_id || 'None'}</span>
                  </div>
                  <div className="flex justify-between pt-1">
                    <span className="text-text-muted">Required Sigs</span>
                    <span className="font-bold text-text-main">{payment.required_signatures || 0}</span>
                  </div>
                </div>
                
                <Link 
                  to={`/payments/${payment.request_id}/approve`}
                  className="w-full block text-center py-2.5 rounded bg-navy-border text-text-main font-medium hover:bg-primary hover:text-navy-bg transition-colors"
                >
                  Review & Authorize
                </Link>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
