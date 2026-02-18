export const API_BASE = "http://127.0.0.1:8000";

export const apiClient = {
    // Papers
    getPapers: async () => {
        const res = await fetch(`${API_BASE}/papers`);
        if (!res.ok) throw new Error("Failed to fetch papers");
        return res.json();
    },

    // Jobs
    runDeepRead: async (paperId) => {
        const res = await fetch(`${API_BASE}/jobs/deepread`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                paper_id: paperId,
                clean_reindex: false
            }),
        });
        if (!res.ok) throw new Error("Failed to start job");
        return res.json(); // { job_id, ... }
    },

    getJobStatus: async (jobId) => {
        const res = await fetch(`${API_BASE}/jobs/${jobId}`);
        if (!res.ok) throw new Error("Failed to fetch job status");
        return res.json();
    },

    cancelJob: async (jobId) => {
        const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, {
            method: "POST",
        });
        if (!res.ok) throw new Error("Failed to cancel job");
        return res.json();
    },

    // SSE Helper
    getJobEventSource: (jobId) => {
        return new EventSource(`${API_BASE}/jobs/${jobId}/events`);
    }
};
