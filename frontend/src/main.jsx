import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App";
import SessionPrep from "./pages/SessionPrep";
import LiveInterview from "./pages/LiveInterview";
import PostInterview from "./pages/PostInterview";
import Settings from "./pages/Settings";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/prep/:sessionId" element={<SessionPrep />} />
        <Route path="/live/:sessionId" element={<LiveInterview />} />
        <Route path="/review/:sessionId" element={<PostInterview />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
