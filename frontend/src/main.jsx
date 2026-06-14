import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { initAdminToken } from "./api.js";
import "./styles.css";

initAdminToken(); // capture ?admin=... before first render

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
