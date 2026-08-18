import React, { StrictMode, useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
// Self-hosted, so the surface keeps its typeface on a store network that cannot
// reach a CDN. Variable, so the type ramp has real Medium and SemiBold steps.
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { FluentProvider } from "@fluentui/react-components";
import { storeLightTheme, storeDarkTheme } from './theme/storeTheme';
import {
  beginRuntimeBootstrap,
  runtimeBootstrapLoaded,
  setEnvData,
  setApiUrl,
  config as defaultConfig,
  toBoolean,
  getUserInfo,
  setUserInfoGlobal,
} from './api/config';
import { apiService } from './api';
import { Provider as ReduxProvider } from 'react-redux';
import { store } from './store/store';
import { hydrateCurrentUser } from './store/slices/appSlice';
const root = ReactDOM.createRoot(document.getElementById("root") as HTMLElement);

const AppWrapper = () => {
  // State to store the current theme
  const [isDarkMode, setIsDarkMode] = useState(
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
  useEffect(() => {
    const initConfig = async () => {
      window.appConfig = defaultConfig;
      setEnvData(defaultConfig);
      setApiUrl(defaultConfig.API_URL);

      // The user record shares no dependency with runtime configuration.
      const userInfo = getUserInfo();

      try {
        const response = await fetch('/config');
        let config = defaultConfig;
        if (response.ok) {
          config = await response.json();
          config.ENABLE_AUTH = toBoolean(config.ENABLE_AUTH);
        }

          window.appConfig = config;
          setEnvData(config);
          setApiUrl(config.API_URL);
      } catch (error) {
          console.info("frontend config did not load from python", error);
      } finally {
          const resolvedUserInfo = await userInfo;
          window.userInfo = resolvedUserInfo;
          setUserInfoGlobal(resolvedUserInfo);
          store.dispatch(hydrateCurrentUser(resolvedUserInfo));
          runtimeBootstrapLoaded();
          void apiService.sendUserBrowserLanguage().catch((error) => {
            console.info("browser language did not reach the backend", error);
          });
      }
    };
    
    initConfig(); // Call the async function inside useEffect
  }, []);
  // Effect to listen for changes in the user's preferred color scheme
  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const handleThemeChange = (event: MediaQueryListEvent) => {
      setIsDarkMode(event.matches);
      document.body.classList.toggle("dark-mode", event.matches);
    };

    // Apply dark-mode class initially
    document.body.classList.toggle("dark-mode", isDarkMode);

    mediaQuery.addEventListener("change", handleThemeChange);
    return () => mediaQuery.removeEventListener("change", handleThemeChange);
  }, []);
  return (
    <StrictMode>
      <ReduxProvider store={store}>
        <FluentProvider
          theme={isDarkMode ? storeDarkTheme : storeLightTheme}
          // `dvh`, not `vh`: on iOS Safari `100vh` is the viewport *without* the
          // browser chrome, so the shell was a toolbar taller than the screen
          // and jumped as that chrome collapsed. This is a shared phone in a
          // store before it is anything else.
          style={{ height: "100dvh" }}
        >
          <App />
        </FluentProvider>
      </ReduxProvider>
    </StrictMode>
  );
};
beginRuntimeBootstrap();
root.render(<AppWrapper />);
reportWebVitals();
