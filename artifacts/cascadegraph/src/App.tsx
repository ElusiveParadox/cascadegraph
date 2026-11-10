import { type ReactNode } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { createQueryClient } from '@/lib/query-client';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Shell } from '@/components/shell';
import NotFound from '@/pages/not-found';
import Overview from '@/pages/overview';
import AnalysisPage from '@/pages/analysis';
import PoliciesPage from '@/pages/policies';
import SimulationPage from '@/pages/simulation';
import ComparisonPage from '@/pages/comparison';
import ValidationPage from '@/pages/validation';
import ReportPage from '@/pages/report';
import HelpPage from '@/pages/help';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';

const queryClient = createQueryClient();

function Router() {
  return (
    <Shell>
      <RoutedErrorBoundary>
        <Switch>
          <Route path="/" component={Overview} />
          <Route path="/analyses/:id" component={AnalysisPage} />
          <Route path="/policies/:id" component={PoliciesPage} />
          <Route path="/simulation/:id" component={SimulationPage} />
          <Route path="/comparison/:id" component={ComparisonPage} />
          <Route path="/reports/:id" component={ReportPage} />
          <Route path="/validation" component={ValidationPage} />
          <Route path="/help" component={HelpPage} />
          <Route component={NotFound} />
        </Switch>
      </RoutedErrorBoundary>
    </Shell>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
