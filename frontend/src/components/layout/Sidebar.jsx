import { NavLink } from 'react-router-dom';
import { LayoutDashboard, FileText, Activity, CheckSquare, Clock, Settings, BookOpen, ShieldCheck, FileUp } from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Upload Invoice', path: '/invoices/upload', icon: FileUp },
  { name: 'Payment Requests', path: '/payments', icon: FileText },
  { name: 'Risk Analysis', path: '/risk', icon: Activity },
  { name: 'Approvals', path: '/approval', icon: CheckSquare },
  { name: 'Analyst Holds', path: '/analyst', icon: Clock },
  { name: 'Policy Settings', path: '/policy', icon: Settings },
  { name: 'Mock Ledger', path: '/ledger', icon: BookOpen },
  { name: 'Audit Log', path: '/audit', icon: ShieldCheck },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-navy-surface border-r border-navy-border h-full flex-col hidden md:flex shrink-0">
      <div className="h-16 flex items-center px-6 border-b border-navy-border shrink-0">
        <ShieldCheck className="text-primary w-6 h-6 mr-2" />
        <span className="text-xl font-bold tracking-wider">TRUSTGUARD</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-3">
          {navItems.map((item) => (
            <li key={item.name}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center px-3 py-2.5 rounded-md transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'text-text-muted hover:bg-navy-border/50 hover:text-text-main border border-transparent'
                  )
                }
              >
                <item.icon className="w-5 h-5 mr-3" />
                <span className="font-medium text-sm">{item.name}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="p-4 border-t border-navy-border shrink-0">
        <div className="text-xs text-text-muted font-medium mb-1">System Settings</div>
        <div className="text-xs text-text-muted mt-2">DEMO / PROOF OF CONCEPT</div>
      </div>
    </aside>
  );
}
