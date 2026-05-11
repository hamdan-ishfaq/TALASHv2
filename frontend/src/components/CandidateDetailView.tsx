import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CandidateDetail, GapRecord, MissingReq, PipelineMetrics } from '../types';
import { ScoreBadge, ScoreBar, StatusBadge } from './Shared';

interface CandidateDetailViewProps {
  detail: CandidateDetail | null;
  missingInfo: MissingReq[];
  onBack: () => void;
  apiBase: string;
  onRefetch: () => void;
}

export const CandidateDetailView: React.FC<CandidateDetailViewProps> = ({
  detail,
  missingInfo,
  onBack,
  apiBase,
  onRefetch,
}) => {
  const [jdDraft, setJdDraft] = useState('');
  const [jdBusy, setJdBusy] = useState(false);
  const [jdMsg, setJdMsg] = useState<string | null>(null);

  useEffect(() => {
    setJdDraft(detail?.target_job_description || '');
    setJdMsg(null);
  }, [detail?.id, detail?.target_job_description]);

  const assessment = useMemo(() => {
    if (!detail?.assessments?.length) return {} as Record<string, number | string | undefined>;
    const sorted = [...detail.assessments].sort((a, b) => (b.id || 0) - (a.id || 0));
    return sorted[0] || {};
  }, [detail]);

  if (!detail) return <div className="empty-state">Loading...</div>;

  const pm: PipelineMetrics | undefined = detail.pipeline_metrics;

  const saveJobDescription = async () => {
    setJdBusy(true);
    setJdMsg(null);
    try {
      await axios.patch(`${apiBase}/candidates/${detail.id}/job-description`, {
        target_job_description: jdDraft.trim() || null,
      });
      setJdMsg('Saved. Use “Recompute skill scores” then run full pipeline (or Summary) to refresh ranks.');
      onRefetch();
    } catch (e: any) {
      setJdMsg(e.response?.data?.detail || 'Failed to save job description');
    } finally {
      setJdBusy(false);
    }
  };

  const recomputeSkills = async () => {
    setJdBusy(true);
    setJdMsg(null);
    try {
      await axios.post(`${apiBase}/analysis/skills/${detail.id}`);
      setJdMsg('Skill alignment recomputed.');
      onRefetch();
    } catch (e: any) {
      setJdMsg(e.response?.data?.detail || 'Failed to recompute skills');
    } finally {
      setJdBusy(false);
    }
  };

  const runFullPipeline = async () => {
    setJdBusy(true);
    setJdMsg(null);
    try {
      await axios.post(`${apiBase}/analysis/full-pipeline/${detail.id}`);
      setJdMsg('Full analysis pipeline completed.');
      onRefetch();
    } catch (e: any) {
      setJdMsg(e.response?.data?.detail || 'Full pipeline failed (see analysis banner)');
      onRefetch();
    } finally {
      setJdBusy(false);
    }
  };

  return (
    <div className="view-transition">
      <button className="back-btn" onClick={onBack}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        Back to Dashboard
      </button>

      {detail.analysis_health && !detail.analysis_health.healthy && (
        <div className="alert alert-error" style={{ marginBottom: 16, fontSize: 13 }}>
          <strong>Analysis incomplete or failed.</strong>
          {' '}
          {detail.analysis_health.pipeline_error && (
            <span style={{ whiteSpace: 'pre-wrap' }}>{String(detail.analysis_health.pipeline_error).slice(0, 500)}</span>
          )}
          {!detail.analysis_health.pipeline_error && detail.analysis_health.detail && (
            <span>{detail.analysis_health.detail}</span>
          )}
          {' '}Use “Run full pipeline” below to retry after fixing environment (API keys, DB, network).
        </div>
      )}

      <div className="stats-row">
        <div className="stat-card 3d-card accent-blue">
          <div className="stat-label">Candidate Name</div>
          <div className="stat-value" style={{ fontSize: 20 }}>{detail.name || `ID: ${detail.id}`}</div>
          <div className="stat-sub">Status: <StatusBadge status={detail.status} /></div>
        </div>

        <div className="stat-card 3d-card accent-purple">
          <div className="stat-label">Overall Rank</div>
          <div className="stat-value"><ScoreBadge value={assessment.overall_rank as number | undefined} /></div>
          <div className="stat-sub">Weighted composite (JD affects skills slot when set)</div>
        </div>

          <div className="stat-card 3d-card accent-green">
          <div className="stat-label">Data Points</div>
          <div className="stat-value">
            {detail.education_records.length +
              detail.work_experiences.length +
              detail.journal_publications.length +
              detail.conference_publications.length}
          </div>
          <div className="stat-sub">Extracted records</div>
        </div>
      </div>

      {((detail.education_gaps && detail.education_gaps.length > 0) ||
        (detail.employment_gaps && detail.employment_gaps.length > 0)) && (
        <div className="section 3d-card" style={{ marginBottom: 18, borderLeft: '4px solid var(--accent-purple)' }}>
          <div className="section-head">Timeline gaps</div>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
            Gaps between education stages or jobs (per CS417 §3.1 / §3.8). “Justified” means overlapping work or study was detected.
          </p>
          {detail.education_gaps && detail.education_gaps.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Education</div>
              <ul style={{ paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>
                {detail.education_gaps.map((g: GapRecord, i: number) => (
                  <li key={`eg-${i}`}>
                    {g.from_stage ?? '?'} → {g.to_stage ?? '?'}: {g.gap_months ?? '?'} mo
                    {g.justified ? ' · justified' : ' · review'}
                    {g.justification && <span style={{ color: 'var(--text-muted)' }}> — {g.justification}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {detail.employment_gaps && detail.employment_gaps.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Employment</div>
              <ul style={{ paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>
                {detail.employment_gaps.map((g: GapRecord, i: number) => (
                  <li key={`em-${i}`}>
                    {g.gap_type || 'Gap'}: {g.gap_months ?? '?'} mo
                    {g.gap_start && g.gap_end && (
                      <span style={{ color: 'var(--text-muted)' }}> ({g.gap_start} – {g.gap_end})</span>
                    )}
                    {g.justified ? ' · justified' : ' · review'}
                    {g.justification && <span style={{ color: 'var(--text-muted)' }}> — {g.justification}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-col">
          <div className="section 3d-card score-panel">
            <div className="section-head">Score Breakdown</div>
            <ScoreBar label="Education Strength" value={assessment.education_score as number | undefined} description={`${detail.education_records.length} records`} />
            <ScoreBar label="Experience Strength" value={assessment.experience_score as number | undefined} description={`${detail.work_experiences.length} roles`} />
            <ScoreBar label="Research Strength" value={assessment.research_score as number | undefined} description={`${detail.journal_publications.length + detail.conference_publications.length} pubs`} />
            <ScoreBar label="Skill evidence (CV)" value={assessment.skill_score as number | undefined} description={`${detail.skills.length} skills`} />
            {assessment.jd_alignment_score != null && (
              <ScoreBar
                label="Skill ↔ Job description match"
                value={assessment.jd_alignment_score as number | undefined}
                description="Heuristic overlap with target JD"
              />
            )}

            <div style={{ marginTop: 20, paddingTop: 15, borderTop: '1px solid var(--border-subtle)' }}>
              <ScoreBar label="Overall Composite Rank" value={assessment.overall_rank as number | undefined} max={10} />
            </div>
          </div>

          <div className="section 3d-card" style={{ borderLeft: '4px solid var(--accent-blue)' }}>
            <div className="section-head">Target job description (§3.9)</div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
              Paste the role text here. The pipeline scores keyword overlap between this text, extracted skills, and publication titles.
            </p>
            <textarea
              className="f-search"
              style={{ width: '100%', minHeight: 100, padding: 10, fontSize: 12, resize: 'vertical', marginBottom: 10 }}
              value={jdDraft}
              onChange={(e) => setJdDraft(e.target.value)}
              placeholder="e.g. Required: Python, PyTorch, NLP, teaching experience..."
            />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-sm" disabled={jdBusy} onClick={saveJobDescription}>Save JD</button>
              <button type="button" className="btn btn-sm" disabled={jdBusy} onClick={recomputeSkills}>Recompute skill scores</button>
              <button type="button" className="btn btn-sm" disabled={jdBusy} onClick={runFullPipeline}>Run full pipeline</button>
            </div>
            {jdMsg && <div style={{ fontSize: 11, marginTop: 10, color: 'var(--text-secondary)' }}>{jdMsg}</div>}
          </div>

          {assessment.summary && (
            <div className="section 3d-card glass-panel" style={{ borderLeft: '4px solid var(--accent-blue)' }}>
              <div className="section-head">
                <span className="sparkle-icon">✨</span> Executive Summary
              </div>
              <div className="summary-text">{assessment.summary as string}</div>
            </div>
          )}

          {pm && (pm.topic_variability || pm.collaboration || pm.skill_alignment || pm.verification_links) && (
            <div className="section 3d-card">
              <div className="section-head">Research Profile Analytics</div>
              {pm.skill_alignment && (
                <div style={{ marginBottom: 14, fontSize: 12, color: 'var(--text-muted)' }}>
                  Pipeline skill scores — evidence: <strong>{pm.skill_alignment.evidence_score ?? '—'}</strong>
                  {pm.skill_alignment.jd_score != null && (
                    <> · JD match: <strong>{pm.skill_alignment.jd_score}</strong> ({pm.skill_alignment.jd_skills_matched} skills)</>
                  )}
                </div>
              )}
              {pm.research_audit?.enrichment_audit && (
                <div style={{ marginBottom: 14, fontSize: 11, color: 'var(--text-secondary)' }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>Publication enrichment</div>
                  {(pm.research_audit.enrichment_audit?.warnings || []).slice(0, 5).map((w, i) => (
                    <div key={i}>• {w}</div>
                  ))}
                  {(pm.research_audit.enrichment_audit?.errors || []).slice(0, 3).map((w, i) => (
                    <div key={`e-${i}`} style={{ color: 'var(--accent-amber)' }}>• {w}</div>
                  ))}
                </div>
              )}
              {pm.topic_variability && pm.topic_variability.publication_count ? (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Topic variability</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Dominant theme: <strong>{pm.topic_variability.dominant_theme || '—'}</strong>
                    {' '}({pm.topic_variability.dominant_share_pct ?? 0}% of publications)
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    Diversity score: <strong>{pm.topic_variability.diversity_score ?? 0}</strong>
                    {' '}(1 = evenly spread across themes)
                  </div>
                  {pm.topic_variability.topic_stability_note && (
                    <div style={{ fontSize: 11, marginTop: 8, color: 'var(--text-secondary)' }}>
                      {pm.topic_variability.topic_stability_note}
                    </div>
                  )}
                  {pm.topic_variability.topic_trend_by_year && pm.topic_variability.topic_trend_by_year.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6 }}>Theme by publication year</div>
                      <ul style={{ paddingLeft: 18, fontSize: 11, marginTop: 4 }}>
                        {pm.topic_variability.topic_trend_by_year.map((row, idx) => (
                          <li key={`${row.year ?? 'u'}-${idx}`}>
                            {(row as { year_label?: string }).year_label ?? row.year ?? 'Undated'}: <strong>{row.dominant_theme}</strong> ({row.publication_count} papers)
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {pm.topic_variability.theme_counts && (
                    <ul style={{ paddingLeft: 18, fontSize: 11, marginTop: 8 }}>
                      {Object.entries(pm.topic_variability.theme_counts).map(([k, v]) => (
                        <li key={k}>{k}: {v}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}
              {pm.collaboration && (pm.collaboration.unique_coauthors ?? 0) > 0 ? (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Co-authors</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Unique co-authors: {pm.collaboration.unique_coauthors} · Recurring: {pm.collaboration.recurring_collaborators}
                    {' '}· Avg co-authors/paper: {pm.collaboration.avg_coauthors_per_paper}
                  </div>
                  {pm.collaboration.international_collaboration_hint && (
                    <div style={{ fontSize: 11, marginTop: 8, color: 'var(--text-secondary)' }}>
                      {pm.collaboration.international_collaboration_hint}
                    </div>
                  )}
                  {pm.collaboration.top_collaborators && pm.collaboration.top_collaborators.length > 0 && (
                    <ul style={{ paddingLeft: 18, fontSize: 11, marginTop: 8 }}>
                      {pm.collaboration.top_collaborators.slice(0, 8).map((c, i) => (
                        <li key={i}>{c.name} ({c.shared_papers} shared)</li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}
              {pm.ip_format_checks && ((pm.ip_format_checks.books_checked ?? 0) > 0 || (pm.ip_format_checks.patents_checked ?? 0) > 0) ? (
                <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                  Books (ISBN format check): {pm.ip_format_checks.books_with_valid_isbn}/{pm.ip_format_checks.books_checked} valid ·
                  Patents (number plausibility): {pm.ip_format_checks.patents_with_plausible_number}/{pm.ip_format_checks.patents_checked}
                </div>
              ) : null}
              {pm.verification_links && (pm.verification_links.books?.length || pm.verification_links.patents?.length) ? (
                <div style={{ marginTop: 14, fontSize: 11 }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>Suggested verification links</div>
                  {pm.verification_links.books?.slice(0, 5).map((b) => (
                    <div key={`b-${b.id}`} style={{ marginBottom: 4 }}>
                      {b.open_library_json && (
                        <a href={b.open_library_json.replace(/\.json$/i, '')} target="_blank" rel="noreferrer">Open Library</a>
                      )}
                      {b.google_books_search && (
                        <>
                          {b.open_library_json ? ' · ' : ''}
                          <a href={b.google_books_search} target="_blank" rel="noreferrer">Google Books</a>
                        </>
                      )}
                    </div>
                  ))}
                  {pm.verification_links.patents?.slice(0, 5).map((p) => (
                    <div key={`p-${p.id}`} style={{ marginBottom: 4 }}>
                      {p.google_patents_search && (
                        <a href={p.google_patents_search} target="_blank" rel="noreferrer">Google Patents search #{p.id}</a>
                      )}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          {missingInfo.length > 0 && (
            <div className="section 3d-card" style={{ borderLeft: '4px solid var(--accent-amber)' }}>
              <div className="section-head" style={{ color: 'var(--accent-amber)' }}>
                Missing information — draft emails (CS417 §4)
              </div>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                Personalized templates you can paste into your mail client. Regenerate via{' '}
                <code style={{ fontSize: 10 }}>POST /analysis/missing-info/:id/generate</code>.
              </p>
              {missingInfo.map((m) => (
                <div key={m.id} style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                    Module: {m.module_name}
                  </div>
                  <ul style={{ paddingLeft: 20, fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                    {m.missing_fields.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                  {m.draft_email_subject && (
                    <div className="email-preview">
                      <div className="email-subject">Subject: {m.draft_email_subject}</div>
                      <div className="email-body">{m.draft_email_body}</div>
                      <button
                        type="button"
                        className="btn btn-sm"
                        style={{ marginTop: 8 }}
                        onClick={() => {
                          const t = `${m.draft_email_subject || ''}\n\n${m.draft_email_body || ''}`;
                          void navigator.clipboard.writeText(t).catch(() => undefined);
                        }}
                      >
                        Copy subject + body
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="detail-col">
          <div className="section 3d-card">
            <div className="section-head">Education ({detail.education_records.length})</div>
            <div className="record-list">
              {detail.education_records.map((r, i) => (
                <div key={i} className="record-item">
                  <div className="record-title">{(r as any).degree_title || (r as any).degree_name || r.stage || '—'}</div>
                  <div className="record-org">{(r as any).institution || (r as any).institution_name || '—'}</div>
                  <div className="record-meta">
                    {(r as any).start_year || '?'} – {(r as any).end_year || '?'}
                    {(r as any).marks_percentage != null && (
                      <span className="record-badge">{(r as any).marks_percentage}%</span>
                    )}
                    {(r as any).cgpa != null && <span className="record-badge">CGPA: {(r as any).cgpa}</span>}
                    {(r as any).qs_ranking != null && <span className="record-badge qs-badge">QS: #{(r as any).qs_ranking}</span>}
                    {(r as any).the_ranking != null && <span className="record-badge qs-badge">THE: #{(r as any).the_ranking}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="section 3d-card">
            <div className="section-head">Experience ({detail.work_experiences.length})</div>
            <div className="record-list">
              {detail.work_experiences.map((r, i) => (
                <div key={i} className="record-item">
                  <div className="record-title">{(r as any).job_title || '—'}</div>
                  <div className="record-org">{(r as any).organization || (r as any).organization_name || '—'}</div>
                  <div className="record-meta">
                    {(r as any).start_year || '?'} – {(r as any).end_year || 'Present'}
                    {(r as any).employment_type && <span className="record-badge">{(r as any).employment_type}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="section 3d-card">
            <div className="section-head">Skills ({detail.skills.length})</div>
            <div className="record-list">
              {detail.skills.map((s: any, i: number) => (
                <div key={i} className="record-item">
                  <div className="record-title">{s.name}</div>
                  <div className="record-meta">
                    {s.strength_of_evidence && <span className="record-badge">{s.strength_of_evidence}</span>}
                    {s.evidenced_in_work && <span className="record-badge">Work</span>}
                    {s.evidenced_in_research && <span className="record-badge">Research</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="section 3d-card">
            <div className="section-head">
              Publications ({detail.journal_publications.length + detail.conference_publications.length})
            </div>
            <div className="record-list">
              {detail.journal_publications.map((r: any, i: number) => (
                <div key={`j-${i}`} className="record-item">
                  <div className="record-title">{r.title || r.journal_name || 'Journal paper'}</div>
                  <div className="record-org" style={{ fontSize: 11 }}>{r.journal_name}</div>
                  <div className="record-meta">
                    {r.year ?? r.publication_year ?? '?'}
                    {r.quartile && <span className="record-badge qs-badge">{r.quartile}</span>}
                    {r.wos_indexed && <span className="record-badge">WoS</span>}
                    {r.scopus_indexed && <span className="record-badge">Scopus</span>}
                    {r.issn && <span className="record-badge" title="ISSN">{String(r.issn).slice(0, 12)}</span>}
                  </div>
                </div>
              ))}
              {detail.conference_publications.map((r: any, i: number) => (
                <div key={`c-${i}`} className="record-item">
                  <div className="record-title">{r.title || r.conference_name || 'Conference paper'}</div>
                  <div className="record-org" style={{ fontSize: 11 }}>{r.conference_name}</div>
                  <div className="record-meta">
                    {r.year ?? r.publication_year ?? '?'}
                    {(r.core_ranking || r.core_rank) && (
                      <span className="record-badge qs-badge">{(r.core_ranking || r.core_rank)} CORE</span>
                    )}
                    {r.is_a_star && <span className="record-badge qs-badge">A*</span>}
                    {r.indexed_in && <span className="record-badge" title={r.indexed_in}>Indexed</span>}
                    {r.publisher && <span className="record-badge">{r.publisher}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {(detail.books?.length || detail.patents?.length) ? (
            <div className="section 3d-card">
              <div className="section-head">Books & Patents</div>
              <div className="record-list">
                {detail.books?.map((b: any) => (
                  <div key={`book-${b.id}`} className="record-item">
                    <div className="record-title">{b.title}</div>
                    <div className="record-meta">
                      {b.isbn && <span className="record-badge">{b.isbn}</span>}
                      {b.online_link && (
                        <a href={b.online_link} target="_blank" rel="noreferrer" className="record-badge">Link</a>
                      )}
                    </div>
                  </div>
                ))}
                {detail.patents?.map((p: any) => (
                  <div key={`pat-${p.id}`} className="record-item">
                    <div className="record-title">{p.title}</div>
                    <div className="record-meta">
                      {p.patent_no && <span className="record-badge">{p.patent_no}</span>}
                      {p.online_link && (
                        <a href={p.online_link} target="_blank" rel="noreferrer" className="record-badge">Link</a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
