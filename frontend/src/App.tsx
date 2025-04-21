import React from 'react';
import { BrowserRouter as Router, Route, Routes, Link, useParams, useLocation, Outlet } from 'react-router-dom';
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

// --- App Layout Component --- 
// Contains the shell, header, navbar. Renders child routes via <Outlet />
const AppLayout: React.FC = () => {
  const [opened, { toggle }] = useDisclosure();
  const location = useLocation(); // Get current location

  // Helper function to close navbar on mobile after click
  const handleNavClick = () => {
    if (opened) {
      toggle();
    }
  };

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 200, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
      styles={{
        main: {
          width: '100%',
          maxWidth: '100%',
          // Ensure main area takes up space
          minHeight: 'calc(100vh - 60px)' // Subtract header height
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
        <NavLink 
          label="Create Voices" 
          component={Link} 
          to="/voice-design" 
          active={location.pathname === '/voice-design' || location.pathname === '/'} 
          onClick={handleNavClick} 
          style={(theme) => ({
            borderLeft: (location.pathname === '/voice-design' || location.pathname === '/') ? `3px solid ${theme.colors.blue[6]}` : 'none',
            paddingLeft: (location.pathname === '/voice-design' || location.pathname === '/') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md,
          })}
        />
        <NavLink 
          label="Manage Scripts" 
          component={Link} 
          to="/scripts" 
          active={location.pathname.startsWith('/scripts')} 
          onClick={handleNavClick} 
          style={(theme) => ({
            borderLeft: location.pathname.startsWith('/scripts') ? `3px solid ${theme.colors.blue[6]}` : 'none',
            paddingLeft: location.pathname.startsWith('/scripts') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md,
          })}
        />
        <NavLink 
          label="Generate Recordings" 
          component={Link} 
          to="/generate" 
          active={location.pathname === '/generate'} 
          onClick={handleNavClick} 
          style={(theme) => ({
            borderLeft: location.pathname === '/generate' ? `3px solid ${theme.colors.blue[6]}` : 'none',
            paddingLeft: location.pathname === '/generate' ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md,
          })}
        /> 
        <NavLink 
          label="Monitor Generations" 
          component={Link} 
          to="/jobs" 
          active={location.pathname === '/jobs'} 
          onClick={handleNavClick} 
          style={(theme) => ({
            borderLeft: location.pathname === '/jobs' ? `3px solid ${theme.colors.blue[6]}` : 'none',
            paddingLeft: location.pathname === '/jobs' ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md,
          })}
        />
        <NavLink 
          label="Edit Recordings" 
          component={Link} 
          to="/batches" 
          active={location.pathname.startsWith('/batch') || location.pathname === '/batches'} 
          onClick={handleNavClick} 
          style={(theme) => ({
            borderLeft: (location.pathname.startsWith('/batch') || location.pathname === '/batches') ? `3px solid ${theme.colors.blue[6]}` : 'none',
            paddingLeft: (location.pathname.startsWith('/batch') || location.pathname === '/batches') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md,
          })}
        />
      </AppShell.Navbar>

      {/* Render the matched child route's element here */}
      <AppShell.Main>
        <Outlet /> 
      </AppShell.Main>
    </AppShell>
  );
}

// --- Main App Component --- 
// Sets up providers, Router, and defines the route structure
const App: React.FC = () => {
  return (
    <MantineProvider>
      <QueryClientProvider client={queryClient}>
        <Notifications />
        <VoiceProvider>
          <Router>
            <Routes>
              {/* Route defining the main layout */}
              <Route path="/" element={<AppLayout />}>
                {/* Nested routes that will render inside AppLayout's Outlet */}
                <Route index element={<VoiceDesignPage />} /> {/* Default page for '/' */}
                <Route path="voice-design" element={<VoiceDesignPage />} />
                <Route path="scripts" element={<ManageScriptsPage />} />
                <Route path="scripts/new" element={<ScriptEditorPage />} />
                <Route path="scripts/:scriptId" element={<ScriptEditorPage />} />
                <Route path="batch/*" element={<RankingPageRouteWrapper />} />
                <Route path="batches" element={<BatchesPage />} />
                <Route path="jobs" element={<JobsPage />} />
                <Route path="generate" element={<GenerationPage />} />
                {/* Add a catch-all or Not Found route if desired */}
                {/* <Route path="*" element={<NotFoundPage />} /> */}
              </Route>
              {/* Routes outside the main layout (if any) could go here */}
            </Routes>
          </Router>
        </VoiceProvider>
      </QueryClientProvider>
    </MantineProvider>
  );
};

export default App;
