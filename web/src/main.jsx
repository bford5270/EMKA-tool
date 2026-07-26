import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

// State lives in memory only — no localStorage, no sessionStorage, no
// cookies. Nothing sensitive persists in the browser.
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
