import dayjs from 'dayjs';

export function formatCurrency(value: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatCompactCurrency(value: number, currency = 'USD'): string {
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(1)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(1)}K`;
  }
  return formatCurrency(value, currency);
}

export function formatPercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

export function formatDate(timestamp: number | string): string {
  return dayjs(timestamp).format('MMM D, YYYY');
}

export function formatDateTime(timestamp: number | string): string {
  return dayjs(timestamp).format('MMM D, YYYY h:mm A');
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}
