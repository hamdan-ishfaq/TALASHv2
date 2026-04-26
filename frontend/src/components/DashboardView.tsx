import React from 'react';
import { DashCandidate } from '../types';
import { StatusBadge, ScoreBadge } from './Shared';

interface DashboardViewProps {
  candidates: DashCandidate[];
  onSelectCandidate: (id: number) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  candidates, onSelectCandidate
}) => {
  return (
    <div className="view-transition">
      <div className="page-header">
        <h1>Multi-Candidate Overview</h1>
        <p>Compare parsed candidates, view real-time pipeline status, and access detailed analysis reports.</p>
      </div>

      <div className="filter-row">
        <div className="f-search">
          <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, flexShrink: 0, color: 'var(--text-muted)' }} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input type="text" placeholder="Search candidates..." />
        </div>
        <div className="f-sel">
          Status: All ▾
        </div>
      </div>

      <div className="table-wrapper 3d-card">
        <table className="table">
          <thead>
            <tr>
              <th style={{width: '25%'}}>Candidate</th>
              <th style={{width: '15%'}}>Status</th>
              <th style={{width: '12%'}}>Education</th>
              <th style={{width: '12%'}}>Experience</th>
              <th style={{width: '12%'}}>Pubs / Skills</th>
              <th style={{width: '10%'}}>Score</th>
              <th style={{width: '14%'}}>Action</th>
            </tr>
          </thead>
          <tbody>
            {candidates.length === 0 && (
              <tr>
                <td colSpan={7} style={{textAlign: 'center', padding: '40px', color: 'var(--text-muted)'}}>
                  No candidates found in database. Upload a CV to begin.
                </td>
              </tr>
            )}
            {candidates.map(c => (
              <tr key={c.candidate_id}>
                <td>
                  <div 
                    className="candidate-link" 
                    onClick={() => onSelectCandidate(c.candidate_id)}
                  >
                    {c.name || `Candidate #${c.candidate_id}`}
                  </div>
                  {c.email && <div style={{fontSize: 10, color: 'var(--text-muted)'}}>{c.email}</div>}
                </td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
                <td>
                  <div style={{fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)'}}>
                    {c.education_count} records
                  </div>
                </td>
                <td>
                  <div style={{fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)'}}>
                    {c.experience_count} records
                  </div>
                </td>
                <td>
                  <div style={{fontSize: 11, fontWeight: 500, color: 'var(--text-secondary)'}}>
                    {c.journal_count + c.conference_count} / {c.skill_count}
                  </div>
                </td>
                <td>
                  <ScoreBadge value={c.overall_rank} />
                </td>
                <td>
                  <button 
                    className="btn btn-sm" 
                    onClick={() => onSelectCandidate(c.candidate_id)}
                  >
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
