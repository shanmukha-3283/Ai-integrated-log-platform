import React, { useState } from 'react';

export default function LogTable({
  logs = [],
  page = 1,
  pages = 1,
  onFilterChange = () => { },
  onPageChange = () => { },
}) {
  const [filters, setFilters] = useState({
    service: '',
    level: '',
    anomaly_threshold: 0.5,
    search: '',
  });
  const [expandedRow, setExpandedRow] = useState(null);

  const handleFilterChange = (name, value) => {
    const newFilters = { ...filters, [name]: value };
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  const getLevelBadge = (level) => {
    const base = "badge ";
    switch (level?.toUpperCase()) {
      case 'ERROR': return <span className={base + "bg-red-500/10 text-red-500 border border-red-500/20 shadow-[0_0_10px_rgba(244,63,94,0.1)]"}>{level}</span>;
      case 'WARN': return <span className={base + "bg-amber-500/10 text-amber-500 border border-amber-500/20 shadow-[0_0_10px_rgba(245,158,11,0.1)]"}>{level}</span>;
      case 'INFO': return <span className={base + "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]"}>{level}</span>;
      default: return <span className={base + "bg-white/5 text-muted border border-white/10"}>{level}</span>;
    }
  };

  const getAnomalyGlow = (score) => {
    if (score > 0.7) return 'bg-red-500 shadow-[0_0_12px_#f43f5e]';
    if (score > 0.4) return 'bg-amber-500 shadow-[0_0_12px_#f59e0b]';
    return 'bg-emerald-500 shadow-[0_0_12px_#10b981]';
  };

  return (
    <div className="glass-card !p-0 overflow-hidden animate-fadeIn">
      {/* Filters Overlay */}
      <div className="p-6 bg-white/[0.02] border-b border-white/10 grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-muted uppercase tracking-widest pl-1">Search Feed</label>
          <input
            type="text"
            placeholder="Regex search..."
            value={filters.search}
            onChange={(e) => handleFilterChange('search', e.target.value)}
            className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm focus:border-accent/40 focus:bg-white/[0.08] transition-all outline-none"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-muted uppercase tracking-widest pl-1">Origin Service</label>
          <input
            type="text"
            placeholder="Service name..."
            value={filters.service}
            onChange={(e) => handleFilterChange('service', e.target.value)}
            className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm focus:border-accent/40 focus:bg-white/[0.08] transition-all outline-none"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-muted uppercase tracking-widest pl-1">Importance</label>
          <select
            value={filters.level}
            onChange={(e) => handleFilterChange('level', e.target.value)}
            className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm focus:border-accent/40 focus:bg-white/[0.08] transition-all outline-none appearance-none"
          >
            <option value="">All Levels</option>
            <option value="ERROR">CRITICAL/ERROR</option>
            <option value="WARN">WARNING</option>
            <option value="INFO">INFORMATION</option>
          </select>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between items-center pl-1">
            <label className="text-[10px] font-bold text-muted uppercase tracking-widest">Anomaly Sensitivity</label>
            <span className="text-[10px] font-mono text-accent">{filters.anomaly_threshold.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={filters.anomaly_threshold}
            onChange={(e) => handleFilterChange('anomaly_threshold', parseFloat(e.target.value))}
            className="w-full mt-3 h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-accent"
          />
        </div>
      </div>

      {/* Table Body */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-white/5 bg-white/[0.01]">
              <th className="px-6 py-4 text-left">Internal Timestamp</th>
              <th className="px-6 py-4 text-left">Level</th>
              <th className="px-6 py-4 text-left">Source Service</th>
              <th className="px-6 py-4 text-left">Payload Message</th>
              <th className="px-6 py-4 text-left">Analysis Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05]">
            {logs.length === 0 ? (
              <tr>
                <td colSpan="5" className="px-6 py-12 text-center">
                  <div className="text-muted italic text-sm">No transmissions detected on current frequency</div>
                </td>
              </tr>
            ) : (
              logs.map((log, idx) => (
                <React.Fragment key={idx}>
                  <tr
                    onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                    className={`group cursor-pointer transition-colors ${expandedRow === idx ? 'bg-white/[0.03]' : 'hover:bg-white/[0.02]'}`}
                  >
                    <td className="px-6 py-4">
                      <div className="text-[11px] font-mono text-muted group-hover:text-text transition-colors">
                        {new Date(log.timestamp).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {getLevelBadge(log.level)}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm font-semibold tracking-tight text-white/90">{log.service || 'Kernel'}</span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-white/70 max-w-md truncate group-hover:text-white transition-colors">
                        {log.message || log.raw_line}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex-1 w-20 h-1 bg-white/5 rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ${getAnomalyGlow(log.anomaly_score || 0)}`}
                            style={{ width: `${((log.anomaly_score || 0) * 100).toFixed(0)}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-mono font-bold text-muted w-8">
                          {((log.anomaly_score || 0) * 10).toFixed(1)}
                        </span>
                      </div>
                    </td>
                  </tr>
                  {expandedRow === idx && (
                    <tr className="bg-black/20 animate-fadeIn">
                      <td colSpan="5" className="px-8 py-6">
                        <div className="ai-box !p-4 !bg-[#030712] rounded-2xl">
                          <div className="text-[10px] font-bold text-accent uppercase tracking-widest mb-3 flex items-center gap-2">
                            Full Transmission Log
                          </div>
                          <pre className="text-xs font-mono text-white/60 whitespace-pre-wrap leading-relaxed">
                            {log.raw_line || JSON.stringify(log, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modern Pagination */}
      <div className="px-6 py-4 bg-white/[0.01] border-t border-white/10 flex items-center justify-between">
        <div className="text-xs font-medium text-muted uppercase tracking-widest">
          Transmissions <span className="text-white ml-2">{logs.length} of {total}</span>
        </div>
        <div className="flex items-center gap-6">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page === 1}
            className="p-2 hover:bg-white/10 disabled:opacity-30 rounded-lg transition-colors"
            title="Previous Page"
          >
            ←
          </button>
          <div className="text-xs font-mono font-bold px-3 py-1 bg-white/5 rounded-md border border-white/10">
            {page} / {pages}
          </div>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page === pages}
            className="p-2 hover:bg-white/10 disabled:opacity-30 rounded-lg transition-colors"
            title="Next Page"
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
}
