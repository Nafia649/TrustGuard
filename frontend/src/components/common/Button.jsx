import clsx from 'clsx';

const variants = {
  primary: 'bg-primary text-navy-bg hover:bg-primary/90',
  secondary: 'bg-navy-surface text-text-main border border-navy-border hover:bg-navy-border/50',
  danger: 'bg-danger/10 text-danger border border-danger/20 hover:bg-danger/20',
};

export default function Button({ children, variant = 'primary', className, ...props }) {
  return (
    <button
      className={clsx(
        'px-4 py-2 rounded-md font-medium text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50',
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
