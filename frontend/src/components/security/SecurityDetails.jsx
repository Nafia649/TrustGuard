import { useState } from 'react';
import { ChevronDown, ChevronUp, ShieldCheck } from 'lucide-react';

export default function SecurityDetails() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-8 border border-navy-border rounded-lg overflow-hidden">
      <button 
        onClick={() => setExpanded(!expanded)} 
        className="w-full flex items-center justify-between p-4 bg-navy-surface hover:bg-navy-surface-hover transition-colors focus:outline-none"
      >
        <span className="flex items-center text-sm font-semibold text-text-main">
          <ShieldCheck className="w-4 h-4 mr-2 text-primary" />
          Why does REALKEY matter?
        </span>
        {expanded ? <ChevronUp className="w-4 h-4 text-text-muted" /> : <ChevronDown className="w-4 h-4 text-text-muted" />}
      </button>
      
      {expanded && (
        <div className="p-4 bg-navy-bg text-sm text-text-muted space-y-3 border-t border-navy-border">
          <p>
            <strong className="text-text-main">REALKEY binds your approval to the exact payment details.</strong>
          </p>
          <p>
            Your approval is not just an approval of the vendor. It is a cryptographic approval of this exact payment, including the amount, bank account, invoice, PO, policy and routing information.
          </p>
          <p>
            If any critical payment information changes after your approval (e.g., an attacker modifies the bank account in the database), the approved fingerprint will no longer match the payment being released, and the transaction will be automatically blocked.
          </p>
        </div>
      )}
    </div>
  );
}
