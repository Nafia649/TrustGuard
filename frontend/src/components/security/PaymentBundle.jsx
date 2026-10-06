import { useState } from 'react';
import Card from '../common/Card';
import { formatINR } from '../../utils/formatters';
import { ChevronDown, ChevronUp, Lock } from 'lucide-react';

export default function PaymentBundle({ approval }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card className="border-primary/30">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-text-main flex items-center">
          <Lock className="w-5 h-5 mr-2 text-primary" />
          Payment being approved
        </h3>
      </div>
      
      <div className="bg-navy-bg p-6 rounded-lg border border-navy-border space-y-4">
        <div className="flex justify-between items-end border-b border-navy-border pb-4">
          <div>
            <p className="text-text-muted text-sm mb-1">Vendor</p>
            <p className="text-xl font-medium text-text-main">{approval.vendor}</p>
          </div>
          <div className="text-right">
            <p className="text-text-muted text-sm mb-1">Amount</p>
            <p className="text-3xl font-bold text-text-main">{formatINR(approval.amount)}</p>
          </div>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
          <div>
            <p className="text-text-muted text-xs uppercase mb-1">Bank Account</p>
            <p className="font-medium text-text-main">{approval.bankAccount}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs uppercase mb-1">Invoice ID</p>
            <p className="font-medium text-text-main">{approval.invoiceId}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs uppercase mb-1">PO ID</p>
            <p className="font-medium text-text-main">{approval.poId}</p>
          </div>
          <div>
            <p className="text-text-muted text-xs uppercase mb-1">Risk Score</p>
            <p className="font-medium text-text-main">{approval.riskScore} ({approval.riskLevel})</p>
          </div>
        </div>
      </div>

      <div className="mt-4">
        <button 
          onClick={() => setExpanded(!expanded)} 
          className="flex items-center text-sm text-primary hover:text-primary/80 focus:outline-none"
        >
          {expanded ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
          View exact payment bundle
        </button>
        
        {expanded && (
          <div className="mt-3 p-4 bg-navy-bg border border-navy-border rounded-md text-xs font-mono text-text-muted overflow-x-auto">
            <pre>
{JSON.stringify({
  vendor_id: approval.vendorId,
  amount: approval.amount,
  currency: approval.currency,
  bank_account: approval.bankAccount,
  invoice_id: approval.invoiceId,
  po_id: approval.poId,
  nonce: approval.nonce,
  expiry: approval.expiry,
  policy_version: approval.policyVersion,
  routing_tier: approval.routingTier
}, null, 2)}
            </pre>
            <div className="mt-4 pt-4 border-t border-navy-border/50">
              <p className="text-text-main mb-1">Payment Fingerprint</p>
              <p className="text-warning font-bold tracking-wider">DEMO: {approval.mockFingerprint}</p>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
