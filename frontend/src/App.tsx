import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
  Navigate
} from 'react-router-dom';
import { AppShell, Burger, Group, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import './App.css'

// Assuming placeholder pages exist
import GenerationPage from './pages/GenerationPage';
import JobsPage from './pages/JobsPage';
import BatchesPage from './pages/BatchesPage';
import RankingPage from './pages/RankingPage';
import VoiceDesignPage from './pages/VoiceDesignPage';

function App() {
  const [opened, { toggle }] = useDisclosure();

  // Define link style for NavLink
  const linkStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
      display: 'block',
      padding: '8px 12px',
      borderRadius: '4px',
      textDecoration: 'none',
      color: isActive ? 'var(--mantine-color-blue-filled)' : 'var(--mantine-color-text)',
      backgroundColor: isActive ? 'var(--mantine-color-blue-light)' : 'transparent',
      fontWeight: isActive ? 500 : 400,
  });

  return (
    <Router>
      <AppShell
        header={{ height: 60 }}
        navbar={{ width: 200, breakpoint: 'sm', collapsed: { mobile: !opened } }}
        padding="md"
      >
        <AppShell.Header>
          <Group h="100%" px="md">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={3}>Voice Generation & Ranking</Title>
          </Group>
        </AppShell.Header>

        <AppShell.Navbar p="md">
          <NavLink to="/voice-design" style={linkStyle} onClick={toggle}>Voice Design</NavLink>
          <NavLink to="/generate" style={linkStyle} onClick={toggle}>Generate</NavLink>
          <NavLink to="/jobs" style={linkStyle} onClick={toggle}>Jobs</NavLink>
          <NavLink to="/batches" style={linkStyle} onClick={toggle}>Batches</NavLink>
        </AppShell.Navbar>

        <AppShell.Main style={{ width: '100%', maxWidth: 'none' }}>
          <Routes>
            <Route path="/generate" element={<GenerationPage />} />
            <Route path="/voice-design" element={<VoiceDesignPage />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/batches" element={<BatchesPage />} />
            <Route path="/batch/:batchId" element={<RankingPage />} />
            <Route path="*" element={<Navigate to="/generate" replace />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </Router>
  );
}

export default App;
