import clsx from 'clsx';

const variants = {
  success: 'bg-success/10 text-success border border-success/20',
  warning: 'bg-warning/10 text-warning border border-warning/20',
  danger: 'bg-danger/10 text-danger border border-danger/20',
  primary: 'bg-primary/10 text-primary border border-primary/20',
  secondary: 'bg-navy-border/50 text-text-muted border border-navy-border',
};

// Map semantic statuses to variants
const statusMap = {
  LOW: 'success',
  MEDIUM: 'warning',
  HIGH: 'danger',
  CRITICAL: 'danger',
  APPROVED: 'success',
  PENDING: 'warning',
  HOLD: 'danger',
  BLOCKED: 'danger',
  AUTO: 'primary',
  '1 SIGNATURE': 'warning',
  '2 SIGNATURES': 'danger',
};

export default function Badge({ children, status, variant, className }) {
  const selectedVariant = variant || statusMap[status?.toUpperCase()] || 'secondary';
  return (
    <span className={clsx('px-2 py-0.5 text-xs font-semibold rounded-full', variants[selectedVariant], className)}>
      {children || status}
    </span>
  );
}
