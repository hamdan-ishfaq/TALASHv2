import React, { useRef } from 'react';
import axios from 'axios';
import { UploadQueueItem } from '../types';

interface UploadViewProps {
  uploadQueue: UploadQueueItem[];
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>;
  dragOver: boolean;
  setDragOver: (b: boolean) => void;
  setError: (msg: string|null) => void;
}

const API = 'http://localhost:8000';

export const UploadView: React.FC<UploadViewProps> = ({
  uploadQueue, setUploadQueue, dragOver, setDragOver, setError
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setError(null);
    const file = files[0];
    const item: UploadQueueItem = { name: file.name, status: 'queued', progress: 0 };
    setUploadQueue(prev => [...prev, item]);
    const idx = uploadQueue.length;

    const fd = new FormData();
    fd.append('file', file);

    try {
      const res = await axios.post(`${API}/upload`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (ev) => {
          if (ev.total) {
            const pct = Math.round((ev.loaded * 100) / ev.total);
            setUploadQueue(prev => {
              const n = [...prev];
              n[idx].progress = pct;
              return n;
            });
          }
        }
      });
      setUploadQueue(prev => {
        const n = [...prev];
        n[idx].status = 'processing';
        n[idx].cid = res.data.candidate_id;
        return n;
      });
    } catch (e: any) {
      setUploadQueue(prev => {
        const n = [...prev];
        n[idx].status = 'failed';
        return n;
      });
      setError(e.response?.data?.detail || 'Upload failed');
    }
  };

  return (
    <div className="view-transition">
      <div className="page-header">
        <h1>CV Upload & Ingestion Setup</h1>
        <p>Upload candidate CVs to extract data, analyze research profiles, and rank against job configurations.</p>
      </div>

      <div className="two-col">
        {/* Left Panel - Job Configuration */}
        <div className="section 3d-card">
          <div className="section-head">Job Configuration</div>
          
          <div className="form-group">
            <label className="form-label">Target Role</label>
            <input type="text" className="form-input" defaultValue="Faculty Position — Computer Science" />
          </div>

          <div className="form-group">
            <label className="form-label">Role Skills Required</label>
            <div className="chips">
              <span className="chip active">Machine Learning</span>
              <span className="chip active">Deep Learning</span>
              <span className="chip active">PhD Supervision</span>
              <span className="chip">Research Publications</span>
              <span className="chip">Grant Writing</span>
            </div>
          </div>

          <div className="form-group" style={{marginTop: '24px'}}>
            <label className="form-label">System Status</label>
            <div className="system-status-box">
              <div className="dot dot-solid"></div>
              <span>Ready to ingest</span>
            </div>
          </div>
        </div>

        {/* Right Panel - Upload Queue */}
        <div className="section 3d-card">
          <div className="section-head">CV Upload & Queue</div>
          
          <div 
            className={`dropzone ${dragOver ? 'dragover' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => {
              e.preventDefault();
              setDragOver(false);
              handleUpload(e.dataTransfer.files);
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="drop-icon-wrapper">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
            </div>
            <div className="drop-text">Drag & drop CVs here</div>
            <div className="drop-sub">.pdf, .docx up to 10MB</div>
            <input 
              type="file" 
              style={{display:'none'}} 
              ref={fileInputRef}
              onChange={e => handleUpload(e.target.files)}
              accept=".pdf,.doc,.docx"
            />
          </div>

          <div className="queue-header">
            <span className="form-label" style={{marginBottom:0}}>Processing Queue</span>
            <span className="queue-count">{uploadQueue.length} files</span>
          </div>

          <div className="queue-list">
            {uploadQueue.map((q, i) => (
              <div key={i} className="queue-item">
                <span className="queue-item-name">{q.name}</span>
                <div className="progress">
                  <div className="progress-fill" style={{width: `${q.progress}%`}} />
                </div>
                <span className={`queue-badge badge-${q.status}`}>
                  {q.status === 'processing' ? 'Processing...' :
                   q.status === 'done' ? 'Done ✓' :
                   q.status === 'failed' ? 'Failed ✗' : 'Queued'}
                </span>
              </div>
            ))}
            {uploadQueue.length === 0 && (
              <div style={{fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '10px'}}>
                No files in queue.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
