import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import Button from '../common/Button';
import { formatINR, formatDate } from '../../utils/formatters';

export default function PaymentTable({ payments }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm whitespace-nowrap">
        <thead className="text-xs text-text-muted uppercase border-b border-navy-border bg-navy-surface-hover">
          <tr>
            <th className="px-4 py-3 font-semibold">Request ID</th>
            <th className="px-4 py-3 font-semibold">Vendor</th>
            <th className="px-4 py-3 font-semibold">Amount</th>
            <th className="px-4 py-3 font-semibold">Invoice</th>
            <th className="px-4 py-3 font-semibold">PO</th>
            <th className="px-4 py-3 font-semibold">Risk</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Required Approval</th>
            <th className="px-4 py-3 font-semibold">Created</th>
            <th className="px-4 py-3 font-semibold">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-navy-border">
          {payments.map(p => (
            <tr key={p.id} className="hover:bg-navy-border/20 transition-colors">
              <td className="px-4 py-3 font-medium text-text-main">{p.id}</td>
              <td className="px-4 py-3">{p.vendor}</td>
              <td className="px-4 py-3 font-medium">{formatINR(p.amount)}</td>
              <td className="px-4 py-3 text-text-muted">{p.invoiceId}</td>
              <td className="px-4 py-3 text-text-muted">{p.poId}</td>
              <td className="px-4 py-3">
                <Link to={`/risk/${p.id}`} className="hover:opacity-80 transition-opacity" title="View Risk Analysis">
                  <Badge status={p.riskLevel} />
                </Link>
              </td>
              <td className="px-4 py-3"><Badge status={p.status} /></td>
              <td className="px-4 py-3 text-text-muted">{p.requiredApproval}</td>
              <td className="px-4 py-3 text-text-muted">{formatDate(p.createdAt)}</td>
              <td className="px-4 py-3">
                <Link to={`/payments/${p.id}`}>
                  <Button variant="secondary" className="px-3 py-1.5 text-xs">View</Button>
                </Link>
              </td>
            </tr>
          ))}
          {payments.length === 0 && (
            <tr>
              <td colSpan="10" className="px-4 py-8 text-center text-text-muted">
                No payment requests found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
