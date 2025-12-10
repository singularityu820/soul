import { useEffect, useMemo, useState } from "react";
import StarPortal from "./pages/StarPortal";
import StarPortalPlanB from "./pages/StarPortalPlanB";
import ChatApp from "./pages/ChatApp/ChatApp.jsx";
import ChatNew from "./pages/ChatNew/index.jsx";
import KawaiiChat from "./pages/KawaiiChat/KawaiiChat.jsx";
import UserCenter from "./pages/UserCenter";
import NotFound from "./pages/NotFound";
import LoginModal from "./pages/LoginModal";
import RouteSwitcher from "./components/RouteSwitcher.jsx";
import SettingsButton from "./components/SettingsButton.jsx";

const normalizeHash = () => {
  const raw = window.location.hash || "#/";
  // 去掉结尾斜杠（保留根路径）
  if (raw.length > 2 && raw.endsWith("/")) return raw.slice(0, -1);
  return raw;
};

// 在模块加载时就定义 window.navigate，确保在任何地方调用时都可用
if (typeof window !== 'undefined' && !window.navigate) {
  window.navigate = (path) => {
    if (!path || typeof path !== "string") return;
    if (!path.startsWith("#")) path = `#${path}`;
    window.location.hash = path;
  };
}

export default function App() {
  const ROUTES = useMemo(
    () => ({
      "#/": UserCenter,
      "#/login": LoginModal,
      // "#/portal": StarPortal,
      "#/portal-planb": StarPortalPlanB,
      "#/chatnew": ChatNew,
      "#/kawaiichat": KawaiiChat,
      "#/user": UserCenter,
    }),
    []
  );

  const [route, setRoute] = useState(normalizeHash());

  useEffect(() => {
    // 确保 window.navigate 已定义（如果之前没有定义，这里会重新定义）
    if (!window.navigate) {
      window.navigate = (path) => {
        if (!path || typeof path !== "string") return;
        if (!path.startsWith("#")) path = `#${path}`;
        window.location.hash = path;
      };
    }
    
    const handleHashChange = () => setRoute(normalizeHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const Component = ROUTES[route] || NotFound;
  return (
    <>
      <Component />
        {/*<RouteSwitcher routes={ROUTES} current={route} onNavigate={(p) => window.navigate(p)} />*/}
        {route !== "#/user" && <SettingsButton />}
    </>
  );
}