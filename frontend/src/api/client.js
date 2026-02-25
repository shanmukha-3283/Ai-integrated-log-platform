import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE_URL });

/**
 * Upload a log file to the backend
 * @param {File} file - The file to upload
 * @param {Function} onProgress - Callback for upload progress (0-100)
 * @returns {Promise} Response data with jobId
 */
export async function uploadLog(file, onProgress = () => { }) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/upload-log", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (progressEvent) => {
      const percent = Math.round(
        (progressEvent.loaded / progressEvent.total) * 100
      );
      onProgress(percent);
    },
  });

  return response.data;
}

/**
 * Get job status and results
 * @param {string} jobId - The job ID to fetch
 * @returns {Promise} Job data with status and results
 */
export async function getJob(jobId) {
  const response = await api.get(`/jobs/${jobId}`);
  return response.data;
}

/**
 * Fetch logs with optional filters
 * @param {Object} filters - Query filters (service, level, search, etc.)
 * @returns {Promise} Logs array and pagination info
 */
export async function getLogs(filters = {}) {
  const response = await api.get("/logs", { params: filters });
  return response.data;
}

/**
 * Fetch analytics (total logs, errors, anomalies, etc.)
 * @returns {Promise} Analytics data
 */
export async function getAnalytics() {
  const response = await api.get("/analytics");
  return response.data;
}

/**
 * Stream AI analysis using Server-Sent Events
 * @param {string} query - User question
 * @param {Array} logIds - Optional array of log IDs to analyze
 * @param {Function} onToken - Callback for each token received
 * @param {Function} onComplete - Callback when stream is done
 */
export async function askAI(query, logIds = [], onToken = () => { }, onComplete = () => { }, model = 'gpt-4o') {
  const payload = { query, log_ids: logIds, model };

  try {
    const response = await fetch(`${BASE_URL}/ask-ai`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");

      for (let i = 0; i < lines.length - 1; i++) {
        const line = lines[i];
        if (line.startsWith("data: ")) {
          try {
            const jsonStr = line.slice(6);
            const json = JSON.parse(jsonStr);
            if (json.done) {
              onComplete(json.result);
            } else if (json.token) {
              onToken(json.token);
            }
          } catch (e) {
            console.error("Error parsing JSON:", e);
          }
        }
      }

      buffer = lines[lines.length - 1];
    }
  } catch (error) {
    console.error("Error in askAI:", error);
    onComplete({ error: "Failed to get AI response" });
  }
}
