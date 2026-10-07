import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom'
import Shell from './components/Shell'
import { StoreProvider } from './lib/store'
import Today from './pages/Today'
// Today loads with the app; every other screen is fetched when first opened (smaller first load).
const Teams = lazy(() => import('./pages/Teams'))
const Investigate = lazy(() => import('./pages/Investigate'))
const Plans = lazy(() => import('./pages/Plans'))
const Review = lazy(() => import('./pages/Review'))
const Insights = lazy(() => import('./pages/Insights'))
const Ask = lazy(() => import('./pages/Ask'))
const DataSources = lazy(() => import('./pages/DataSources'))
const Value = lazy(() => import('./pages/Value'))
const Trust = lazy(() => import('./pages/Trust'))
const Sus = lazy(() => import('./pages/Sus'))

// v0.7 tabs map to the questions on the v0.8 Investigate screen.
const TAB_TO_FOCUS: Record<string, string> = { overview: 'real', drivers: 'explain', evidence: 'explain', plan: 'act' }

// Every older URL keeps working (README, demo scripts, judges' bookmarks).
const ToInvestigate = ({ tab }: { tab?: string }) => {
  const { teamId } = useParams()
  const loc = useLocation()
  const t = tab ?? new URLSearchParams(loc.search).get('tab') ?? ''
  const focus = TAB_TO_FOCUS[t]
  return <Navigate to={`/investigate/${teamId}${focus ? `?focus=${focus}&tab=${t || 'overview'}` : ''}`} replace />
}
const ToReview = () => { const { planId } = useParams(); return <Navigate to={planId ? `/review/${planId}` : '/review'} replace /> }

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Today />} />
            <Route path="investigate" element={<Teams />} />
            <Route path="investigate/:teamId" element={<Investigate />} />
            <Route path="plans" element={<Plans />} />
            <Route path="review" element={<Review />} />
            <Route path="review/:planId" element={<Review />} />
            <Route path="insights" element={<Insights />} />
            <Route path="ask" element={<Ask />} />
            <Route path="data" element={<DataSources />} />
            <Route path="value" element={<Value />} />
            <Route path="trust" element={<Trust />} />
            <Route path="study/sus" element={<Sus />} />
            {/* v0.7 routes */}
            <Route path="teams" element={<Navigate to="/investigate" replace />} />
            <Route path="teams/:teamId" element={<ToInvestigate />} />
            <Route path="impact" element={<Navigate to="/review" replace />} />
            <Route path="impact/:planId" element={<ToReview />} />
            {/* v0.6 routes */}
            <Route path="why/:teamId" element={<ToInvestigate tab="overview" />} />
            <Route path="plan/:teamId" element={<ToInvestigate tab="plan" />} />
            <Route path="proof/:planId" element={<ToReview />} />
            <Route path="hood" element={<Navigate to="/trust" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  )
}
