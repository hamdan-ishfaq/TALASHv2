import React, { useState, useCallback } from 'react';
import axios from 'axios';
import './index.css';

interface EducationRecord {
  degree_level?: string;
  title?: string;
  institution?: string;
  passing_year?: number;
  cgpa?: number;
}

interface WorkExperience {
  job_title?: string;
  organization?: string;
  location?: string;
  start_date?: string;
  end_date?: string;
  is_current?: boolean;
}

interface Publication {
  title?: string;
  authors?: string[];
  venue?: string;
  year?: number;
  type?: string;
}

interface Skill {
  name?: string;
  proficiency_level?: string;
  years_of_experience?: number;
}

interface Candidate {
  id?: number;
  name?: string;
  email?: string;
  status?: string;
  file_path?: string;
  raw_text?: string;
  summary?: string;
}

interface ExtractedData {
  candidate: Candidate;
  education: EducationRecord[];
  experience: WorkExperience[];
  publications: Publication[];
  skills: Skill[];
}

interface CandidateApiResponse {
  id?: number;
  name?: string;
  email?: string;
  status?: string;
  file_path?: string;
  raw_text?: string;
  summary?: string;
  education_records?: EducationRecord[];
  work_experiences?: WorkExperience[];
  publications?: Array<Publication & { authors?: string[] | string }>;
  skills?: Skill[];
}

interface ProcessingCandidate {
  filename: string;
  status: 'queued' | 'processing' | 'complete' | 'error';
  progress: number;
  candidateId?: number;
}

const App: React.FC = () => {
  const [view, setView] = useState<'upload' | 'results' | 'overview'>('upload');
  const [processingQueue, setProcessingQueue] = useState<ProcessingCandidate[]>([]);
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const API_URL = 'http://localhost:8000';

  const normalizeCandidateData = (data: CandidateApiResponse): ExtractedData => ({
    candidate: {
      id: data.id,
      name: data.name,
      email: data.email,
      status: data.status,
      file_path: data.file_path,
      raw_text: data.raw_text,
      summary: data.summary,
    },
    education: data.education_records ?? [],
    experience: data.work_experiences ?? [],
    publications: (data.publications ?? []).map((pub) => ({
      ...pub,
      authors: (() => {
        const rawAuthors = pub.authors as unknown;
        if (Array.isArray(rawAuthors)) {
          return rawAuthors as string[];
        }
        if (typeof rawAuthors === 'string') {
          return rawAuthors.split(',').map((s) => s.trim()).filter(Boolean);
        }
        return [];
      })(),
    })),
    skills: data.skills ?? [],
  });

  const monitorCandidateProcessing = useCallback((candidateId: number, filename: string) => {
    let attempts = 0;
    const maxAttempts = 180;

    const pollInterval = window.setInterval(async () => {
      attempts += 1;
      try {
        const dataResponse = await axios.get(`${API_URL}/candidates/${candidateId}`);
        const data = dataResponse.data as CandidateApiResponse;
        const status = (data.status ?? '').toLowerCase();

        if (status === 'completed') {
          setProcessingQueue((prev) =>
            prev.map((item) =>
              item.filename === filename
                ? { ...item, status: 'complete', progress: 100, candidateId }
                : item
            )
          );
          setExtractedData(normalizeCandidateData(data));
          setView('results');
          window.clearInterval(pollInterval);
          return;
        }

        if (status === 'failed' || status === 'error') {
          setProcessingQueue((prev) =>
            prev.map((item) =>
              item.filename === filename
                ? { ...item, status: 'error', progress: 0, candidateId }
                : item
            )
          );
          setError(`Processing failed for ${filename}`);
          window.clearInterval(pollInterval);
          return;
        }

        setProcessingQueue((prev) =>
          prev.map((item) =>
            item.filename === filename
              ? {
                  ...item,
                  status: 'processing',
                  progress: status === 'processing' ? 70 : 35,
                  candidateId,
                }
              : item
          )
        );

        if (attempts >= maxAttempts) {
          setError(`Timed out waiting for ${filename} to finish processing`);
          window.clearInterval(pollInterval);
        }
      } catch {
        if (attempts >= maxAttempts) {
          setError(`Could not fetch status for ${filename}`);
          window.clearInterval(pollInterval);
        }
      }
    }, 2000);
  }, []);

  const handleFileSelect = useCallback(async (files: FileList) => {
    if (!files || files.length === 0) return;

    setError(null);
    setLoading(true);

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const filename = file.name;

      // Add to queue
      setProcessingQueue((prev) => [
        ...prev,
        { filename, status: 'queued', progress: 10 },
      ]);

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await axios.post(`${API_URL}/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        if (response.data.candidate_id) {
          const backendStatus = (response.data.status ?? '').toLowerCase();
          const isImmediateComplete = backendStatus === 'completed';

          setProcessingQueue((prev) =>
            prev.map((item) =>
              item.filename === filename
                ? {
                    ...item,
                    status: isImmediateComplete ? 'complete' : 'queued',
                    progress: isImmediateComplete ? 100 : 25,
                    candidateId: response.data.candidate_id,
                  }
                : item
            )
          );

          monitorCandidateProcessing(response.data.candidate_id, filename);
        }
      } catch (err: any) {
        setProcessingQueue((prev) =>
          prev.map((item) =>
            item.filename === filename
              ? { ...item, status: 'error', progress: 0 }
              : item
          )
        );
        setError(err.response?.data?.detail || `Failed to process ${filename}`);
      }
    }

    setLoading(false);
  }, [monitorCandidateProcessing]);

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      handleFileSelect(e.target.files);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '—';
    return dateString;
  };

  const renderUploadView = () => (
    <div className="container">
      <div className="two-col">
        {/* Left Panel */}
        <div className="section">
          <div className="section-head">Job Configuration</div>

          <div className="field">
            <label className="label">Target Role</label>
            <input
              type="text"
              className="input"
              value="Associate Prof — Machine Learning"
              disabled
            />
          </div>

          <div className="field">
            <label className="label">Role Skills Required</label>
            <div style={{ marginTop: 6 }}>
              <span className="chip active">Machine Learning</span>
              <span className="chip active">Deep Learning</span>
              <span className="chip active">PhD Supervision</span>
              <span className="chip">Research Publications</span>
              <span className="chip">Grant Writing</span>
            </div>
          </div>

          <div className="field">
            <label className="label">System Status</label>
            <div className="status-bar">
              <div className="dot solid"></div>
              <span style={{ fontWeight: 600 }}>Ready to ingest</span>
            </div>
          </div>

          <button className="btn">[ Initialize System ]</button>
        </div>

        {/* Right Panel */}
        <div className="section">
          <div className="section-head">CV Upload &amp; Queue</div>

          <div
            className={`dropzone ${dragOver ? 'dragover' : ''}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="drop-icon">
              <svg viewBox="0 0 16 16" style={{ width: 16, height: 16, stroke: '#999', fill: 'none', strokeWidth: 1.5 }}>
                <polyline points="8 2 8 10" />
                <polyline points="5 7 8 10 11 7" />
                <rect x="2" y="11" width="12" height="3" rx="1" />
              </svg>
            </div>
            <div className="drop-text">Drag &amp; drop CVs here</div>
            <div className="drop-sub">.pdf · .docx</div>
            <label className="btn-sm" style={{ cursor: 'pointer', marginTop: 6 }}>
              Browse files
              <input
                type="file"
                multiple
                accept=".pdf,.docx"
                onChange={handleInputChange}
                style={{ display: 'none' }}
              />
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <label className="label" style={{ marginBottom: 0 }}>
              Processing Queue
            </label>
            <span style={{ fontSize: 9, color: '#888' }}>
              {processingQueue.filter((q) => q.status === 'complete').length} /{' '}
              {processingQueue.length}{' '}
              complete
            </span>
          </div>

          {processingQueue.length === 0 ? (
            <div style={{ padding: 8, textAlign: 'center', color: '#aaa', fontSize: 9 }}>
              No files queued
            </div>
          ) : (
            processingQueue.map((item, idx) => (
              <div key={idx} className="queue-item">
                <span style={{ flex: 1 }}>{item.filename}</span>
                <div className="progress">
                  <div
                    className="progress-fill"
                    style={{ width: `${item.progress}%` }}
                  />
                </div>
                <span className={`badge ${item.status === 'complete' ? 'complete' : ''}`}>
                  {item.status === 'processing'
                    ? 'Extracting…'
                    : item.status === 'complete'
                      ? '✓ Done'
                      : item.status === 'error'
                        ? '✗ Error'
                        : '⧐ Queued'}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="annotation">
        Milestone 1 scope: Basic CV upload, folder monitoring setup, and initial extraction
        pipeline. Full multi-candidate processing and advanced analysis deferred to Milestone
        2–3.
      </div>
    </div>
  );

  const renderResultsView = () => (
    <div className="container">
      {error && <div className="error">Error: {error}</div>}

      {extractedData && (
        <>
          {/* Metrics Row */}
          <div className="two-col" style={{ marginBottom: 20 }}>
            <div className="metric-card">
              <div className="metric-label">Candidate Name</div>
              <div className="metric-value" style={{ fontSize: 16 }}>
                {extractedData.candidate.name || 'Unknown'}
              </div>
              <div className="metric-sub">
                {extractedData.candidate.file_path || 'No file'} · Parsed
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Education Records</div>
              <div className="metric-value">{extractedData.education?.length || 0}</div>
              <div className="metric-sub">Records extracted</div>
            </div>
          </div>

          {/* Data Summary Cards */}
          <div className="two-col" style={{ marginBottom: 20 }}>
            <div className="section">
              <div className="section-head">Personal Information</div>
              <div className="data-row">
                <span className="data-label">Name:</span>
                <span className="data-value">{extractedData.candidate.name || 'N/A'}</span>
              </div>
              <div className="data-row">
                <span className="data-label">Email:</span>
                <span className="data-value">{extractedData.candidate.email || 'N/A'}</span>
              </div>
              <div className="data-row">
                <span className="data-label">Status:</span>
                <span className="data-value">{extractedData.candidate.status || 'Unknown'}</span>
              </div>
            </div>

            <div className="section">
              <div className="section-head">Quick Stats</div>
              <div className="data-row">
                <span className="data-label">Education:</span>
                <span className="data-value">{extractedData.education?.length || 0} records</span>
              </div>
              <div className="data-row">
                <span className="data-label">Experience:</span>
                <span className="data-value">{extractedData.experience?.length || 0} records</span>
              </div>
              <div className="data-row">
                <span className="data-label">Publications:</span>
                <span className="data-value">{extractedData.publications?.length || 0} records</span>
              </div>
              <div className="data-row">
                <span className="data-label">Skills:</span>
                <span className="data-value">{extractedData.skills?.length || 0} records</span>
              </div>
            </div>
          </div>

          {/* Education Table */}
          <div style={{ marginBottom: 20 }}>
            <div className="section-head">Education Records</div>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: '25%' }}>Degree</th>
                  <th style={{ width: '30%' }}>Institution</th>
                  <th style={{ width: '15%' }}>Year</th>
                  <th style={{ width: '15%' }}>CGPA</th>
                </tr>
              </thead>
              <tbody>
                {extractedData.education && extractedData.education.length > 0 ? (
                  extractedData.education.map((edu, idx) => (
                    <tr key={idx}>
                      <td>{edu.degree_level || edu.title || '—'}</td>
                      <td>{edu.institution || '—'}</td>
                      <td>{edu.passing_year || '—'}</td>
                      <td>{edu.cgpa || '—'}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', color: '#aaa' }}>
                      No education records extracted
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Experience Table */}
          <div style={{ marginBottom: 20 }}>
            <div className="section-head">Experience Records</div>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: '20%' }}>Job Title</th>
                  <th style={{ width: '25%' }}>Organization</th>
                  <th style={{ width: '25%' }}>Location</th>
                  <th style={{ width: '30%' }}>Duration</th>
                </tr>
              </thead>
              <tbody>
                {extractedData.experience && extractedData.experience.length > 0 ? (
                  extractedData.experience.map((exp, idx) => (
                    <tr key={idx}>
                      <td>{exp.job_title || '—'}</td>
                      <td>{exp.organization || '—'}</td>
                      <td>{exp.location || '—'}</td>
                      <td>{formatDate(exp.start_date)} – {formatDate(exp.end_date)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', color: '#aaa' }}>
                      No experience records extracted
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Publications */}
          {extractedData.publications && extractedData.publications.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div className="section-head">Publications ({extractedData.publications.length})</div>
              <div className="section">
                {extractedData.publications.slice(0, 5).map((pub, idx) => (
                  <div key={idx} style={{ marginBottom: idx < extractedData.publications.length - 1 ? 8 : 0, fontSize: 9 }}>
                    <strong>{pub.title || 'Untitled'}</strong>
                    <div style={{ color: '#666', marginTop: 2 }}>
                      {pub.authors && pub.authors.length > 0 ? pub.authors.slice(0, 2).join(', ') : 'No authors'}
                      {pub.year && ` (${pub.year})`}
                    </div>
                  </div>
                ))}
                {extractedData.publications.length > 5 && (
                  <div style={{ color: '#888', fontSize: 8, marginTop: 8 }}>
                    ... and {extractedData.publications.length - 5} more
                  </div>
                )}
              </div>
            </div>
          )}

          <button
            className="btn"
            onClick={() => {
              setExtractedData(null);
              setProcessingQueue([]);
              setView('upload');
            }}
            style={{ marginBottom: 20 }}
          >
            [ Process Another CV ]
          </button>

          <div className="annotation">
            Milestone 1: Raw extracted data displayed. Full LLM analysis (research profile,
            skill alignment, gap detection) deferred to Milestone 2–3.
          </div>
        </>
      )}

      {!extractedData && !loading && (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
          <p>Upload a CV to see extraction results</p>
          <button
            className="btn"
            style={{ maxWidth: 200, margin: '12px auto' }}
            onClick={() => setView('upload')}
          >
            [ Back to Upload ]
          </button>
        </div>
      )}

      {loading && (
        <div className="loading">
          <p>Processing extracted data...</p>
        </div>
      )}
    </div>
  );

  return (
    <div className="app">
      <div className="navbar">
        <div className="navbar-logo"></div>
        <div className="navbar-title">TALASH — Smart HR Recruitment (Milestone 1)</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
          <button
            className={`btn-sm ${view === 'upload' ? 'active' : ''}`}
            onClick={() => setView('upload')}
            style={{ fontWeight: view === 'upload' ? 600 : 400 }}
          >
            Upload
          </button>
          <button
            className={`btn-sm ${view === 'results' ? 'active' : ''}`}
            onClick={() => setView('results')}
            style={{ fontWeight: view === 'results' ? 600 : 400 }}
          >
            Results
          </button>
        </div>
      </div>

      {view === 'upload' && renderUploadView()}
      {view === 'results' && renderResultsView()}
    </div>
  );
};

export default App;
