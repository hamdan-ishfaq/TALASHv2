import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './index.css';

import { DashCandidate, CandidateDetail, MissingReq, UploadQueueItem } from './types';
import { UploadView } from './components/UploadView';
import { DashboardView } from './components/DashboardView';
import { CandidateDetailView } from './components/CandidateDetailView';

const API = 'http://localhost:8000';

const App: React.FC = () => {
  const [view, setView] = useState<'upload'|'dashboard'|'detail'>('upload');
  const [candidates, setCandidates] = useState<DashCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<number|null>(null);
  const [detail, setDetail] = useState<CandidateDetail|null>(null);
  const [missingInfo, setMissingInfo] = useState<MissingReq[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string|null>(null);
  
  // Upload State
  const [dragOver, setDragOver] = useState(false);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);

  const fetchDashboard = useCallback(async (isPolling = false) => {
    if (!isPolling) setLoading(true); 
    setError(null);
    try {
      const r = await axios.get(`${API}/analysis/dashboard`);
      setCandidates(r.data.candidates || []);
    } catch (e: any) { setError(e.response?.data?.detail || 'Failed to load dashboard'); }
    if (!isPolling) setLoading(false);
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

  useEffect(() => { 
    if (view === 'dashboard') {
      fetchDashboard(false); 
      const interval = setInterval(() => fetchDashboard(true), 5000);
      return () => clearInterval(interval);
    }
  }, [view, fetchDashboard]);

  useEffect(() => { 
    if (view === 'detail' && selectedId) fetchDetail(selectedId); 
  }, [view, selectedId, fetchDetail]);

  const handleSelectCandidate = (id: number) => {
    setSelectedId(id);
    setView('detail');
  };

  return (
    <div className="app">
      {/* Navigation Bar */}
      <nav className="navbar">
        <div className="navbar-logo"></div>
        <div className="navbar-title">TALASH — Smart HR Recruitment</div>
        <div className="nav-tabs">
          <button className={`nav-tab ${view === 'upload' ? 'active' : ''}`} onClick={() => setView('upload')}>
            Upload
          </button>
          <button className={`nav-tab ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setView('dashboard')}>
            Dashboard
          </button>
        </div>
      </nav>

      {/* Main Content Container */}
      <main className="container">
        {error && <div className="alert alert-error">{error}</div>}
        
        {loading && view !== 'upload' ? (
          <div className="loading-container">
            <div className="spinner"></div>
            <div className="loading-text">Loading data...</div>
          </div>
        ) : (
          <>
            {view === 'upload' && (
              <UploadView 
                uploadQueue={uploadQueue} 
                setUploadQueue={setUploadQueue}
                dragOver={dragOver}
                setDragOver={setDragOver}
                setError={setError}
              />
            )}
            
            {view === 'dashboard' && (
              <DashboardView 
                candidates={candidates}
                onSelectCandidate={handleSelectCandidate}
              />
            )}

            {view === 'detail' && (
              <CandidateDetailView 
                detail={detail}
                missingInfo={missingInfo}
                onBack={() => setView('dashboard')}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
};

export default App;
