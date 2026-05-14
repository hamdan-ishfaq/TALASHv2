import React, { useState, useMemo } from 'react';
import { DashCandidate } from '../types';
import { StatusBadge, ScoreBadge } from './Shared';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface DashboardViewProps {
  candidates: DashCandidate[];
  onSelectCandidate: (id: number) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  candidates, onSelectCandidate
}) => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const filtered = candidates.filter(c => {
    const matchesSearch = !search || 
      (c.name || '').toLowerCase().includes(search.toLowerCase()) ||
      (c.email || '').toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const chartData = useMemo(() => {
    return candidates
      .filter(c => c.status === 'completed' && c.overall_rank != null)
      .sort((a, b) => (b.overall_rank || 0) - (a.overall_rank || 0))
      .slice(0, 5)
      .map(c => ({
        name: c.name?.split(' ')[0] || `ID ${c.candidate_id}`,
        score: Number((c.overall_rank || 0).toFixed(1)),
        fullName: c.name
      }));
  }, [candidates]);

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
          <input type="text" placeholder="Search candidates..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="f-sel" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="processing">Processing</option>
          <option value="queued">Queued</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {chartData.length > 0 && (
        <div className="section 3d-card" style={{ padding: '24px 24px 8px 24px' }}>
          <div className="section-head" style={{ marginBottom: '16px' }}>Top Candidates Score Comparison</div>
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 30, left: -20, bottom: 5 }}>
                <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-primary)' }} tickLine={false} />
                <YAxis domain={[0, 10]} tick={{ fill: 'var(--text-muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--border-primary)' }} tickLine={false} />
                <Tooltip 
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  contentStyle={{ backgroundColor: 'var(--bg-card-solid)', border: '1px solid var(--border-primary)', borderRadius: '8px' }}
                  labelStyle={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: '4px' }}
                  itemStyle={{ color: 'var(--accent-blue)', fontWeight: 600 }}
                  formatter={(value: number) => [`${value} / 10`, 'Overall Score']}
                />
                <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.score >= 8 ? 'var(--accent-green)' : entry.score >= 6 ? 'var(--accent-blue)' : entry.score >= 4 ? 'var(--accent-amber)' : 'var(--accent-red)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

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
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} style={{textAlign: 'center', padding: '40px', color: 'var(--text-muted)'}}>
                  {candidates.length === 0 ? 'No candidates found in database. Upload a CV to begin.' : 'No candidates match your filters.'}
                </td>
              </tr>
            )}
            {filtered.map(c => (
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
