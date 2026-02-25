import React, { useState, useEffect, useRef } from 'react';
import { getAnalytics, getLogs } from './api/client';
import StatCards from './components/StatCards';
import AnomalyChart from './components/AnomalyChart';
import LogUploader from './components/LogUploader';
import LogTable from './components/LogTable';
import AskAI from './components/AskAI';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [analytics, setAnalytics] = useState({});
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [filters, setFilters] = useState({});
  const [health, setHealth] = useState(false);
  const analyticsIntervalRef = useRef(null);

  // Fetch analytics data
  const fetchAnalytics = async () => {
    try {
      const data = await getAnalytics();
      setAnalytics(data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  // Fetch logs with filters
  const fetchLogs = async (pageNum = 1, filtersObj = filters) => {
    try {
      const response = await getLogs({
        page: pageNum,
        ...filtersObj,
      });
      setLogs(response.logs || []);
      setTotal(response.total || 0);
      setPage(pageNum);
      setPages(response.pages || 1);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  // Check backend health
  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      setHealth(response.ok);
    } catch {
      setHealth(false);
    }
  };

  // On mount: fetch initial data and set up auto-refresh
  useEffect(() => {
    const init = async () => {
      await fetchAnalytics();
      await fetchLogs(1);
      await checkHealth();
    };

    init();

    // Auto-refresh analytics every 30 seconds
    analyticsIntervalRef.current = setInterval(() => {
      fetchAnalytics();
      checkHealth();
    }, 30000);

    return () => {
      if (analyticsIntervalRef.current) {
        clearInterval(analyticsIntervalRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle uploader completion
  const handleUploadComplete = () => {
    fetchAnalytics();
    fetchLogs(1);
  };

  // Handle filter changes
  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
    fetchLogs(1, newFilters);
  };

  // Handle page changes
  const handlePageChange = (newPage) => {
    fetchLogs(newPage, filters);
  };

  return (
    <div className="min-h-screen bg-bg text-text relative overflow-hidden">
      {/* Background Glow Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-[#10b98110] rounded-full blur-[120px] pointer-events-none animate-float" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[35%] h-[35%] bg-[#00d4ff10] rounded-full blur-[100px] pointer-events-none animate-float" style={{ animationDelay: '-2s' }} />

      {/* Navbar */}
      <nav className="navbar">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-accent rounded-xl flex items-center justify-center text-xl shadow-[0_0_20px_rgba(16,185,129,0.3)]">
              ⚡
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">AI Log Platform</h1>
              <p className="text-[10px] text-muted uppercase tracking-[0.2em] font-semibold">Intelligent Observability</p>
            </div>
          </div>

          <div className="flex items-center gap-8">
            <div className="flex gap-2">
              {[
                { id: 'dashboard', label: 'Overview' },
                { id: 'logs', label: 'Monitor' },
                { id: 'askai', label: 'AI Analysis' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-3 bg-white/5 px-4 py-2 rounded-full border border-white/10">
              <span
                className={`w-2 h-2 rounded-full ${health ? 'bg-success shadow-[0_0_8px_#10b981] animate-pulse' : 'bg-error shadow-[0_0_8px_#f43f5e]'}`}
              />
              <span className="text-xs font-medium text-muted"> {health ? 'Live' : 'Offline'}</span>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-10 relative z-10">
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div className="space-y-10">
            <StatCards analytics={analytics} />
            <div className="glass-card">
              <h2 className="text-lg font-bold mb-6">Log Frequency Trends</h2>
              <AnomalyChart data={analytics.hourly_data || []} />
            </div>
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div className="space-y-8 animate-fadeIn">
            <LogUploader onComplete={handleUploadComplete} />
            <LogTable
              logs={logs}
              total={total}
              page={page}
              pages={pages}
              onFilterChange={handleFilterChange}
              onPageChange={handlePageChange}
            />
          </div>
        )}

        {/* Ask AI Tab */}
        {activeTab === 'askai' && (
          <div className="animate-fadeIn">
            <AskAI />
          </div>
        )}
      </main>
    </div>
  );
}
