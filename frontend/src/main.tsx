import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AppProvider } from "./context/AppContext";
import { ConfirmDialogProvider } from "./components/ConfirmDialogProvider";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider>
      <ConfirmDialogProvider>
        <App />
      </ConfirmDialogProvider>
    </AppProvider>
  </StrictMode>,
);
