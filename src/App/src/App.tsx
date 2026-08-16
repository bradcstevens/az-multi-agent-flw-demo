import React, { useEffect } from 'react';
import './App.css';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { HomePage, ChatPage } from './pages';
import PlanApprovalPrototype from './pages/prototype/PlanApprovalPrototype';
import { useWebSocket } from './hooks/useWebSocket';
import { useAppDispatch } from './store/hooks';
import { hydrateCurrentUser } from './store/slices/appSlice';
import { getUserInfoGlobal } from './api/config';

/**
 * The conversation route the surface used to have.
 *
 * A Chat is the unit of the surface (ADR-025), so the route is `/chat/:id`.
 * The old path is kept as a redirect rather than deleted: a presenter mid-demo
 * has `/plan/<id>` in a tab, in history and in whatever they pasted into chat,
 * and the catch-all below would send them to the home screen with the
 * conversation they were showing gone.
 */
function LegacyPlanRoute() {
  const { planId } = useParams<{ planId: string }>();
  return <Navigate to={`/chat/${planId}`} replace />;
}

function App() {
    useWebSocket();
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(hydrateCurrentUser(getUserInfoGlobal()));
    }, [dispatch]);
    
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat/:id" element={<ChatPage />} />
        <Route path="/plan/:planId" element={<LegacyPlanRoute />} />
        {/* PROTOTYPE — throwaway, issue #85. Never reaches main. */}
        <Route path="/prototype/plan-approval" element={<PlanApprovalPrototype />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;