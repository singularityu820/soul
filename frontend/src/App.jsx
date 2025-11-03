import { useEffect, useMemo, useState } from "react";
import StarPortal from "./pages/StarPortal";
import ChatApp from "./pages/ChatApp/ChatApp.jsx";
import NotFound from "./pages/NotFound";
import RouteSwitcher from "./components/RouteSwitcher.jsx";

const normalizeHash = () => {
  const raw = window.location.hash || "#/";
  // 去掉结尾斜杠（保留根路径）
  if (raw.length > 2 && raw.endsWith("/")) return raw.slice(0, -1);
  return raw;
};

export default function App() {
  const ROUTES = useMemo(
    () => ({
      "#/": ChatApp,
      "#/portal": StarPortal,
    }),
    []
  );

  const [route, setRoute] = useState(normalizeHash());

  useEffect(() => {
    // 统一导航助手
    window.navigate = (path) => {
      if (!path || typeof path !== "string") return;
      if (!path.startsWith("#")) path = `#${path}`;
      window.location.hash = path;
    };
    const handleHashChange = () => setRoute(normalizeHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const Component = ROUTES[route] || NotFound;
  return (
    <>
      <Component />
      <RouteSwitcher routes={ROUTES} current={route} onNavigate={(p) => window.navigate(p)} />
    </>
  );
}
