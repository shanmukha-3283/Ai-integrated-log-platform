import React, { useState } from 'react';
import { askAI } from '../api/client';

export default function AskAI() {
  const [query, setQuery] = useState('');
  const [model, setModel] = useState('gpt-4o');
  const [response, setResponse] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

  const models = [
    { id: 'gpt-4o', name: 'GPT-4o', desc: 'Fast & Intelligent' },
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', desc: 'Deep Analysis' },
    { id: 'gpt-3.5-turbo', name: 'GPT-3.5', desc: 'Efficiency' },
  ];

  const handleAsk = async () => {
    if (!query.trim()) return;

    setIsStreaming(true);
    setResponse('');

    const tokenBuffer = [];

    await askAI(
      query,
      [],
      (token) => {
        tokenBuffer.push(token);
        setResponse(tokenBuffer.join(''));
      },
      (result) => {
        setIsStreaming(false);
        if (result.error) {
          setResponse(`Error: ${result.error}`);
        } else {
          if (typeof result === 'object') {
            setResponse(JSON.stringify(result, null, 2));
          } else {
            setResponse(result);
          }
        }
      },
      model // Pass the selected model
    );
  };

  const parseResponse = (text) => {
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  };

  const parsed = parseResponse(response);

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fadeIn">
      <div className="glass-card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Neural Link</h2>
            <p className="text-[10px] text-muted uppercase tracking-[0.2em] font-semibold">Direct AI Consultation</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-bold text-muted uppercase tracking-widest">Target Model</span>
            <div className="flex bg-white/5 p-1 rounded-xl border border-white/10">
              {models.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setModel(m.id)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all ${model === m.id ? 'bg-accent text-[#030712] shadow-[0_0_10px_#10b981]' : 'text-muted hover:text-text'
                    }`}
                >
                  {m.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={isStreaming}
          placeholder="Translate log anomalies into actionable insights..."
          rows="4"
          className="w-full px-5 py-4 bg-black/40 text-text border border-white/10 rounded-2xl resize-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all outline-none text-sm leading-relaxed"
        />

        <div className="flex gap-4 mt-6">
          <button
            onClick={handleAsk}
            disabled={!query.trim() || isStreaming}
            className="flex-1 btn-primary py-3.5 uppercase tracking-[0.2em] text-xs"
          >
            {isStreaming ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-2 h-2 bg-black rounded-full animate-ping" />
                Interrogating...
              </span>
            ) : 'Initiate Inquiry'}
          </button>
          <button
            onClick={() => { setQuery(''); setResponse(''); }}
            className="px-8 py-3.5 bg-white/5 border border-white/10 rounded-xl text-xs font-bold uppercase tracking-widest hover:bg-white/10 transition-all"
          >
            Reset
          </button>
        </div>
      </div>

      {response && (
        <div className="glass-card !bg-black/20 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-accent opacity-50 shadow-[0_0_15px_#10b981]" />
          <h3 className="text-xs font-bold uppercase tracking-[0.3em] text-muted mb-6 flex items-center gap-2">
            <span className="w-2 h-2 bg-accent rounded-full animate-pulse shadow-[0_0_5px_#10b981]" />
            Intelligence Protocol Response
          </h3>

          {parsed ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-sm">
              <div className="space-y-6">
                <div>
                  <label className="text-[10px] font-bold text-accent uppercase tracking-widest mb-2 block">Identified Root Cause</label>
                  <p className="text-white font-medium leading-relaxed">{parsed.cause}</p>
                </div>

                <div className="flex gap-8">
                  <div>
                    <label className="text-[10px] font-bold text-muted uppercase tracking-widest mb-2 block">Confidence Level</label>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${parsed.confidence === 'HIGH' ? 'text-emerald-400 border-emerald-400/20 bg-emerald-400/5' : 'text-amber-400 border-amber-400/20 bg-amber-400/5'
                      }`}>
                      {parsed.confidence}
                    </span>
                  </div>
                  <div>
                    <label className="text-[10px] font-bold text-muted uppercase tracking-widest mb-2 block">Threat Severity</label>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${parsed.severity === 'CRITICAL' ? 'text-red-400 border-red-400/20 bg-red-400/5 shadow-[0_0_10px_rgba(244,63,94,0.1)]' : 'text-orange-400 border-orange-400/20 bg-orange-400/5'
                      }`}>
                      {parsed.severity}
                    </span>
                  </div>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-muted uppercase tracking-widest mb-3 block">Compromised Sectors</label>
                  <div className="flex flex-wrap gap-2">
                    {parsed.affected_services?.map((s, i) => (
                      <span key={i} className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-[11px] font-mono text-white/80">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-6 bg-white/[0.02] p-5 rounded-2xl border border-white/5">
                <div>
                  <label className="text-[10px] font-bold text-accent uppercase tracking-widest mb-2 block">Strategic Recommendation</label>
                  <p className="text-white/80 italic leading-relaxed text-xs">{parsed.recommendation}</p>
                </div>
                <div>
                  <label className="text-[10px] font-bold text-muted uppercase tracking-widest mb-2 block">Tactical Resolution</label>
                  <p className="text-white/80 leading-relaxed text-xs">{parsed.solution}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="ai-box font-mono text-xs leading-loose text-white/70 min-h-[100px] border-none !p-0">
              {response.split('').map((char, i) => (
                <span key={i} className="ai-token">{char}</span>
              ))}
              {isStreaming && <span className="inline-block w-1.5 h-4 bg-accent ml-1 animate-pulse" />}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
