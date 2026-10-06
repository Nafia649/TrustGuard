import Badge from '../common/Badge';
import { formatINR } from '../../utils/formatters';

export default function PaymentSummary({ payment }) {
  const overallMatchBadge = () => {
    if (payment.threeWayMatch.overall_match === 'MATCHED') return <Badge status="APPROVED">✓ MATCHED</Badge>;
    if (payment.threeWayMatch.overall_match === 'PARTIAL MATCH') return <Badge status="PENDING">⚠ PARTIAL MATCH</Badge>;
    return <Badge status="BLOCKED">✕ MISMATCH</Badge>;
  };

  return (
    <div className="flex flex-col md:flex-row justify-between md:items-center gap-6">
      <div>
        <p className="text-text-muted text-sm uppercase tracking-wider mb-1">Payment Status</p>
        <div className="flex items-center space-x-4">
          <h2 className="text-3xl font-bold text-text-main">{formatINR(payment.amount)}</h2>
          <span className="text-xl text-text-muted">|</span>
          <span className="text-xl text-text-main">{payment.vendor}</span>
        </div>
        <div className="mt-3 flex items-center space-x-2">
          {overallMatchBadge()}
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-8">
        <div>
          <p className="text-xs text-text-muted uppercase mb-1">Risk Analysis</p>
          <Badge status={payment.riskLevel} />
        </div>
        <div>
          <p className="text-xs text-text-muted uppercase mb-1">Routing</p>
          <div className="text-sm font-medium text-text-main">{payment.requiredApproval}</div>
        </div>
        <div>
          <p className="text-xs text-text-muted uppercase mb-1">Approval</p>
          <Badge status={payment.status} />
        </div>
      </div>
    </div>
  );
}
