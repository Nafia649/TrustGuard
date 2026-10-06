import Card from '../components/common/Card';

export default function Placeholder({ title }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-text-main">{title}</h1>
      <Card>
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-16 h-16 bg-navy-border rounded-full flex items-center justify-center mb-4 text-text-muted">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          </div>
          <h2 className="text-xl font-semibold mb-2">Coming in a later implementation phase.</h2>
          <p className="text-text-muted max-w-md">
            This feature is currently under development and will be available soon.
          </p>
        </div>
      </Card>
    </div>
  );
}
