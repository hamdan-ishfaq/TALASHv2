import React from 'react';
import { CandidateDetail, MissingReq } from '../types';
import { ScoreBadge, ScoreBar, StatusBadge } from './Shared';

interface CandidateDetailViewProps {
  detail: CandidateDetail | null;
  missingInfo: MissingReq[];
  onBack: () => void;
}

export const CandidateDetailView: React.FC<CandidateDetailViewProps> = ({
  detail, missingInfo, onBack
}) => {
  if (!detail) return <div className="empty-state">Loading...</div>;

  const assessment = detail.assessments?.[0] || {};

  return (
    <div className="view-transition">
      <button className="back-btn" onClick={onBack}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        Back to Dashboard
      </button>

      {/* Top Stat Cards Row */}
      <div className="stats-row">
        <div className="stat-card 3d-card accent-blue">
          <div className="stat-label">Candidate Name</div>
          <div className="stat-value" style={{fontSize: 20}}>{detail.name || `ID: ${detail.id}`}</div>
          <div className="stat-sub">Status: <StatusBadge status={detail.status} /></div>
        </div>
        
        <div className="stat-card 3d-card accent-purple">
          <div className="stat-label">Overall Rank</div>
          <div className="stat-value"><ScoreBadge value={assessment.overall_rank} /></div>
          <div className="stat-sub">AI Evaluated</div>
        </div>

        <div className="stat-card 3d-card accent-green">
          <div className="stat-label">Data Points</div>
          <div className="stat-value">{detail.education_records.length + detail.work_experiences.length + detail.journal_publications.length}</div>
          <div className="stat-sub">Extracted fields</div>
        </div>
      </div>

      <div className="detail-grid">
        {/* Left Column */}
        <div className="detail-col">
          {/* Score Breakdown Card */}
          <div className="section 3d-card score-panel">
            <div className="section-head">Score Breakdown</div>
            <ScoreBar label="Education Strength" value={assessment.education_score} description={`${detail.education_records.length} records`} />
            <ScoreBar label="Experience Strength" value={assessment.experience_score} description={`${detail.work_experiences.length} roles`} />
            <ScoreBar label="Research Strength" value={assessment.research_score} description={`${detail.journal_publications.length + detail.conference_publications.length} pubs`} />
            <ScoreBar label="Skill Alignment" value={assessment.skill_score} description={`${detail.skills.length} skills`} />
            
            <div style={{marginTop: 20, paddingTop: 15, borderTop: '1px solid var(--border-subtle)'}}>
              <ScoreBar label="Overall Composite Rank" value={assessment.overall_rank} max={10} />
            </div>
          </div>

          {/* AI Executive Summary */}
          {assessment.summary && (
            <div className="section 3d-card glass-panel" style={{borderLeft: '4px solid var(--accent-blue)'}}>
              <div className="section-head">
                <span className="sparkle-icon">✨</span> Executive Summary
              </div>
              <div className="summary-text">{assessment.summary}</div>
            </div>
          )}

          {/* Missing Info Panel */}
          {missingInfo.length > 0 && (
            <div className="section 3d-card" style={{borderLeft: '4px solid var(--accent-amber)'}}>
              <div className="section-head" style={{color: 'var(--accent-amber)'}}>
                Missing Information Detected
              </div>
              {missingInfo.map(m => (
                <div key={m.id} style={{marginBottom: 16}}>
                  <div style={{fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6}}>
                    Module: {m.module_name}
                  </div>
                  <ul style={{paddingLeft: 20, fontSize: 11, color: 'var(--text-muted)', marginBottom: 12}}>
                    {m.missing_fields.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                  {m.draft_email_subject && (
                    <div className="email-preview">
                      <div className="email-subject">Draft Email: {m.draft_email_subject}</div>
                      <div className="email-body">{m.draft_email_body}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="detail-col">
          {/* Education Records */}
          <div className="section 3d-card">
            <div className="section-head">Education ({detail.education_records.length})</div>
            <div className="record-list">
              {detail.education_records.map((r, i) => (
                <div key={i} className="record-item">
                  <div className="record-title">{r.degree_name}</div>
                  <div className="record-org">{r.institution_name}</div>
                  <div className="record-meta">
                    {r.start_year || '?'} – {r.end_year || '?'} 
                    {r.cgpa && <span className="record-badge">CGPA: {r.cgpa}</span>}
                    {r.qs_ranking && <span className="record-badge qs-badge">QS: #{r.qs_ranking}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Experience Records */}
          <div className="section 3d-card">
            <div className="section-head">Experience ({detail.work_experiences.length})</div>
            <div className="record-list">
              {detail.work_experiences.map((r, i) => (
                <div key={i} className="record-item">
                  <div className="record-title">{r.job_title}</div>
                  <div className="record-org">{r.organization_name}</div>
                  <div className="record-meta">
                    {r.start_year || '?'} – {r.end_year || 'Present'}
                    {r.employment_type && <span className="record-badge">{r.employment_type}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Publications */}
          <div className="section 3d-card">
            <div className="section-head">
              Publications ({detail.journal_publications.length + detail.conference_publications.length})
            </div>
            <div className="record-list">
              {detail.journal_publications.map((r, i) => (
                <div key={`j-${i}`} className="record-item">
                  <div className="record-title">{r.journal_name}</div>
                  <div className="record-meta">
                    {r.publication_year || '?'}
                    {r.quartile && <span className="record-badge qs-badge">{r.quartile}</span>}
                    {r.wos_indexed && <span className="record-badge">WoS Indexed</span>}
                  </div>
                </div>
              ))}
              {detail.conference_publications.map((r, i) => (
                <div key={`c-${i}`} className="record-item">
                  <div className="record-title">{r.conference_name}</div>
                  <div className="record-meta">
                    {r.publication_year || '?'}
                    {r.core_rank && <span className="record-badge qs-badge">{r.core_rank} Rank</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
