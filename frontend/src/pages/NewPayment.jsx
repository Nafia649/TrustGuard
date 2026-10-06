import { Navigate } from 'react-router-dom';

export default function NewPayment() {
  return <Navigate to="/invoices/upload" replace />;
}
