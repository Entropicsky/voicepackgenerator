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
import BatchListPage from './pages/BatchListPage';
import RankingPage from './pages/RankingPage';

function App() {
  // Basic layout with navigation
  return (
    <Router>
      <div>
        <h1>Voice Generation & Ranking Tool</h1>
        <nav>
          <ul>
            <li>
              <Link to="/generate">Generate</Link>
            </li>
            <li>
              <Link to="/batches">Rank Batches</Link>
            </li>
          </ul>
        </nav>

        <hr />

        <Routes>
          <Route path="/generate" element={<GenerationPage />} />
          <Route path="/batches" element={<BatchListPage />} />
          <Route path="/batch/:batchId" element={<RankingPage />} />
          {/* Default route redirects to generate page */}
          <Route path="*" element={<Navigate to="/generate" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
