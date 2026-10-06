import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Payments from './pages/Payments';
import NewPayment from './pages/NewPayment';
import PaymentDetails from './pages/PaymentDetails';
import RiskAnalysis from './pages/RiskAnalysis';
import Placeholder from './pages/Placeholder';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="payments" element={<Payments />} />
          <Route path="payments/new" element={<NewPayment />} />
          <Route path="payments/:id" element={<PaymentDetails />} />
          <Route path="payments/:id/approve" element={<Placeholder title="Approve Payment" />} />
          <Route path="risk" element={<Placeholder title="Risk Analysis Dashboard" />} />
          <Route path="risk/:id" element={<RiskAnalysis />} />
          <Route path="approvals" element={<Placeholder title="Approvals" />} />
          <Route path="analyst" element={<Placeholder title="Analyst Holds" />} />
          <Route path="policy" element={<Placeholder title="Policy Settings" />} />
          <Route path="ledger" element={<Placeholder title="Mock Ledger" />} />
          <Route path="audit" element={<Placeholder title="Audit Log" />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
