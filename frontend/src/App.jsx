import { useState } from 'react'
import PaperList from './components/PaperList'
import JobMonitor from './components/JobMonitor'

function App() {
  const [activeJobId, setActiveJobId] = useState(null)

  const handleJobStarted = (jobId) => {
    setActiveJobId(jobId)
  }

  const handleJobComplete = (finalStatus) => {
    console.log(`Job ended with status: ${finalStatus}`)
    // We keep the monitor open so user can see the final log/status
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-6xl mx-auto bg-white shadow rounded-lg p-6">
        <header className="mb-6 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">PaperPipe Control</h1>
          <div className="text-sm text-gray-500">v3.1 MVP</div>
        </header>

        {activeJobId && (
          <div className="mb-8 p-4 bg-gray-50 border border-gray-200 rounded">
            <h2 className="text-lg font-semibold text-gray-800 mb-2">Active Job Monitor</h2>
            <JobMonitor jobId={activeJobId} onComplete={handleJobComplete} />

            <div className="text-right mt-2">
              <button
                onClick={() => setActiveJobId(null)}
                className="text-sm text-gray-400 hover:text-gray-600 underline"
              >
                Close Monitor
              </button>
            </div>
          </div>
        )}

        <section>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Paper Queue</h2>
            <button
              onClick={() => window.location.reload()}
              className="text-sm text-blue-600 hover:underline"
            >
              Refresh List
            </button>
          </div>
          <PaperList onJobStarted={handleJobStarted} />
        </section>
      </div>
    </div>
  )
}

export default App
