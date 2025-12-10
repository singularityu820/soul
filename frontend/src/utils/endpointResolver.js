const DEV_SERVER_PORTS = new Set(["5173", "4173", "4174", "3000", "3001", "8080", "9000"]);
const FALLBACK_HTTP_BASE = "https://xbxm.cloud:443";

const WINDOW_CONFIG_SOURCES = [
  (w) => w.__SOUL_CONFIG__,
  (w) => w.__SOUL_APP_CONFIG__,
  (w) => w.__SOUL_ENDPOINTS__,
  (w) => w.__SOUL_API__,
  (w) => w.__SOUL_ENV__,
];

const stripTrailingSlash = (url) => url.replace(/\/+$/, "");

const getEnvValue = (key) => {
  if (typeof import.meta !== "undefined" && import.meta.env && key in import.meta.env) {
    const value = import.meta.env[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
};

const readWindowValue = (keys) => {
  if (typeof window === "undefined") {
    return undefined;
  }

  for (const key of keys) {
    if (window[key]) {
      return window[key];
    }
  }

  for (const getter of WINDOW_CONFIG_SOURCES) {
    const cfg = getter(window);
    if (!cfg) continue;
    for (const key of keys) {
      if (cfg[key]) {
        return cfg[key];
      }
    }
  }

  return undefined;
};

const toAbsoluteUrl = (raw, base) => {
  if (!raw) return null;
  const value = raw.trim();
  if (!value) return null;

  try {
    if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("ws://") || value.startsWith("wss://")) {
      return new URL(value);
    }

    if (value.startsWith("//")) {
      const protocol = base?.startsWith("https:") ? "https:" : "http:";
      return new URL(`${protocol}${value}`);
    }

    const resolvedBase = base ?? FALLBACK_HTTP_BASE;
    return new URL(value, resolvedBase);
  } catch (error) {
    console.error("[endpointResolver] Failed to parse URL", value, error);
    return null;
  }
};

const normalizeWsFromUrl = (urlObj) => {
  if (!urlObj) return null;
  if (urlObj.protocol === "ws:" || urlObj.protocol === "wss:") {
    return urlObj.toString();
  }
  const protocol = urlObj.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${urlObj.host}${urlObj.pathname}${urlObj.search || ""}`;
};

export const resolveApiBaseUrl = () => {
  const envBase = getEnvValue("VITE_API_BASE_URL");
  if (envBase) {
    return stripTrailingSlash(envBase);
  }

  const windowBase = readWindowValue(["apiBaseUrl", "apiBase", "apiUrl", "api_origin", "apiEndpoint"]);
  if (windowBase) {
    return stripTrailingSlash(windowBase);
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location;
    if (port && DEV_SERVER_PORTS.has(port)) {
      return `${protocol}//${hostname}:8000`;
    }
    const portSegment = port ? `:${port}` : "";
    return `${protocol}//${hostname}${portSegment}`;
  }

  return FALLBACK_HTTP_BASE;
};

export const resolveWebSocketUrl = (path, options = {}) => {
  const trimmedPath = path.startsWith("/") ? path : `/${path}`;
  const envOverride =
    options.override ??
    (options.envVar ? getEnvValue(options.envVar) : undefined);
  const windowOverride = readWindowValue(options.windowKeys ?? []);
  const origin = typeof window !== "undefined" ? window.location.origin : FALLBACK_HTTP_BASE;
  const override = envOverride ?? windowOverride;

  if (override) {
    const normalized = normalizeWsFromUrl(toAbsoluteUrl(override, origin));
    if (normalized) {
      return normalized;
    }
  }
  const httpBase = options.httpBase ?? resolveApiBaseUrl();
  const derived = normalizeWsFromUrl(toAbsoluteUrl(trimmedPath, httpBase));
  if (derived) {
    return derived;
  }

  const fallback = normalizeWsFromUrl(toAbsoluteUrl(trimmedPath, FALLBACK_HTTP_BASE));
  return fallback ?? `${FALLBACK_HTTP_BASE.replace("http", "ws")}${trimmedPath}`;
};

export { DEV_SERVER_PORTS };
