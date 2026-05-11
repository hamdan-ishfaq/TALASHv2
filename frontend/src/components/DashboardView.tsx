import React, { useMemo, useState } from 'react';
import { DashCandidate } from '../types';
import { StatusBadge, ScoreBadge } from './Shared';

interface DashboardViewProps {
  candidates: DashCandidate[];
  onSelectCandidate: (id: number) => void;
  includeFailed: boolean;
  onIncludeFailedChange: (v: boolean) => void;
}

const avg = (rows: DashCandidate[], key: keyof DashCandidate): number | null => {
  const vals = rows.map((r) => r[key] as number | undefined).filter((x): x is number => typeof x === 'number' && !Number.isNaN(x));
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  candidates,
  onSelectCandidate,
  includeFailed,
  onIncludeFailedChange,
}) => {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((c) => {
      const name = (c.name || '').toLowerCase();
      const email = (c.email || '').toLowerCase();
      return name.includes(q) || email.includes(q) || String(c.candidate_id).includes(q);
    });
  }, [candidates, search]);

  const snapshot = useMemo(() => {
    const base = filtered.filter((c) => c.status === 'completed' || c.status === 'completed_with_errors');
    const withEdu = base.filter((c) => c.education_score != null);
    const withExp = base.filter((c) => c.experience_score != null);
    const withRes = base.filter((c) => c.research_score != null);
    const withSk = base.filter((c) => c.skill_score != null);
    const withOv = base.filter((c) => c.overall_rank != null);
    return {
      n: base.length,
      nEdu: withEdu.length,
      nExp: withExp.length,
      nRes: withRes.length,
      nSk: withSk.length,
      nOv: withOv.length,
      edu: avg(withEdu, 'education_score'),
      exp: avg(withExp, 'experience_score'),
      res: avg(withRes, 'research_score'),
      sk: avg(withSk, 'skill_score'),
      overall: avg(withOv, 'overall_rank'),
    };
  }, [filtered]);

  const bar = (label: string, v: number | null) => {
    const pct = v != null ? Math.min(100, (v / 10) * 100) : 0;
    return (
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
          <span>{label}</span>
          <span>{v != null ? v.toFixed(1) : '—'}</span>
        </div>
        <div style={{ height: 6, borderRadius: 3, background: 'var(--border-subtle)', overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${pct}%`,
              borderRadius: 3,
              background: 'linear-gradient(90deg, var(--accent-blue), var(--accent-purple))',
              transition: 'width 0.3s ease',
            }}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="view-transition">
      <div className="page-header">
        <h1>Multi-Candidate Overview</h1>
        <p>Compare parsed candidates, view pipeline status, and access detailed analysis reports.</p>
      </div>

      {filtered.length > 0 && (
        <div className="section 3d-card" style={{ marginBottom: 20, padding: '16px 20px' }}>
          <div className="section-head" style={{ marginBottom: 12 }}>
            Score snapshot (completed in view{search.trim() ? ', filtered' : ''})
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>
            Averages from candidates with scores: Edu {snapshot.nEdu}/{snapshot.n}, Exp {snapshot.nExp}/{snapshot.n},
            Res {snapshot.nRes}/{snapshot.n}, Skills {snapshot.nSk}/{snapshot.n}, Overall {snapshot.nOv}/{snapshot.n}.
            {' '}Overall rank blends evidence scores (JD match affects rank when a target description is set).
          </div>
          {bar('Education', snapshot.edu)}
          {bar('Experience', snapshot.exp)}
          {bar('Research', snapshot.res)}
          {bar('Skill evidence', snapshot.sk)}
          {bar('Overall rank', snapshot.overall)}
        </div>
      )}

      <div className="filter-row">
        <div className="f-search">
          <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, flexShrink: 0, color: 'var(--text-muted)' }} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            placeholder="Search by name, email, or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <label className="f-sel" style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', userSelect: 'none' }}>
          <input
            type="checkbox"
            checked={includeFailed}
            onChange={(e) => onIncludeFailedChange(e.target.checked)}
          />
          <span>Show non-completed</span>
        </label>
      </div>

      <div className="table-wrapper 3d-card">
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: '22%' }}>Candidate</th>
              <th style={{ width: '12%' }}>Status</th>
              <th style={{ width: '8%' }}>Pipeline</th>
              <th style={{ width: '12%' }}>Education</th>
              <th style={{ width: '12%' }}>Experience</th>
              <th style={{ width: '10%' }}>Pubs / Skills</th>
              <th style={{ width: '8%' }}>Missing</th>
              <th style={{ width: '10%' }}>Score</th>
              <th style={{ width: '12%' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  {candidates.length === 0
                    ? 'No candidates found. Upload a CV to begin.'
                    : 'No candidates match your search.'}
                </td>
              </tr>
            )}
            {filtered.map((c) => (
              <tr key={c.candidate_id}>
                <td>
                  <div className="candidate-link" onClick={() => onSelectCandidate(c.candidate_id)}>
                    {c.name || `Candidate #${c.candidate_id}`}
                  </div>
                  {c.email && <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{c.email}</div>}
                </td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
                <td style={{ fontSize: 12, textAlign: 'center' }} title="Post-extraction pipeline healthy">
                  {c.analysis_healthy === true ? '✓' : c.analysis_healthy === false ? '⚠' : '—'}
                </td>
                <td>
                  <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)' }}>
                    {c.education_count} records
                  </div>
                </td>
                <td>
                  <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)' }}>
                    {c.experience_count} records
                  </div>
                </td>
                <td>
                  <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)' }}>
                    {c.journal_count + c.conference_count} / {c.skill_count}
                  </div>
                </td>
                <td style={{ textAlign: 'center', fontSize: 12 }}>
                  {c.missing_info_count > 0 ? (
                    <span title="Draft missing-info emails generated" style={{ color: 'var(--accent-amber)', fontWeight: 600 }}>
                      {c.missing_info_count}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)' }}>0</span>
                  )}
                </td>
                <td>
                  <ScoreBadge value={c.overall_rank} />
                </td>
                <td>
                  <button className="btn btn-sm" onClick={() => onSelectCandidate(c.candidate_id)}>
                    View Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
