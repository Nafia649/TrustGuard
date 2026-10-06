import { useNavigate } from 'react-router-dom';
import Card from '../components/common/Card';
import Button from '../components/common/Button';
import PaymentTable from '../components/payment/PaymentTable';
import { mockPayments } from '../data/mockPayments';

export default function Payments() {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-main">Payment Requests</h1>
          <p className="text-sm text-text-muted mt-1">Review and manage payment authorization requests.</p>
        </div>
        <Button onClick={() => navigate('/payments/new')}>+ New Payment</Button>
      </div>

      <Card>
        <PaymentTable payments={mockPayments} />
      </Card>
    </div>
  );
}
