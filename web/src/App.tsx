import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'
import Shell from './components/Shell'
import { StoreProvider } from './lib/store'
import Today from './pages/Today'
// Today loads with the app; every other screen is fetched when first opened (smaller first load).
const Teams = lazy(() => import('./pages/Teams'))
const TeamDetail = lazy(() => import('./pages/TeamDetail'))
const Plans = lazy(() => import('./pages/Plans'))
const Impact = lazy(() => import('./pages/Impact'))
const Insights = lazy(() => import('./pages/Insights'))
const Ask = lazy(() => import('./pages/Ask'))
const DataSources = lazy(() => import('./pages/DataSources'))
const Value = lazy(() => import('./pages/Value'))
const Trust = lazy(() => import('./pages/Trust'))
const Sus = lazy(() => import('./pages/Sus'))

// v0.6 URLs from the README and earlier demos keep working.
const ToTeam = ({ tab }: { tab?: string }) => { const { teamId } = useParams(); return <Navigate to={`/teams/${teamId}${tab ? `?tab=${tab}` : ''}`} replace /> }
const ToImpact = () => { const { planId } = useParams(); return <Navigate to={`/impact/${planId}`} replace /> }

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Today />} />
            <Route path="teams" element={<Teams />} />
            <Route path="teams/:teamId" element={<TeamDetail />} />
            <Route path="plans" element={<Plans />} />
            <Route path="impact" element={<Impact />} />
            <Route path="impact/:planId" element={<Impact />} />
            <Route path="insights" element={<Insights />} />
            <Route path="ask" element={<Ask />} />
            <Route path="data" element={<DataSources />} />
            <Route path="value" element={<Value />} />
            <Route path="trust" element={<Trust />} />
            <Route path="study/sus" element={<Sus />} />
            <Route path="why/:teamId" element={<ToTeam />} />
            <Route path="plan/:teamId" element={<ToTeam tab="plan" />} />
            <Route path="proof/:planId" element={<ToImpact />} />
            <Route path="hood" element={<Navigate to="/trust" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  )
}
