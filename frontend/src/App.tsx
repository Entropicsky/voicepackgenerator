import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  Navigate
} from 'react-router-dom';
import './App.css'

// Assuming placeholder pages exist
import GenerationPage from './pages/GenerationPage';
import JobsPage from './pages/JobsPage';
import BatchesPage from './pages/BatchesPage';
import RankingPage from './pages/RankingPage';

function App() {
  // Basic layout with navigation
  return (
    <Router>
      <div style={{ padding: '10px 20px' }}>
        <h1>Voice Generation & Ranking Tool</h1>
        <nav>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', gap: '15px' }}>
            <li>
              <Link to="/generate">Generate</Link>
            </li>
            <li>
              <Link to="/jobs">Jobs</Link>
            </li>
            <li>
              <Link to="/batches">Batches</Link>
            </li>
          </ul>
        </nav>

        <hr style={{ margin: '15px 0' }} />

        <Routes>
          <Route path="/generate" element={<GenerationPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/batches" element={<BatchesPage />} />
          <Route path="/batch/:batchId" element={<RankingPage />} />
          {/* Default route redirects to generate page */}
          <Route path="*" element={<Navigate to="/generate" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
