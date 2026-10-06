import { Link } from 'react-router-dom';
import Card from '../components/common/Card';
import Badge from '../components/common/Badge';
import { CreditCard, Clock, AlertTriangle, PauseCircle, CheckCircle, XCircle } from 'lucide-react';

import { mockPayments } from '../data/mockPayments';
import { formatINR } from '../utils/formatters';

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-main">Payment Security Dashboard</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wider">Total Payments</p>
              <h2 className="text-3xl font-bold mt-2">24</h2>
              <p className="text-xs text-text-muted mt-1">Today</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
              <CreditCard className="text-primary w-5 h-5" />
            </div>
          </div>
        </Card>
        
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wider">Pending Approvals</p>
              <h2 className="text-3xl font-bold mt-2">5</h2>
              <p className="text-xs text-warning mt-1">Needs review</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-warning/10 flex items-center justify-center">
              <Clock className="text-warning w-5 h-5" />
            </div>
          </div>
        </Card>
        
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-muted text-xs font-semibold uppercase tracking-wider">Payments on Hold</p>
              <h2 className="text-3xl font-bold mt-2">3</h2>
              <p className="text-xs text-danger mt-1">High risk</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center">
              <PauseCircle className="text-danger w-5 h-5" />
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card title="Recent Payments" action={<Link to="/payments" className="text-primary text-sm hover:underline">View all →</Link>}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="text-xs text-text-muted uppercase border-b border-navy-border">
                  <tr>
                    <th className="pb-3 font-semibold">Request ID</th>
                    <th className="pb-3 font-semibold">Vendor</th>
                    <th className="pb-3 font-semibold">Amount</th>
                    <th className="pb-3 font-semibold">Risk</th>
                    <th className="pb-3 font-semibold">Status</th>
                    <th className="pb-3 font-semibold">Required Approval</th>
                    <th className="pb-3 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-border">
                  {mockPayments.slice(0, 5).map(p => (
                    <tr key={p.id} className="hover:bg-navy-border/20 transition-colors">
                      <td className="py-3 font-medium text-text-main">{p.id}</td>
                      <td className="py-3">{p.vendor}</td>
                      <td className="py-3">{formatINR(p.amount)}</td>
                      <td className="py-3">
                        <Link to={`/risk/${p.id}`} className="hover:opacity-80 transition-opacity" title="View Risk Analysis">
                          <Badge status={p.riskLevel} />
                        </Link>
                      </td>
                      <td className="py-3"><Badge status={p.status} /></td>
                      <td className="py-3 text-text-muted">{p.requiredApproval}</td>
                      <td className="py-3">
                        <Link to={`/payments/${p.id}`} className="text-primary hover:underline">View</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          
          <Card title="System Flow">
            <div className="flex flex-col space-y-2">
              <div className="flex items-center text-sm"><CheckCircle className="w-4 h-4 text-success mr-2"/> Payment Request</div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm"><CheckCircle className="w-4 h-4 text-success mr-2"/> Three-Way Match</div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm"><CheckCircle className="w-4 h-4 text-success mr-2"/> Risk Analysis</div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm"><AlertTriangle className="w-4 h-4 text-warning mr-2"/> Risk-Based Routing</div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm"><Clock className="w-4 h-4 text-text-muted mr-2"/> REALKEY Approval</div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm text-text-muted"><div className="w-4 h-4 rounded-full border-2 border-text-muted mr-2"></div> Verification</div>
              <div className="ml-2 w-0.5 h-3 bg-navy-border"></div>
              <div className="flex items-center text-sm text-text-muted"><div className="w-4 h-4 rounded-full border-2 border-text-muted mr-2"></div> Mock Ledger</div>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Risk Overview">
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Low Risk</span>
                  <span className="text-success">17</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-success h-1.5 rounded-full" style={{ width: '70%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Medium Risk</span>
                  <span className="text-warning">4</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-warning h-1.5 rounded-full" style={{ width: '20%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>High Risk</span>
                  <span className="text-danger">2</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-danger h-1.5 rounded-full" style={{ width: '8%' }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Critical</span>
                  <span className="text-danger font-bold">1</span>
                </div>
                <div className="w-full bg-navy-border rounded-full h-1.5">
                  <div className="bg-danger h-1.5 rounded-full" style={{ width: '2%' }}></div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
