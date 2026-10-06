import { Bell, User } from 'lucide-react';

export default function Topbar() {
  return (
    <header className="h-16 bg-navy-bg border-b border-navy-border flex items-center justify-between px-6 sticky top-0 z-10 shrink-0">
      <div className="flex items-center md:hidden">
        <span className="text-xl font-bold tracking-wider text-text-main">TRUSTGUARD</span>
      </div>
      <div className="hidden md:flex items-center space-x-4">
        {/* Can be used for page title if passed via context, else empty left side on desktop */}
      </div>
      <div className="flex items-center space-x-6">
        <div className="hidden sm:block">
           <span className="px-3 py-1 text-xs font-semibold bg-navy-surface text-text-muted border border-navy-border rounded-md">
            All risk
          </span>
        </div>
        <div className="flex items-center space-x-3 border-l border-navy-border pl-6">
          <div className="w-8 h-8 rounded-full bg-navy-surface border border-navy-border flex items-center justify-center text-text-muted text-xs font-bold">
            SA
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-medium text-text-main leading-tight">Security Admin</span>
            <span className="text-xs text-text-muted leading-tight">Payment Operations</span>
          </div>
        </div>
      </div>
    </header>
  );
}
