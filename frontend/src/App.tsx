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
import TemplateManagerPage from '@/pages/TemplateManagerPage'; // This path might need checking for actual file vs alias
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
import VoScriptListView from '@/pages/VoScriptListView'; // Path alias check
import VoScriptCreateView from '@/pages/VoScriptCreateView'; // Path alias check
import VoScriptDetailView from '@/pages/VoScriptDetailView'; // Path alias check
import { ChatDrawer } from './components/chat/ChatDrawer'; // Changed from ChatModal

const queryClient = new QueryClient();

const RankingPageRouteWrapper: React.FC = () => {
  const params = useParams<{ '*' : string }>();
  const batchPrefix = params['*'];
  if (!batchPrefix) {
    return <p>Error: Missing Batch Prefix in URL.</p>;
  }
  return (
    <RankingProvider batchId={batchPrefix}> 
      <RankingPage />
    </RankingProvider>
  );
};

const AppLayout: React.FC = () => {
  const [opened, { toggle }] = useDisclosure();
  const location = useLocation();
  const handleNavClick = () => { if (opened) { toggle(); } };

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 200, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
      styles={{
        main: {
          width: '100%',
          maxWidth: '100%',
          minHeight: 'calc(100vh - 60px)'
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
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="md">
        <NavLink label="Create Scripts" component={Link} to="/vo-scripts" active={location.pathname.startsWith('/vo-scripts')} onClick={handleNavClick} style={(theme) => ({ borderLeft: location.pathname.startsWith('/vo-scripts') ? `3px solid ${theme.colors.blue[6]}` : 'none', paddingLeft: location.pathname.startsWith('/vo-scripts') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md, })} />
        <NavLink label="Create Voices" component={Link} to="/voice-design" active={location.pathname === '/voice-design' || location.pathname === '/'} onClick={handleNavClick} style={(theme) => ({ borderLeft: (location.pathname === '/voice-design' || location.pathname === '/') ? `3px solid ${theme.colors.blue[6]}` : 'none', paddingLeft: (location.pathname === '/voice-design' || location.pathname === '/') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md, })} />
        <NavLink label="Generate Recordings" component={Link} to="/generate" active={location.pathname === '/generate'} onClick={handleNavClick} style={(theme) => ({ borderLeft: location.pathname === '/generate' ? `3px solid ${theme.colors.blue[6]}` : 'none', paddingLeft: location.pathname === '/generate' ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md, })} /> 
        <NavLink label="Monitor Generations" component={Link} to="/jobs" active={location.pathname === '/jobs'} onClick={handleNavClick} style={(theme) => ({ borderLeft: location.pathname === '/jobs' ? `3px solid ${theme.colors.blue[6]}` : 'none', paddingLeft: location.pathname === '/jobs' ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md, })} />
        <NavLink label="Edit Recordings" component={Link} to="/batches" active={location.pathname.startsWith('/batch') || location.pathname === '/batches'} onClick={handleNavClick} style={(theme) => ({ borderLeft: (location.pathname.startsWith('/batch') || location.pathname === '/batches') ? `3px solid ${theme.colors.blue[6]}` : 'none', paddingLeft: (location.pathname.startsWith('/batch') || location.pathname === '/batches') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md, })} />
        <NavLink label="Manage Templates" component={Link} to="/script-templates" active={location.pathname.startsWith('/script-templates')} onClick={handleNavClick} style={(theme) => ({ borderLeft: location.pathname.startsWith('/script-templates') ? `3px solid ${theme.colors.blue[6]}` : 'none', paddingLeft: location.pathname.startsWith('/script-templates') ? `calc(${theme.spacing.md} - 3px)` : theme.spacing.md, })} />
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet /> 
      </AppShell.Main>
      <ChatDrawer />
    </AppShell>
  );
}

const App: React.FC = () => {
  return (
    <MantineProvider>
      <QueryClientProvider client={queryClient}>
        <Notifications />
        <VoiceProvider>
          <Router>
            <Routes>
              <Route path="/" element={<AppLayout />}>
                <Route index element={<VoiceDesignPage />} />
                <Route path="voice-design" element={<VoiceDesignPage />} />
                <Route path="scripts" element={<ManageScriptsPage />} />
                <Route path="scripts/new" element={<ScriptEditorPage />} />
                <Route path="scripts/:scriptId" element={<ScriptEditorPage />} />
                <Route path="script-templates" element={<TemplateManagerPage />} />
                <Route path="vo-scripts" element={<VoScriptListView />} />
                <Route path="vo-scripts/new" element={<VoScriptCreateView />} />
                <Route path="vo-scripts/:scriptId" element={<VoScriptDetailView />} />
                <Route path="batch/*" element={<RankingPageRouteWrapper />} />
                <Route path="batches" element={<BatchesPage />} />
                <Route path="jobs" element={<JobsPage />} />
                <Route path="generate" element={<GenerationPage />} />
              </Route>
            </Routes>
          </Router>
        </VoiceProvider>
      </QueryClientProvider>
    </MantineProvider>
  );
};

export default App;
