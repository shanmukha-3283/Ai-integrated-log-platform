import React, { useState, useRef, useEffect } from 'react';
import { uploadLog, getJob } from '../api/client';

export default function LogUploader({ onComplete }) {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("Queued");
  const [progress, setProgress] = useState(0);
  const [jobId, setJobId] = useState(null);
  const [displayText, setDisplayText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (status === "Processing" && jobId) {
      intervalRef.current = setInterval(async () => {
        try {
          const job = await getJob(jobId);
          if (job.status === "completed") {
            setStatus("Completed");
            setProgress(100);
            setDisplayText(`Successfully processed ${job.processed_count || 0} logs.`);
            clearInterval(intervalRef.current);
            if (onComplete) onComplete();
          } else if (job.status === "failed") {
            setStatus("Failed");
            setDisplayText(`Processing failed: ${job.error || "Unknown error"}`);
            clearInterval(intervalRef.current);
          }
        } catch (error) {
          console.error("Error fetching job:", error);
        }
      }, 2000);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [status, jobId, onComplete]);

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setStatus("Queued");
      setProgress(0);
      setJobId(null);
      setDisplayText("");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
      setStatus("Queued");
      setProgress(0);
      setJobId(null);
      setDisplayText("");
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setStatus("Uploading");
    setProgress(0);
    setJobId(null);
    setDisplayText("");

    try {
      const result = await uploadLog(file, (percent) => {
        setProgress(percent);
      });
      setJobId(result.job_id);
      setStatus("Processing");
      setDisplayText("Analyzing log patterns...");
    } catch (error) {
      setStatus("Failed");
      setDisplayText(`Upload failed: ${error.message}`);
    }
  };

  return (
    <div className={`glass-card p-1 ${isDragging ? 'ring-2 ring-accent ring-offset-4 ring-offset-bg' : ''} transition-all duration-300`}>
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        className={`upload-zone px-8 py-12 text-center rounded-[0.9rem] ${isDragging ? 'active' : ''}`}
      >
        <div className="mb-6">
          <div className="text-4xl mb-4 animate-float inline-block">🛸</div>
          <h3 className="text-lg font-bold mb-1 tracking-tight">Transmission Uplink</h3>
          <p className="text-muted text-xs uppercase tracking-widest font-semibold mb-6 italic opacity-60">Upload system logs for AI scanning</p>

          <input
            type="file"
            onChange={handleFileSelect}
            disabled={status === "Uploading" || status === "Processing"}
            className="hidden"
            id="file-input"
          />
          <label
            htmlFor="file-input"
            className={`cursor-pointer px-8 py-3 bg-white/5 border border-white/10 rounded-xl font-bold text-sm hover:bg-white/10 transition-all ${status !== 'Queued' ? 'opacity-50 pointer-events-none' : ''}`}
          >
            Select System Log
          </label>
        </div>

        {file && status === "Queued" && (
          <div className="max-w-md mx-auto p-4 bg-accent/5 rounded-xl border border-accent/20 animate-fadeIn">
            <div className="flex items-center justify-between text-left">
              <div>
                <p className="text-[10px] font-bold text-accent uppercase tracking-wider mb-1">Target Identified</p>
                <div className="text-sm font-mono truncate max-w-[200px]">{file.name}</div>
              </div>
              <div className="text-xs text-muted font-mono">{(file.size / 1024).toFixed(1)} KB</div>
            </div>
            <button
              onClick={handleUpload}
              className="w-full mt-4 btn-primary text-sm uppercase tracking-widest"
            >
              Initiate Upload
            </button>
          </div>
        )}

        {(status === "Uploading" || status === "Processing") && (
          <div className="max-w-md mx-auto mt-6 animate-fadeIn">
            <div className="flex justify-between items-end mb-2">
              <span className="text-[10px] font-bold uppercase tracking-[0.2em]">{status}</span>
              <span className="text-sm font-mono text-accent">{progress}%</span>
            </div>
            <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden border border-white/5">
              <div
                className="h-full bg-gradient-to-r from-[#10b981] via-[#00d4ff] to-[#10b981] bg-[length:200%_100%] animate-loading transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            <p className="text-[11px] text-muted italic mt-3">{displayText}</p>
          </div>
        )}

        {status === "Completed" && (
          <div className="max-w-md mx-auto mt-6 p-4 bg-success/5 border border-success/20 rounded-xl animate-scaleIn">
            <div className="flex items-center gap-3 text-success">
              <span className="text-xl">✅</span>
              <div className="text-left">
                <p className="text-[10px] font-bold uppercase tracking-widest">Scanning Complete</p>
                <p className="text-sm font-medium">{displayText}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
