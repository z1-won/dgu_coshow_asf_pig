import React from "react";
import ReactDOM from "react-dom/client";
import "pretendard/dist/web/variable/pretendardvariable.css";
import "./styles.css";
import App from "./App.jsx";
import { DashboardDataProvider } from "./DashboardDataContext.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <DashboardDataProvider>
      <App />
    </DashboardDataProvider>
  </React.StrictMode>
);
