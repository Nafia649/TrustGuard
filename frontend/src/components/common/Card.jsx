import clsx from 'clsx';

export default function Card({ children, className, title, action }) {
  return (
    <div className={clsx('bg-navy-surface border border-navy-border rounded-xl flex flex-col', className)}>
      {(title || action) && (
        <div className="px-5 py-4 border-b border-navy-border flex justify-between items-center">
          {title && <h3 className="font-semibold text-text-main">{title}</h3>}
          {action && <div>{action}</div>}
        </div>
      )}
      <div className="p-5 flex-1">
        {children}
      </div>
    </div>
  );
}
