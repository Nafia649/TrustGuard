import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Payments from './pages/Payments';
import NewPayment from './pages/NewPayment';
import PaymentDetails from './pages/PaymentDetails';
import RiskAnalysis from './pages/RiskAnalysis';
import PaymentApproval from './pages/PaymentApproval';
import InvoiceUpload from './pages/InvoiceUpload';
import Placeholder from './pages/Placeholder';

import Approvals from './pages/Approvals';
import Ledger from './pages/Ledger';
import PolicySettings from './pages/PolicySettings';
import AnalystReview from './pages/AnalystReview';
import AuditLog from './pages/AuditLog';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="invoices/upload" element={<InvoiceUpload />} />
          <Route path="payments" element={<Payments />} />
          <Route path="payments/new" element={<NewPayment />} />
          <Route path="payments/:id" element={<PaymentDetails />} />
          <Route path="payments/:id/approve" element={<PaymentApproval />} />
          <Route path="risk" element={<Placeholder title="Risk Analysis Dashboard" />} />
          <Route path="risk/:id" element={<RiskAnalysis />} />
          <Route path="approval" element={<Approvals />} />
          <Route path="analyst" element={<AnalystReview />} />
          <Route path="policy" element={<PolicySettings />} />
          <Route path="ledger" element={<Ledger />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
