import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Analytics } from "@vercel/analytics/react";
import { AuthProvider } from "./AuthContext.jsx";
import SearchPage from "./components/SearchPage.jsx";
import CommitteePage from "./components/CommitteePage.jsx";
import AuthPage from "./components/AuthPage.jsx";
import HistoryPage from "./components/HistoryPage.jsx";
import ReplayPage from "./components/ReplayPage.jsx";
import RequireAuth from "./components/RequireAuth.jsx";
import TopNav from "./components/TopNav.jsx";
import UpdatePrompt from "./components/UpdatePrompt.jsx";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <TopNav />
        <UpdatePrompt />
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/analysis/:ticker" element={<CommitteePage />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route
            path="/history"
            element={
              <RequireAuth>
                <HistoryPage />
              </RequireAuth>
            }
          />
          <Route
            path="/history/:id"
            element={
              <RequireAuth>
                <ReplayPage />
              </RequireAuth>
            }
          />
        </Routes>
        <Analytics />
      </BrowserRouter>
    </AuthProvider>
  );
}
