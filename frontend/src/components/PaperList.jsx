import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export default function PaperList({ onJobStarted }) {
    const [papers, setPapers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [processingId, setProcessingId] = useState(null);

    useEffect(() => {
        fetchPapers();
    }, []);

    const fetchPapers = async () => {
        try {
            const data = await apiClient.getPapers();
            setPapers(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleRun = async (paperId) => {
        if (processingId) return; // Prevent double click
        setProcessingId(paperId);
        try {
            const { job_id } = await apiClient.runDeepRead(paperId);
            // Callback to parent to show monitor
            if (onJobStarted) onJobStarted(job_id, paperId);
            alert(`Job started: ${job_id}`);
        } catch (err) {
            alert(`Failed to start job: ${err.message}`);
        } finally {
            setProcessingId(null);
        }
    };

    if (loading) return <div className="p-4 text-center">Loading papers...</div>;
    if (error) return <div className="p-4 text-center text-red-500">Error: {error}</div>;

    return (
        <div className="overflow-x-auto shadow-md sm:rounded-lg">
            <table className="w-full text-sm text-left text-gray-500">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                    <tr>
                        <th scope="col" className="px-6 py-3">Status</th>
                        <th scope="col" className="px-6 py-3">Title</th>
                        <th scope="col" className="px-6 py-3">Updated At</th>
                        <th scope="col" className="px-6 py-3">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {papers.map((paper) => (
                        <tr key={paper.paper_id} className="bg-white border-b hover:bg-gray-50">
                            <td className="px-6 py-4">
                                <span className={`px-2 py-1 rounded text-xs font-semibold 
                  ${paper.status === 'INDEXED' ? 'bg-green-100 text-green-800' :
                                        paper.status === 'FAILED' ? 'bg-red-100 text-red-800' :
                                            'bg-gray-100 text-gray-800'}`}>
                                    {paper.status || 'NEW'}
                                </span>
                            </td>
                            <td className="px-6 py-4 font-medium text-gray-900 whitespace-nowrap overflow-hidden text-ellipsis max-w-md" title={paper.title}>
                                {paper.title || paper.paper_id}
                            </td>
                            <td className="px-6 py-4">
                                {new Date(paper.updated_at).toLocaleString()}
                            </td>
                            <td className="px-6 py-4">
                                <button
                                    onClick={() => handleRun(paper.paper_id)}
                                    disabled={!!processingId}
                                    className={`font-medium text-blue-600 hover:underline disabled:text-gray-400 disabled:cursor-not-allowed`}
                                >
                                    {processingId === paper.paper_id ? 'Starting...' : 'Run DeepRead'}
                                </button>
                            </td>
                        </tr>
                    ))}
                    {papers.length === 0 && (
                        <tr>
                            <td colSpan="4" className="px-6 py-4 text-center">No papers found in DB.</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}
