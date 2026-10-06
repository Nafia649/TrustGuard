import Card from '../common/Card';
import { CheckCircle, XCircle } from 'lucide-react';

export default function ThreeWayMatch({ threeWayMatch, poId, invoiceId }) {
  const renderMatchIcon = (isMatch) => {
    return isMatch ? <CheckCircle className="w-5 h-5 text-success" /> : <XCircle className="w-5 h-5 text-danger" />;
  };

  return (
    <div>
      <h3 className="text-lg font-semibold text-text-main mb-4">Three-Way Match</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className={threeWayMatch.po_match ? 'border-success/30' : 'border-danger/30'}>
          <div className="flex justify-between items-start mb-4">
            <h4 className="font-semibold text-text-main">Purchase Order</h4>
            {renderMatchIcon(threeWayMatch.po_match)}
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-text-muted">PO ID</span><span>{poId}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Status</span><span className={threeWayMatch.po_match ? 'text-success' : 'text-danger'}>{threeWayMatch.po_match ? 'Valid' : 'Invalid/Missing'}</span></div>
          </div>
        </Card>
        
        <Card className={threeWayMatch.grn_match ? 'border-success/30' : 'border-danger/30'}>
          <div className="flex justify-between items-start mb-4">
            <h4 className="font-semibold text-text-main">Goods Receipt</h4>
            {renderMatchIcon(threeWayMatch.grn_match)}
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-text-muted">Status</span><span className={threeWayMatch.grn_match ? 'text-success' : 'text-danger'}>{threeWayMatch.grn_match ? 'Received' : 'Not Received'}</span></div>
          </div>
        </Card>

        <Card className={threeWayMatch.invoice_match ? 'border-success/30' : 'border-danger/30'}>
          <div className="flex justify-between items-start mb-4">
            <h4 className="font-semibold text-text-main">Invoice</h4>
            {renderMatchIcon(threeWayMatch.invoice_match)}
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-text-muted">Invoice ID</span><span>{invoiceId}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Status</span><span className={threeWayMatch.invoice_match ? 'text-success' : 'text-danger'}>{threeWayMatch.invoice_match ? 'Matched' : 'Mismatch'}</span></div>
          </div>
        </Card>
      </div>
    </div>
  );
}
