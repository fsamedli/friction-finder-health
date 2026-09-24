import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Shell from './components/Shell'
import { StoreProvider } from './lib/store'
import Board from './pages/Board'
import Why from './pages/Why'
import PlanPage from './pages/Plan'
import Proof from './pages/Proof'
import Value from './pages/Value'
import Hood from './pages/Hood'
import Ask from './pages/Ask'

export default function App() {
  return (
    <StoreProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Board />} />
            <Route path="why/:teamId" element={<Why />} />
            <Route path="plan/:teamId" element={<PlanPage />} />
            <Route path="proof/:planId" element={<Proof />} />
            <Route path="value" element={<Value />} />
            <Route path="hood" element={<Hood />} />
            <Route path="ask" element={<Ask />} />
            <Route path="*" element={<Board />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StoreProvider>
  )
}
