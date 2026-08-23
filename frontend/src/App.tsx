import React from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { useStore } from "./store";

// Pages
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import PracticePage from "./pages/PracticePage";
import SessionPage from "./pages/SessionPage";
import FeedbackPage from "./pages/FeedbackPage";
import SettingsPage from "./pages/SettingsPage";
import BillingPage from "./pages/BillingPage";
import OverlayPage from "./pages/OverlayPage";

// Layout
import AppLayout from "./components/layout/AppLayout";
import WindowTitleBar from "./components/layout/WindowTitleBar";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useStore((s) => s.isAuthenticated());
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function AppContent() {
  // The overlay is its own frameless, always-on-top window with no
  // decorations by design — every other route runs in the frameless main
  // window (Windows only) and needs the custom title bar to be usable at all.
  const { pathname } = useLocation();
  const isOverlay = pathname === "/overlay";

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {!isOverlay && <WindowTitleBar />}
      <div className="flex-1 min-h-0">
        <Routes>
          {/* Public routes */}
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Electron overlay — separate window */}
          <Route path="/overlay" element={<OverlayPage />} />

          {/* Protected app routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"        element={<DashboardPage />} />
            <Route path="practice"         element={<PracticePage />} />
            <Route path="session/:id"      element={<SessionPage />} />
            <Route path="feedback/:id"     element={<FeedbackPage />} />
            <Route path="settings"         element={<SettingsPage />} />
            <Route path="billing"          element={<BillingPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#1E1E2E",
            color: "#E8E8F0",
            border: "1px solid #2D2D3D",
          },
        }}
      />
      <AppContent />
    </BrowserRouter>
  );
}
