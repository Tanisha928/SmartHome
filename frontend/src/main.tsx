import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/index.css";

const renderApp = () => ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
if (import.meta.env.VITE_DEMO_MODE === "true") void import("./demo/browser").then(({ worker }) => worker.start({ onUnhandledRequest: "bypass" })).then(renderApp); else renderApp();
