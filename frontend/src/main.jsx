import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initQaLogger, hookStore } from "./utils/qaLogger";
import { useSightingsStore } from "./stores/sightingsStore";

initQaLogger();
hookStore(useSightingsStore);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
