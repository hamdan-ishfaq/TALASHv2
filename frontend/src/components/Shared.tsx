import React from 'react';

export const scoreClass = (v?: number) => {
  if (v == null) return 'neutral';
  if (v >= 8) return 'excellent';
  if (v >= 6) return 'good';
  if (v >= 4) return 'average';
  return 'poor';
};

export const ScoreBadge: React.FC<{value?: number}> = ({value}) => (
  <span className={`score-badge ${scoreClass(value)}`}>
    {value != null ? value.toFixed(1) : '—'}
  </span>
);

export const ScoreBar: React.FC<{label: string; value?: number; max?: number; description?: string}> = ({label, value, max = 10, description}) => {
  const pct = value != null ? (value / max) * 100 : 0;
  return (
    <div className="score-bar-wrapper">
      <div className="score-bar-header">
        <div className="score-bar-title">
          <span className="score-bar-label-text">{label}</span>
          {description && <span className="score-bar-desc">{description}</span>}
        </div>
        <span className={`score-bar-value ${scoreClass(value)}`}>
          {value != null ? value.toFixed(1) : '—'}
        </span>
      </div>
      <div className="score-bar">
        <div className={`score-bar-fill ${scoreClass(value)}`} style={{width: `${pct}%`}} />
      </div>
    </div>
  );
};

export const StatusBadge: React.FC<{status?: string}> = ({status}) => {
  if (!status) return null;
  const cls = status === 'completed' ? 'completed'
            : status === 'completed_with_errors' ? 'warn'
            : status === 'processing' || status === 'queued' ? 'processing'
            : status === 'failed' ? 'failed' : 'pending';
  const icon = status === 'completed' ? '✓'
             : status === 'completed_with_errors' ? '⚠'
             : status === 'processing' ? '⟳'
             : status === 'queued' ? '⧖'
             : status === 'failed' ? '✗' : '·';
  const label = status === 'completed_with_errors' ? 'Completed (analysis issues)' : status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' ');
  return (
    <span className={`status-badge ${cls}`}>
      <span>{icon}</span>
      {label}
    </span>
  );
};
