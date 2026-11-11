import { type ReactNode, useEffect, useMemo, useRef } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { ClerkProvider, useClerk, useUser } from '@clerk/react';
import { publishableKeyFromHost } from '@clerk/react/internal';
import { shadcn } from '@clerk/themes';
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
import { AuthCallbackPage, SignInPage, SignUpPage } from '@/pages/auth';
import { AUTH_UNAVAILABLE, AuthStateProvider, clearBrowserCookie, useAuthState, type AuthState } from '@/lib/auth-context';
import { writeSelection } from '@/lib/workspace';
import { Redirect, Route, Switch, useLocation, Router as WouterRouter } from 'wouter';

const clerkPubKey = publishableKeyFromHost(
  window.location.hostname,
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY,
);

const clerkProxyUrl = import.meta.env.VITE_CLERK_PROXY_URL;

const basePath = import.meta.env.BASE_URL.replace(/\/$/, '');

function stripBase(path: string): string {
  return basePath && path.startsWith(basePath)
    ? path.slice(basePath.length) || '/'
    : path;
}

const queryClient = createQueryClient();

const clerkAppearance = {
  theme: shadcn,
  cssLayerName: 'clerk',
  options: {
    logoPlacement: 'inside' as const,
    logoLinkUrl: basePath || '/',
    logoImageUrl: `${window.location.origin}${basePath}/logo.svg`,
  },
  variables: {
    colorPrimary: '#E6002B',
    colorForeground: '#131215',
    colorMutedForeground: '#5A5960',
    colorDanger: '#CC0026',
    colorBackground: '#FBFBF9',
    colorInput: '#F5F5F2',
    colorInputForeground: '#131215',
    colorNeutral: '#131215',
    fontFamily: "'Poppins', ui-sans-serif, system-ui, sans-serif",
    borderRadius: '0.5rem',
  },
  elements: {
    rootBox: 'w-full flex justify-center',
    cardBox: 'bg-[#FBFBF9] border border-[#E4E4E6] rounded-xl w-[440px] max-w-full overflow-hidden shadow-[0_2px_0_0_rgba(19,18,21,0.06)]',
    card: '!shadow-none !border-0 !bg-transparent !rounded-none',
    footer: '!shadow-none !border-0 !bg-transparent !rounded-none',
    headerTitle: 'text-[#131215] font-semibold tracking-tight',
    headerSubtitle: 'text-[#5A5960] font-[Georgia] italic',
    socialButtonsBlockButtonText: 'text-[#131215] font-medium',
    formFieldLabel: 'text-[#131215] font-medium',
    footerActionLink: 'text-[#E6002B] font-medium hover:text-[#B80022]',
    footerActionText: 'text-[#5A5960]',
    dividerText: 'text-[#5A5960]',
    identityPreviewEditButton: 'text-[#E6002B]',
    formFieldSuccessText: 'text-[#1E6B4E]',
    alertText: 'text-[#131215]',
    logoBox: 'h-10 justify-center',
    logoImage: 'h-10 w-10',
    socialButtonsBlockButton: 'border border-[#D6D6D9] bg-[#F5F5F2] hover:bg-[#E4E4E6]',
    formButtonPrimary: 'bg-[#E6002B] text-[#F5F5F2] hover:bg-[#C70025] shadow-none',
    formFieldInput: 'bg-[#F5F5F2] border border-[#C9C9CD] text-[#131215]',
    footerAction: 'bg-[#F0F0EC] border-t border-[#E4E4E6]',
    dividerLine: 'bg-[#E4E4E6]',
    alert: 'bg-[#FCEBEE] border border-[#F3B8C3]',
    otpCodeFieldInput: 'border border-[#C9C9CD] text-[#131215]',
    formFieldRow: 'gap-1',
    main: 'gap-5',
  },
};

/** Anonymous demo stays public; a signed-in visitor lands on the workspace alias. */
function HomeRoute() {
  const { ready, signedIn } = useAuthState();
  if (ready && signedIn) return <Redirect to="/workspace" />;
  return <Overview />;
}

function WorkspaceRoute() {
  const { ready, signedIn } = useAuthState();
  if (ready && !signedIn) return <Redirect to="/" />;
  return <Overview />;
}

/** Hold account-scoped content until identity resolves so no prior-account data flashes. */
function AuthReadyBoundary({ children }: { children: ReactNode }) {
  const { ready } = useAuthState();
  if (!ready) {
    return (
      <div className="space-y-4" aria-busy="true" data-testid="status-auth-loading">
        <div className="h-8 w-64 animate-pulse rounded-md bg-muted" />
        <div className="h-4 w-96 max-w-full animate-pulse rounded bg-muted" />
        <div className="h-48 animate-pulse rounded-xl bg-muted/70" />
      </div>
    );
  }
  return <>{children}</>;
}

function WorkspaceRoutes() {
  return (
    <Shell>
      <RoutedErrorBoundary>
        <AuthReadyBoundary>
          <Switch>
            <Route path="/" component={HomeRoute} />
            <Route path="/workspace" component={WorkspaceRoute} />
            <Route path="/analyses/:id" component={AnalysisPage} />
            <Route path="/policies/:id" component={PoliciesPage} />
            <Route path="/simulation/:id" component={SimulationPage} />
            <Route path="/comparison/:id" component={ComparisonPage} />
            <Route path="/reports/:id" component={ReportPage} />
            <Route path="/validation" component={ValidationPage} />
            <Route path="/help" component={HelpPage} />
            <Route component={NotFound} />
          </Switch>
        </AuthReadyBoundary>
      </RoutedErrorBoundary>
    </Shell>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/auth/callback" component={AuthCallbackPage} />
      <Route path="/sign-in/*?" component={SignInPage} />
      <Route path="/sign-up/*?" component={SignUpPage} />
      <Route component={WorkspaceRoutes} />
    </Switch>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

/**
 * Clears account-scoped state when the identity changes. The first observation
 * (initial load) only records the identity, so guest navigation survives.
 */
function IdentityTransitionGuard() {
  const { addListener } = useClerk();
  const prevUserIdRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    const unsubscribe = addListener(({ user }) => {
      if (user === undefined) return; // not resolved yet
      const userId = user?.id ?? null;
      if (prevUserIdRef.current !== undefined && prevUserIdRef.current !== userId) {
        writeSelection({ analysisId: undefined, simulationId: undefined });
      }
      prevUserIdRef.current = userId;
    });
    return unsubscribe;
  }, [addListener]);
  return null;
}

function ClerkAuthBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, user } = useUser();
  const clerk = useClerk();
  const signOutRef = useRef(clerk.signOut);
  signOutRef.current = clerk.signOut;
  const value = useMemo<AuthState>(() => ({
    available: true,
    ready: isLoaded,
    signedIn: !!isSignedIn,
    displayName: user?.fullName || user?.username || null,
    email: user?.primaryEmailAddress?.emailAddress ?? null,
    signOut: async () => {
      await clearBrowserCookie();
      await signOutRef.current({ redirectUrl: basePath || '/' });
    },
  }), [isLoaded, isSignedIn, user]);
  return <AuthStateProvider value={value}>{children}</AuthStateProvider>;
}

function AppBody() {
  return (
    <TooltipProvider>
      <Router />
      <Toaster />
    </TooltipProvider>
  );
}

/** Never expose a previous identity's cached records, even for one render. */
function IdentityScopedQueries() {
  const { isLoaded, user } = useUser();
  const identity = isLoaded ? (user?.id ?? 'guest') : 'loading';
  const client = useMemo(() => createQueryClient(), [identity]);
  useEffect(() => () => {
    void client.cancelQueries().finally(() => client.clear());
  }, [client]);
  return (
    <>
      <IdentityTransitionGuard />
      <QueryClientProvider key={identity} client={client}>
        <ClerkAuthBridge>
          <AppBody />
        </ClerkAuthBridge>
      </QueryClientProvider>
    </>
  );
}

function ClerkProviderWithRoutes() {
  const [, setLocation] = useLocation();
  return (
    <ClerkProvider
      publishableKey={clerkPubKey}
      proxyUrl={clerkProxyUrl}
      appearance={clerkAppearance}
      signInUrl={`${basePath}/sign-in`}
      signUpUrl={`${basePath}/sign-up`}
      localization={{
        signIn: { start: { title: 'Sign in to CascadeGraph', subtitle: 'Keep your analyses and simulations with your account' } },
        signUp: { start: { title: 'Create your CascadeGraph account', subtitle: 'Source-backed retry analysis, saved to you' } },
      }}
      routerPush={(to) => setLocation(stripBase(to))}
      routerReplace={(to) => setLocation(stripBase(to), { replace: true })}
    >
      <IdentityScopedQueries />
    </ClerkProvider>
  );
}

function App() {
  return (
    <WouterRouter base={basePath}>
      {clerkPubKey ? (
        <ClerkProviderWithRoutes />
      ) : (
        // No key (local/CI): anonymous workbench only, with an explicit unavailable state.
        <QueryClientProvider client={queryClient}>
          <AuthStateProvider value={AUTH_UNAVAILABLE}>
            <AppBody />
          </AuthStateProvider>
        </QueryClientProvider>
      )}
    </WouterRouter>
  );
}

export default App;
