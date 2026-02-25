import React from 'react';

/**
 * Key React Concept: Props pass data from parent to child, like arguments to a function.
 * We receive analytics data and display it as 4 cards.
 */
export default function StatCards({ analytics = {} }) {
  const stats = [
    {
      label: 'LOGS PROCESSED',
      value: analytics.total_logs || 0,
      icon: '📊',
      glow: 'shadow-[0_0_15px_rgba(59,130,246,0.2)]',
    },
    {
      label: 'ERROR EVENTS',
      value: analytics.error_count || 0,
      icon: '❌',
      glow: 'shadow-[0_0_15px_rgba(244,63,94,0.2)]',
    },
    {
      label: 'ANOMALIES',
      value: analytics.anomaly_count || 0,
      icon: '⚠️',
      glow: 'shadow-[0_0_15px_rgba(245,158,11,0.2)]',
    },
    {
      label: 'FAILURE RATE',
      value: `${(analytics.error_rate || 0).toFixed(1)}%`,
      icon: '📈',
      glow: 'shadow-[0_0_15px_rgba(16,185,129,0.2)]',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat, idx) => (
        <div
          key={idx}
          className={`glass-card group relative overflow-hidden ${stat.glow}`}
        >
          <div className="absolute top-0 right-0 p-3 opacity-20 group-hover:opacity-40 transition-opacity text-2xl">
            {stat.icon}
          </div>
          <p className="text-[10px] font-bold text-muted uppercase tracking-widest mb-2">
            {stat.label}
          </p>
          <h3 className="text-3xl font-bold font-mono tracking-tighter">
            {stat.value}
          </h3>
          <div className="mt-4 w-full h-1 bg-white/5 rounded-full overflow-hidden">
            <div className="h-full bg-accent w-2/3 group-hover:w-full transition-all duration-700 ease-out opacity-30" />
          </div>
        </div>
      ))}
    </div>
  );
}
