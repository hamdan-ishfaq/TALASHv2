import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './index.css';

const API = 'http://localhost:8000';

interface DashCandidate {
  candidate_id: number; name?: string; email?: string; status?: string;
  education_score?: number; experience_score?: number; research_score?: number;
  skill_score?: number; overall_rank?: number; summary?: string;
  education_count: number; experience_count: number; journal_count: number;
  conference_count: number; skill_count: number; supervision_count: number;
  missing_info_count: number;
}

interface MissingReq {
  id: number; module_name: string; missing_fields: string[];
  draft_email_subject?: string; draft_email_body?: string;
  status: string; generated_at?: string;
}

interface CandidateDetail {
  id: number; name?: string; email?: string; phone?: string; linkedin_url?: string;
  status?: string; summary?: string;
  education_records: any[]; work_experiences: any[]; journal_publications: any[];
  conference_publications: any[]; supervision_records: any[]; skills: any[];
  books: any[]; patents: any[];
  assessments: { education_score?: number; experience_score?: number;
    research_score?: number; skill_score?: number; overall_rank?: number; summary?: string }[];
}

const scoreClass = (v?: number) => {
  if (v == null) return 'neutral';
  if (v >= 8) return 'excellent';
  if (v >= 6) return 'good';
  if (v >= 4) return 'average';
  return 'poor';
};

const ScoreBadge: React.FC<{value?: number}> = ({value}) => (
  <span className={`score-badge ${scoreClass(value)}`}>
    {value != null ? value.toFixed(1) : '—'}
  </span>
);

const ScoreBar: React.FC<{label: string; value?: number; max?: number}> = ({label, value, max = 10}) => {
  const pct = value != null ? (value / max) * 100 : 0;
  return (
    <div style={{marginBottom: 10}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
        <span style={{fontSize:11,color:'var(--text-muted)',fontWeight:500}}>{label}</span>
        <span className={`score-bar-label`} style={{color: `var(--score-${scoreClass(value)})`}}>
          {value != null ? value.toFixed(1) : '—'}
        </span>
      </div>
      <div className="score-bar">
        <div className={`score-bar-fill ${scoreClass(value)}`} style={{width:`${pct}%`}}/>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  const [view, setView] = useState<'upload'|'dashboard'|'detail'>('upload');
  const [candidates, setCandidates] = useState<DashCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<number|null>(null);
  const [detail, setDetail] = useState<CandidateDetail|null>(null);
  const [missingInfo, setMissingInfo] = useState<MissingReq[]>([]);
  const [loading, setLoading] = useState(false);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [error, setError] = useState<string|null>(null);
  const [success, setSuccess] = useState<string|null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<{name:string;status:string;progress:number;cid?:number}[]>([]);

  const fetchDashboard = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await axios.get(`${API}/analysis/dashboard`);
      setCandidates(r.data.candidates || []);
    } catch (e: any) { setError(e.response?.data?.detail || 'Failed to load dashboard'); }
    setLoading(false);
  }, []);

  const fetchDetail = useCallback(async (id: number) => {
    setLoading(true); setError(null);
    try {
      const [cRes, mRes] = await Promise.all([
        axios.get(`${API}/candidates/${id}`),
        axios.get(`${API}/analysis/missing-info/${id}`),
      ]);
      setDetail(cRes.data);
      setMissingInfo(mRes.data.requests || []);
    } catch (e: any) { setError(e.response?.data?.detail || 'Failed to load candidate'); }
    setLoading(false);
  }, []);

  useEffect(() => { if (view === 'dashboard') fetchDashboard(); }, [view, fetchDashboard]);
  useEffect(() => { if (view === 'detail' && selectedId) fetchDetail(selectedId); }, [view, selectedId, fetchDetail]);

  const runFullPipeline = async () => {
    setPipelineLoading(true); setError(null); setSuccess(null);
    try {
      const r = await axios.post(`${API}/analysis/full-pipeline/batch`, {});
      setSuccess(`Pipeline complete: ${r.data.succeeded}/${r.data.total} succeeded`);
      await fetchDashboard();
    } catch (e: any) { setError(e.response?.data?.detail || 'Pipeline failed'); }
    setPipelineLoading(false);
  };

  const runSinglePipeline = async (id: number) => {
    setPipelineLoading(true); setError(null); setSuccess(null);
    try {
      await axios.post(`${API}/analysis/full-pipeline/${id}`);
      setSuccess('Analysis complete for candidate');
      if (view === 'detail') await fetchDetail(id);
      else await fetchDashboard();
    } catch (e: any) { setError(e.response?.data?.detail || 'Analysis failed'); }
    setPipelineLoading(false);
  };

  const openDetail = (id: number) => { setSelectedId(id); setView('detail'); };

  // Upload handlers
  const pollCandidate = (cid: number, fname: string) => {
    let attempts = 0;
    const iv = setInterval(async () => {
      attempts++;
      try {
        const r = await axios.get(`${API}/candidates/${cid}`);
        const st = (r.data.status||'').toLowerCase();
        if (st === 'completed') {
          setUploadQueue(q => q.map(i => i.name===fname ? {...i,status:'complete',progress:100} : i));
          clearInterval(iv);
        } else if (st === 'failed') {
          setUploadQueue(q => q.map(i => i.name===fname ? {...i,status:'error',progress:0} : i));
          clearInterval(iv);
        } else {
          setUploadQueue(q => q.map(i => i.name===fname ? {...i,status:'processing',progress:60} : i));
        }
        if (attempts > 180) clearInterval(iv);
      } catch { if (attempts > 180) clearInterval(iv); }
    }, 2000);
  };

  const handleFiles = async (files: FileList) => {
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      setUploadQueue(q => [...q, {name:f.name, status:'queued', progress:10}]);
      try {
        const fd = new FormData(); fd.append('file', f);
        const r = await axios.post(`${API}/upload`, fd);
        if (r.data.candidate_id) {
          setUploadQueue(q => q.map(x => x.name===f.name ? {...x,cid:r.data.candidate_id,progress:30} : x));
          pollCandidate(r.data.candidate_id, f.name);
        }
      } catch (e: any) {
        setUploadQueue(q => q.map(x => x.name===f.name ? {...x,status:'error',progress:0} : x));
        setError(e.response?.data?.detail || `Upload failed: ${f.name}`);
      }
    }
  };

  // ========== UPLOAD VIEW ==========
  const renderUpload = () => (
    <div className="container">
      <div className="page-header">
        <h1>CV Upload & Ingestion</h1>
        <p>Upload candidate CVs for extraction and analysis</p>
      </div>
      <div className="two-col">
        <div className="section">
          <div className="section-head">Job Configuration</div>
          <div style={{marginBottom:12}}>
            <div style={{fontSize:11,color:'var(--text-muted)',fontWeight:600,marginBottom:4}}>Target Role</div>
            <div style={{fontSize:13,color:'var(--text-primary)',fontWeight:600}}>Associate Professor — Machine Learning</div>
          </div>
          <div style={{marginBottom:12}}>
            <div style={{fontSize:11,color:'var(--text-muted)',fontWeight:600,marginBottom:6}}>Required Skills</div>
            <div>{['Machine Learning','Deep Learning','PhD Supervision','Research Publications'].map(s =>
              <span key={s} className="chip active">{s}</span>)}
            </div>
          </div>
          <div className="btn-group" style={{marginTop:16}}>
            <button className="btn btn-primary" onClick={() => setView('dashboard')}>Open Dashboard →</button>
          </div>
        </div>
        <div className="section">
          <div className="section-head">Upload CVs</div>
          <div className={`dropzone ${dragOver?'dragover':''}`}
            onDragOver={e=>{e.preventDefault();setDragOver(true)}}
            onDragLeave={()=>setDragOver(false)}
            onDrop={e=>{e.preventDefault();setDragOver(false);handleFiles(e.dataTransfer.files)}}>
            <div className="drop-icon">
              <svg viewBox="0 0 24 24" style={{width:32,height:32,stroke:'var(--text-muted)',fill:'none',strokeWidth:1.5}}>
                <path d="M12 5v14M5 12l7-7 7 7"/></svg>
            </div>
            <div className="drop-text">Drop PDF files here</div>
            <div className="drop-sub">.pdf format only</div>
            <label className="btn btn-sm" style={{cursor:'pointer',marginTop:10}}>
              Browse <input type="file" multiple accept=".pdf" onChange={e=>e.target.files&&handleFiles(e.target.files)} style={{display:'none'}}/>
            </label>
          </div>
          {uploadQueue.length > 0 && <>
            <div style={{fontSize:11,color:'var(--text-muted)',fontWeight:600,marginBottom:8}}>
              Queue ({uploadQueue.filter(q=>q.status==='complete').length}/{uploadQueue.length} done)
            </div>
            {uploadQueue.map((q,i)=>(
              <div key={i} className="queue-item">
                <span style={{flex:1,color:'var(--text-secondary)'}}>{q.name}</span>
                <div className="progress"><div className="progress-fill" style={{width:`${q.progress}%`}}/></div>
                <span className={`status-badge ${q.status==='complete'?'completed':q.status==='error'?'failed':'processing'}`}>
                  {q.status==='complete'?'✓ Done':q.status==='error'?'✗ Error':q.status==='processing'?'Extracting…':'Queued'}
                </span>
              </div>
            ))}
          </>}
        </div>
      </div>
    </div>
  );

  // ========== DASHBOARD VIEW ==========
  const renderDashboard = () => {
    const analyzed = candidates.filter(c => c.overall_rank != null);
    const avgRank = analyzed.length ? (analyzed.reduce((s,c) => s + (c.overall_rank||0), 0) / analyzed.length) : 0;
    const totalMissing = candidates.reduce((s,c) => s + c.missing_info_count, 0);

    return (
      <div className="container">
        <div className="page-header">
          <h1>Candidate Analysis Dashboard</h1>
          <p>Module 2 — Education, Experience & Summary Analysis</p>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div className="stats-row">
          <div className="stat-card accent-blue">
            <div className="stat-label">Total Candidates</div>
            <div className="stat-value">{candidates.length}</div>
          </div>
          <div className="stat-card accent-green">
            <div className="stat-label">Analyzed</div>
            <div className="stat-value">{analyzed.length}</div>
          </div>
          <div className="stat-card accent-purple">
            <div className="stat-label">Avg. Rank</div>
            <div className="stat-value">{avgRank ? avgRank.toFixed(1) : '—'}</div>
          </div>
          <div className="stat-card accent-amber">
            <div className="stat-label">Missing Info</div>
            <div className="stat-value">{totalMissing}</div>
            <div className="stat-sub">requests pending</div>
          </div>
        </div>

        <div className="actions-bar">
          <div className="btn-group">
            <button className="btn btn-primary" onClick={runFullPipeline} disabled={pipelineLoading}>
              {pipelineLoading ? '⟳ Running…' : '▶ Run Full Pipeline (All)'}
            </button>
            <button className="btn" onClick={fetchDashboard} disabled={loading}>↻ Refresh</button>
          </div>
        </div>

        {loading ? (
          <div className="loading-container"><div className="spinner"/><div className="loading-text">Loading candidates…</div></div>
        ) : candidates.length === 0 ? (
          <div className="empty-state"><p>No candidates found</p><p className="empty-sub">Upload CVs to get started</p></div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead><tr>
                <th>Candidate</th><th>Status</th><th>Education</th><th>Experience</th>
                <th>Research</th><th>Skills</th><th>Overall</th><th>Missing</th><th>Actions</th>
              </tr></thead>
              <tbody>
                {candidates.map(c => (
                  <tr key={c.candidate_id}>
                    <td>
                      <span className="candidate-link" onClick={()=>openDetail(c.candidate_id)}>
                        {c.name || `#${c.candidate_id}`}
                      </span>
                      {c.email && <div style={{fontSize:10,color:'var(--text-muted)'}}>{c.email}</div>}
                    </td>
                    <td><span className={`status-badge ${c.status||''}`}>{c.status||'—'}</span></td>
                    <td><ScoreBadge value={c.education_score}/></td>
                    <td><ScoreBadge value={c.experience_score}/></td>
                    <td><ScoreBadge value={c.research_score}/></td>
                    <td><ScoreBadge value={c.skill_score}/></td>
                    <td><ScoreBadge value={c.overall_rank}/></td>
                    <td>
                      {c.missing_info_count > 0
                        ? <span className="score-badge average">{c.missing_info_count}</span>
                        : <span className="score-badge excellent">0</span>}
                    </td>
                    <td>
                      <div className="btn-group">
                        <button className="btn btn-sm" onClick={()=>openDetail(c.candidate_id)}>View</button>
                        <button className="btn btn-sm btn-primary" onClick={()=>runSinglePipeline(c.candidate_id)}
                          disabled={pipelineLoading}>Analyze</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  // ========== DETAIL VIEW ==========
  const renderDetail = () => {
    if (loading || !detail) return (
      <div className="container"><div className="loading-container"><div className="spinner"/><div className="loading-text">Loading…</div></div></div>
    );
    const a = detail.assessments?.[0];
    return (
      <div className="container">
        <button className="back-btn" onClick={()=>{setView('dashboard');setDetail(null)}}>← Back to Dashboard</button>
        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:24,flexWrap:'wrap',gap:12}}>
          <div>
            <h1 style={{fontSize:22,fontWeight:700}}>{detail.name || 'Unknown'}</h1>
            <div style={{fontSize:12,color:'var(--text-muted)',marginTop:2}}>
              {[detail.email, detail.phone, detail.linkedin_url].filter(Boolean).join(' · ') || 'No contact info'}
            </div>
          </div>
          <div className="btn-group">
            <button className="btn btn-primary" onClick={()=>runSinglePipeline(detail.id)} disabled={pipelineLoading}>
              {pipelineLoading ? '⟳ Running…' : '▶ Run Analysis'}
            </button>
          </div>
        </div>

        {/* Score Overview */}
        <div className="stats-row" style={{marginBottom:24}}>
          {[
            {label:'Education',score:a?.education_score,count:`${detail.education_records.length} records`},
            {label:'Experience',score:a?.experience_score,count:`${detail.work_experiences.length} roles`},
            {label:'Research',score:a?.research_score,count:`${detail.journal_publications.length+detail.conference_publications.length} pubs`},
            {label:'Skills',score:a?.skill_score,count:`${detail.skills.length} skills`},
            {label:'Overall Rank',score:a?.overall_rank,count:'weighted avg'},
          ].map(({label,score,count})=>(
            <div key={label} className="stat-card">
              <div className="stat-label">{label}</div>
              <div className="stat-value" style={{color:`var(--score-${scoreClass(score)})`}}>
                {score != null ? score.toFixed(1) : '—'}
              </div>
              <div className="stat-sub">{count}</div>
            </div>
          ))}
        </div>

        {/* Score Bars */}
        <div className="section" style={{marginBottom:20}}>
          <div className="section-head">Score Breakdown</div>
          <ScoreBar label="Education Strength" value={a?.education_score}/>
          <ScoreBar label="Experience Strength" value={a?.experience_score}/>
          <ScoreBar label="Research Strength" value={a?.research_score}/>
          <ScoreBar label="Skill Alignment" value={a?.skill_score}/>
          <div style={{borderTop:'1px solid var(--border-subtle)',paddingTop:10,marginTop:6}}>
            <ScoreBar label="Overall Rank" value={a?.overall_rank}/>
          </div>
        </div>

        {/* Summary */}
        {detail.summary && (
          <div className="summary-card">
            <div className="section-head" style={{borderBottom:'1px solid var(--border-subtle)',paddingBottom:10,marginBottom:14}}>Executive Summary</div>
            <div className="summary-text">{detail.summary}</div>
          </div>
        )}

        <div className="detail-grid">
          {/* Education */}
          <div className="detail-section">
            <div className="detail-title">Education ({detail.education_records.length})</div>
            {detail.education_records.map((r:any,i:number)=>(
              <div key={i} style={{marginBottom:10,paddingBottom:10,borderBottom:'1px solid var(--border-subtle)'}}>
                <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)'}}>{r.degree_title||r.stage||'—'}</div>
                <div style={{fontSize:11,color:'var(--text-secondary)'}}>{r.institution||'—'}</div>
                <div style={{fontSize:10,color:'var(--text-muted)',display:'flex',gap:12,marginTop:2}}>
                  <span>{r.start_year||'?'}–{r.end_year||'?'}</span>
                  {r.cgpa && <span>CGPA: {r.cgpa}{r.cgpa_scale ? `/${r.cgpa_scale}` : ''}</span>}
                  {r.qs_ranking && <span>QS: #{r.qs_ranking}</span>}
                </div>
              </div>
            ))}
            {!detail.education_records.length && <div style={{fontSize:11,color:'var(--text-muted)'}}>No education records</div>}
          </div>

          {/* Experience */}
          <div className="detail-section">
            <div className="detail-title">Experience ({detail.work_experiences.length})</div>
            {detail.work_experiences.map((e:any,i:number)=>(
              <div key={i} style={{marginBottom:10,paddingBottom:10,borderBottom:'1px solid var(--border-subtle)'}}>
                <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)'}}>{e.job_title||'—'}</div>
                <div style={{fontSize:11,color:'var(--text-secondary)'}}>{e.organization||'—'}</div>
                <div style={{fontSize:10,color:'var(--text-muted)',display:'flex',gap:12,marginTop:2}}>
                  <span>{e.start_year||'?'}–{e.is_current?'Present':(e.end_year||'?')}</span>
                  {e.is_academic_role && <span className="chip active" style={{fontSize:9,padding:'1px 6px'}}>Academic</span>}
                </div>
              </div>
            ))}
            {!detail.work_experiences.length && <div style={{fontSize:11,color:'var(--text-muted)'}}>No experience records</div>}
          </div>

          {/* Publications */}
          <div className="detail-section">
            <div className="detail-title">Publications ({detail.journal_publications.length + detail.conference_publications.length})</div>
            {detail.journal_publications.slice(0,5).map((p:any,i:number)=>(
              <div key={`j${i}`} style={{marginBottom:8}}>
                <div style={{fontSize:11,fontWeight:600,color:'var(--text-primary)'}}>{p.title}</div>
                <div style={{fontSize:10,color:'var(--text-muted)'}}>{p.journal_name} · {p.year} {p.quartile && `· ${p.quartile}`}</div>
              </div>
            ))}
            {detail.conference_publications.slice(0,5).map((p:any,i:number)=>(
              <div key={`c${i}`} style={{marginBottom:8}}>
                <div style={{fontSize:11,fontWeight:600,color:'var(--text-primary)'}}>{p.title}</div>
                <div style={{fontSize:10,color:'var(--text-muted)'}}>{p.conference_name} · {p.year} {p.core_ranking && `· ${p.core_ranking}`}</div>
              </div>
            ))}
            {detail.journal_publications.length + detail.conference_publications.length > 10 &&
              <div style={{fontSize:10,color:'var(--text-muted)',marginTop:4}}>
                +{detail.journal_publications.length + detail.conference_publications.length - 10} more
              </div>}
          </div>

          {/* Skills */}
          <div className="detail-section">
            <div className="detail-title">Skills ({detail.skills.length})</div>
            <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
              {detail.skills.map((s:any,i:number)=>(
                <span key={i} className={`chip ${s.strength_of_evidence?.includes('Strongly')?'active':''}`}>{s.name}</span>
              ))}
            </div>
            {!detail.skills.length && <div style={{fontSize:11,color:'var(--text-muted)'}}>No skills extracted</div>}
          </div>
        </div>

        {/* Missing Info */}
        {missingInfo.length > 0 && (
          <div className="section" style={{marginTop:20}}>
            <div className="section-head">Missing Information Requests ({missingInfo.length})</div>
            {missingInfo.map((m,i)=>(
              <div key={i} style={{marginBottom:16}}>
                <div style={{display:'flex',gap:8,alignItems:'center',marginBottom:8}}>
                  <span className="chip active">{m.module_name}</span>
                  <span className={`status-badge ${m.status==='draft'?'pending':'completed'}`}>{m.status}</span>
                  <span style={{fontSize:10,color:'var(--text-muted)'}}>
                    {m.missing_fields.length} field{m.missing_fields.length!==1?'s':''}
                  </span>
                </div>
                <div style={{fontSize:11,color:'var(--text-secondary)',marginBottom:6}}>
                  {m.missing_fields.map((f,j)=><div key={j} style={{paddingLeft:12}}>• {f}</div>)}
                </div>
                {m.draft_email_subject && (
                  <div className="email-preview">
                    <div className="email-subject">📧 {m.draft_email_subject}</div>
                    <div className="email-body">{m.draft_email_body}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="app">
      <div className="navbar">
        <div className="navbar-logo"/>
        <div className="navbar-title">TALASH — Smart HR Recruitment</div>
        <div className="nav-tabs">
          <button className={`nav-tab ${view==='upload'?'active':''}`} onClick={()=>setView('upload')}>Upload</button>
          <button className={`nav-tab ${view==='dashboard'?'active':''}`} onClick={()=>setView('dashboard')}>Dashboard</button>
        </div>
      </div>
      {view === 'upload' && renderUpload()}
      {view === 'dashboard' && renderDashboard()}
      {view === 'detail' && renderDetail()}
    </div>
  );
};

export default App;
