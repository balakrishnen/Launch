import { BrowserRouter, HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProjectProvider } from './state'
import { Shell } from './components/Shell'
import { Overview } from './pages/Overview'
import { Element } from './pages/Element'
import { Tables, TablePage, Notes, NotePage, ImportSheet } from './pages/Office'
import { Runs, RunPage } from './pages/Testing'
import { ChatPage } from './pages/Chat'
import { TeamPage } from './pages/Team'
import { Board, Timeline, Trend, Harness } from './pages/Execution'
import { Collection } from './pages/Collection'
import { Artifacts, FormPage, MatrixPage, Views, Docs, Sysml } from './pages/Artifacts'
import { Graph, Gaps, Scorecard, Inbox, Integrations, Documents, History, Budgets, SearchPage, Landing } from './pages/More'
import { Teams, Notifications } from './pages/Lifecycle'

const REVIEW = import.meta.env.VITE_REVIEW === '1'
export default function App() {
  const Router: any = REVIEW ? HashRouter : BrowserRouter
  return <Router {...(REVIEW ? {} : { basename: '/app' })}>
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/p/:pid" element={<ProjectProvider><Shell /></ProjectProvider>}>
        <Route index element={<Overview />} />
        <Route path="artifacts" element={<Artifacts />} />
        <Route path="collection/:kind" element={<Collection />} />
        <Route path="element/:kind/:id" element={<Element />} />
        <Route path="form/:name" element={<FormPage />} />
        <Route path="matrix/:a/:b" element={<MatrixPage />} />
        <Route path="graph" element={<Graph />} /><Route path="graph/:focus" element={<Graph />} />
        <Route path="gaps" element={<Gaps />} /><Route path="scorecard" element={<Scorecard />} /><Route path="inbox" element={<Inbox />} />
        <Route path="integrations" element={<Integrations />} /><Route path="documents" element={<Documents />} /><Route path="history" element={<History />} /><Route path="budgets" element={<Budgets />} />
        <Route path="teams" element={<Teams />} /><Route path="notifications" element={<Notifications />} /><Route path="views" element={<Views />} /><Route path="docs" element={<Docs />} /><Route path="sysml" element={<Sysml />} /><Route path="search/:q" element={<SearchPage />} />
        <Route path="tables" element={<Tables />} /><Route path="table/:tid" element={<TablePage />} /><Route path="notes" element={<Notes />} /><Route path="note/:nid" element={<NotePage />} /><Route path="import" element={<ImportSheet />} /><Route path="team/:tid" element={<TeamPage />} /><Route path="board" element={<Board />} /><Route path="timeline" element={<Timeline />} /><Route path="trend" element={<Trend />} /><Route path="harness" element={<Harness />} /><Route path="chat" element={<ChatPage />} /><Route path="chat/:tid" element={<ChatPage />} /><Route path="runs" element={<Runs />} /><Route path="run/:rid" element={<RunPage />} />
        <Route path="*" element={<Navigate to="." />} />
      </Route>
    </Routes>
  </Router>
}
