import { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';

export default function JobMonitor({ jobId, onComplete }) {
    const [status, setStatus] = useState({ status: 'connecting', progress: 0, stage: 'Connecting...' });
    const [logs, setLogs] = useState([]);
    const [isCancelled, setIsCancelled] = useState(false);
    const eventSourceRef = useRef(null);
    const logEndRef = useRef(null);

    useEffect(() => {
        if (!jobId) return;

        // Connect SSE
        const es = apiClient.getJobEventSource(jobId);
        eventSourceRef.current = es;

        es.onmessage = (event) => {
            // Generic message handler (rarely used if named events match)
            console.log("SSE Message:", event.data);
        };

        es.addEventListener('status', (e) => {
            try {
                const data = JSON.parse(e.data);
                setStatus(data);
            } catch (err) {
                console.error("Status parse error", err);
            }
        });

        es.addEventListener('log', (e) => {
            setLogs((prev) => [...prev, e.data]);
        });

        es.addEventListener('done', (e) => {
            console.log("Job Done:", e.data);
            setStatus((prev) => ({ ...prev, status: e.data, progress: 100 }));
            es.close();
            if (onComplete) onComplete(e.data);
        });

        es.addEventListener('error', (e) => {
            console.error("SSE Error:", e);
            // Check standard EventSource error state
            if (e.target.readyState === EventSource.CLOSED) {
                setStatus((prev) => ({ ...prev, status: 'connection_lost' }));
            } else {
                // Some browsers send error event on connection issues
                // We might want to retry or just show error
            }
        });

        return () => {
            es.close();
        };
    }, [jobId]);

    // Auto-scroll logs
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const handleCancel = async () => {
        if (!confirm("Are you sure you want to cancel this job?")) return;
        try {
            await apiClient.cancelJob(jobId);
            setIsCancelled(true);
            // Status update should come via SSE or we force it
            setStatus((prev) => ({ ...prev, status: 'cancelling...' }));
        } catch (err) {
            alert("Failed to cancel: " + err.message);
        }
    };

    // Status Colors
    const getStatusColor = (s) => {
        switch (s) {
            case 'completed': return 'text-green-600';
            case 'failed': return 'text-red-600';
            case 'cancelled': return 'text-orange-600';
            case 'running': return 'text-blue-600';
            default: return 'text-gray-600';
        }
    };

    return (
        <div className="bg-white border rounded shadow p-4">
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h3 className="text-lg font-bold">Job Monitor: <span className="font-mono text-sm text-gray-500">{jobId}</span></h3>
                    <div className={`text-md font-semibold ${getStatusColor(status.status)}`}>
                        {status.status.toUpperCase()}
                        <span className="text-gray-400 text-sm ml-2">({status.stage})</span>
                    </div>
                </div>
                <div>
                    {['queued', 'running', 'connecting'].includes(status.status) && (
                        <button
                            onClick={handleCancel}
                            disabled={isCancelled}
                            className="bg-red-100 text-red-700 px-3 py-1 rounded hover:bg-red-200 text-sm font-medium"
                        >
                            {isCancelled ? 'Cancelling...' : 'Stop Job'}
                        </button>
                    )}
                </div>
            </div>

            {/* Progress Bar */}
            <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
                <div
                    className={`h-2.5 rounded-full ${status.status === 'failed' ? 'bg-red-500' : 'bg-blue-600'}`}
                    style={{ width: `${Math.max(5, status.progress)}%`, transition: 'width 0.5s' }}
                ></div>
            </div>

            {/* Terminal Log */}
            <div className="bg-gray-900 text-gray-100 font-mono text-xs p-3 rounded h-64 overflow-y-auto">
                {logs.length === 0 && <span className="text-gray-500 italic">Waiting for logs...</span>}
                {logs.map((line, i) => (
                    <div key={i} className="whitespace-pre-wrap border-b border-gray-800 pb-0.5 mb-0.5">{line}</div>
                ))}
                {status.status === 'completed' && <div className="text-green-400 mt-2">✨ Job Finished Successfully.</div>}
                {status.status === 'failed' && <div className="text-red-400 mt-2">❌ Job Failed.</div>}
                {status.status === 'cancelled' && <div className="text-orange-400 mt-2">🚫 Job Cancelled.</div>}
                <div ref={logEndRef} />
            </div>
        </div>
    );
}
