import React from 'react';
import { BrowserRouter as Router, Route, Routes, Link, useParams } from 'react-router-dom';
import { MantineProvider, AppShell, Burger, Group, NavLink, Image, Text, Box } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import GenerationPage from './pages/GenerationPage';
import RankingPage from './pages/RankingPage';
import BatchesPage from './pages/BatchesPage';
import JobsPage from './pages/JobsPage';
import VoiceDesignPage from './pages/VoiceDesignPage';
import ManageScriptsPage from './pages/ManageScriptsPage';
import ScriptEditorPage from './pages/ScriptEditorPage';
import { VoiceProvider } from './contexts/VoiceContext';
import { RankingProvider } from './contexts/RankingContext';
import { Notifications } from '@mantine/notifications';
import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import '@mantine/dates/styles.css';
import 'rc-slider/assets/index.css';
import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query';

// Create a client
const queryClient = new QueryClient();

// NEW: Wrapper component to correctly call useParams
const RankingPageRouteWrapper: React.FC = () => {
  // Use '*' to access the wildcard parameter value
  const params = useParams<{ '*' : string }>();
  const batchPrefix = params['*']; // Get the captured prefix

  if (!batchPrefix) { // Check if the prefix exists
    // Handle case where batchPrefix is missing, maybe redirect or show error
    return <p>Error: Missing Batch Prefix in URL.</p>;
  }
  // Pass the full prefix to the provider/page
  return (
    <RankingProvider batchId={batchPrefix}> 
      <RankingPage />
    </RankingProvider>
  );
};

const App: React.FC = () => {
  const [opened, { toggle }] = useDisclosure();

  return (
    <MantineProvider>
      <Notifications />
      <VoiceProvider>
        <Router>
          <AppShell
            header={{ height: 60 }}
            navbar={{ width: 200, breakpoint: 'sm', collapsed: { mobile: !opened } }}
            padding="md"
            styles={{
              main: {
                width: '100%',
                maxWidth: '100%'
              }
            }}
          >
            <AppShell.Header>
              <Group h="100%" px="md" justify="space-between">
                <Box style={{ display: 'flex', alignItems: 'center' }}>
                  <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" mr="md" />
                  <Image src="/images/color_normal.svg" alt="Logo" h={30} w="auto" mr="sm" />
                  <Text size="lg" fw={500}>Voiceover Assistant</Text>
                </Box>
                {/* Add any other header elements here if needed */}
              </Group>
            </AppShell.Header>

            <AppShell.Navbar p="md">
              <NavLink label="Create Voices" component={Link} to="/voice-design" onClick={toggle} />
              <NavLink label="Manage Scripts" component={Link} to="/scripts" onClick={toggle} />
              <NavLink label="Generate Recordings" component={Link} to="/" onClick={toggle} />
              <NavLink label="Monitor Generations" component={Link} to="/jobs" onClick={toggle} />
              <NavLink label="Edit Recordings" component={Link} to="/batches" onClick={toggle} />
            </AppShell.Navbar>

            <AppShell.Main>
              <Routes>
                <Route path="/scripts" element={<ManageScriptsPage />} />
                <Route path="/scripts/new" element={<ScriptEditorPage />} />
                <Route path="/scripts/:scriptId" element={<ScriptEditorPage />} />
                <Route path="/voice-design" element={<VoiceDesignPage />} />
                <Route path="/batch/*" element={<RankingPageRouteWrapper />} />
                <Route path="/batches" element={<BatchesPage />} />
                <Route path="/jobs" element={<JobsPage />} />
                <Route path="/" element={<GenerationPage />} />
              </Routes>
            </AppShell.Main>
          </AppShell>
        </Router>
      </VoiceProvider>
    </MantineProvider>
  );
};

export default App;
