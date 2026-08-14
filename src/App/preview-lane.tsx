import React from "react";
import { createRoot } from "react-dom/client";
import {
  Body1Strong,
  FluentProvider,
  teamsDarkTheme,
  teamsLightTheme,
} from "@fluentui/react-components";
import {
  BookOpen20Regular,
  Search20Regular,
  Wrench20Regular,
  Document20Regular,
  Shield20Regular,
  Clipboard20Regular,
} from "@fluentui/react-icons";

import PromptCard from "./src/commonComponents/components/PromptCard";
import LaneBadge from "./src/components/lane/LaneBadge";
import "./src/styles/HomeInput.css";

const TASKS = [
  { t: "Close the store", d: "How do I close the store?", l: "fast", i: <BookOpen20Regular /> },
  { t: "Restart the car wash", d: "How do I restart the car wash after a vehicle stalls in the bay?", l: "fast", i: <Search20Regular /> },
  { t: "The coffee brewer is down", d: "The coffee brewer is down. It is not brewing on the left head.", l: "fast", i: <Wrench20Regular /> },
  { t: "I can't fix it", d: "I have tried everything and I can't fix it. I need someone to come out.", l: "deliberate", i: <Document20Regular /> },
  { t: "How much PTO do I have?", d: "My name is Tanya, how much PTO do I have?", l: "fast", i: <Shield20Regular /> },
  { t: "What is due this shift?", d: "What tasks are due on this shift?", l: "fast", i: <Clipboard20Regular /> },
] as const;

const Grid = () => (
  <div className="home-input-center-content" style={{ margin: "0 auto", padding: 24 }}>
    <div className="home-input-quick-tasks-section">
      <div className="home-input-quick-tasks-header">
        <Body1Strong>Quick tasks</Body1Strong>
      </div>
      <div className="home-input-quick-tasks">
        {TASKS.map((task) => (
          <PromptCard
            key={task.t}
            title={task.t}
            icon={task.i}
            description={task.d}
            badge={<LaneBadge lane={task.l as any} variant="declared" />}
          />
        ))}
      </div>
    </div>
  </div>
);

createRoot(document.getElementById("root")!).render(
  <>
    <FluentProvider theme={teamsDarkTheme} style={{ padding: 16 }}>
      <Grid />
    </FluentProvider>
    <FluentProvider theme={teamsLightTheme} style={{ padding: 16 }}>
      <Grid />
    </FluentProvider>
  </>,
);
