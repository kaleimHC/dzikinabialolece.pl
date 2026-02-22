/**
 * QA Logger — universal observability layer.
 *
 * Activation: localStorage.setItem('dziki-qa', '1') + reload
 * Deactivation: localStorage.removeItem('dziki-qa') + reload
 *
 * All output to console AND in-memory ring buffer (5000 entries).
 * Call window.__QA_DUMP() at any time to get full log as text + clipboard copy.
 */

const FLAG_KEY = "dziki-qa";
const RING_SIZE = 5000;

let _active = false;
let _ring = [];
let _lastUiQaId = null;

function isActive() {
  return _active;
}

function nanoid8() {
  return Math.random().toString(36).slice(2, 10).padStart(8, "0");
}

function iso() {
  return new Date().toISOString();
}

function emit(line) {
  console.log(line);
  _ring.push(line);
  if (_ring.length > RING_SIZE) _ring.shift();
}

function redact(str) {
  if (typeof str !== "string") return str;
  // Redact Bearer tokens, session cookies, CSRF tokens
  return str
    .replace(/Bearer\s+[A-Za-z0-9._-]{8,}/g, "Bearer [REDACTED]")
    .replace(/csrftoken=[^;\s&"]{4,}/gi, "csrftoken=[REDACTED]")
    .replace(/sessionid=[^;\s&"]{4,}/gi, "sessionid=[REDACTED]")
    .replace(/"token"\s*:\s*"[^"]{4,}"/gi, '"token":"[REDACTED]"')
    .replace(/"password"\s*:\s*"[^"]{4,}"/gi, '"password":"[REDACTED]"');
}

function truncate(str, max = 200) {
  if (typeof str !== "string") {
    try {
      str = JSON.stringify(str);
    } catch {
      str = String(str);
    }
  }
  return str.length > max ? str.slice(0, max) + "…" : str;
}

function labelFor(el) {
  if (!el) return "?";
  const qa = el.getAttribute("data-qa");
  if (qa) return qa;
  // Fallback for UNFLAGGED elements
  const tag = el.tagName?.toLowerCase() || "?";
  const id = el.id ? `#${el.id}` : "";
  const cls = el.className
    ? "." +
      String(el.className)
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .join(".")
    : "";
  const text = el.textContent
    ? el.textContent.trim().slice(0, 30).replace(/\s+/g, " ")
    : "";
  return `UNFLAGGED:${tag}${id}${cls}${text ? `[${text}]` : ""}`;
}

// ─── 1. UI event delegation ────────────────────────────────────────────────

function setupUiDelegation() {
  ["click", "change", "submit", "pointerdown"].forEach((evtName) => {
    document.addEventListener(
      evtName,
      (e) => {
        if (!isActive()) return;
        // For click/pointerdown, find nearest element with data-qa (or fallback)
        let el = e.target;
        // Walk up to find data-qa attribute (max 5 levels)
        let qaEl = null;
        let cur = el;
        for (let i = 0; i < 5 && cur && cur !== document; i++) {
          if (cur.getAttribute && cur.getAttribute("data-qa")) {
            qaEl = cur;
            break;
          }
          cur = cur.parentElement;
        }
        const label = labelFor(qaEl || el);
        const qaId = nanoid8();
        _lastUiQaId = qaId;

        let extra = "";
        if (evtName === "change" && el.type === "range") {
          extra = ` value=${el.value}`;
        } else if (evtName === "change" && (el.type === "select-one" || el.tagName === "SELECT")) {
          extra = ` value=${el.value}`;
        } else if (evtName === "change" && el.type === "checkbox") {
          extra = ` checked=${el.checked}`;
        }

        emit(
          `[QA] ${iso()} | UI | ${evtName} | ${label}${extra} | qa_id=${qaId}`,
        );
      },
      true, // capture phase — catches everything before React handlers
    );
  });
}

// ─── 2. fetch monkey-patch ─────────────────────────────────────────────────

function setupFetchPatch() {
  const _origFetch = window.fetch;
  window.fetch = async function patchedFetch(input, init = {}) {
    if (!isActive()) return _origFetch(input, init);

    const method = (init.method || "GET").toUpperCase();
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input?.url || String(input);

    // Attach correlation header
    const qaId = _lastUiQaId || "auto";
    const headers = new Headers(init.headers || {});
    headers.set("X-QA-Id", qaId);

    const t0 = performance.now();
    emit(
      `[QA] ${iso()} | API → | ${method} ${url} | qa_id=${qaId}`,
    );

    try {
      const res = await _origFetch(input, { ...init, headers });
      const ms = Math.round(performance.now() - t0);
      const len = res.headers.get("content-length") || "?";
      emit(
        `[QA] ${iso()} | API ← | ${res.status} ${method} ${url} | ${ms}ms bytes=${len} | qa_id=${qaId}`,
      );
      return res;
    } catch (err) {
      const ms = Math.round(performance.now() - t0);
      emit(
        `[QA] ${iso()} | API !!! | NETWORK_ERROR ${method} ${url} | ${ms}ms | ${err.message} | qa_id=${qaId}`,
      );
      throw err;
    }
  };
}

// ─── 3. WebSocket patch ────────────────────────────────────────────────────

function setupWsPatch() {
  const _OrigWS = window.WebSocket;
  window.WebSocket = function PatchedWS(url, protocols) {
    const ws = protocols ? new _OrigWS(url, protocols) : new _OrigWS(url);
    if (!isActive()) return ws;

    const wsLabel = String(url).replace(/^wss?:\/\/[^/]+/, "");
    emit(`[QA] ${iso()} | WS OPEN | ${wsLabel}`);

    ws.addEventListener("message", (e) => {
      if (!isActive()) return;
      emit(
        `[QA] ${iso()} | WS MSG | ${wsLabel} | ${truncate(redact(e.data))}`,
      );
    });
    ws.addEventListener("close", (e) => {
      if (!isActive()) return;
      emit(`[QA] ${iso()} | WS CLOSE | ${wsLabel} | code=${e.code}`);
    });
    ws.addEventListener("error", () => {
      if (!isActive()) return;
      emit(`[QA] ${iso()} | WS !!! ERROR | ${wsLabel}`);
    });
    return ws;
  };
  // Preserve static properties (e.g. CONNECTING, OPEN, CLOSED)
  Object.assign(window.WebSocket, _OrigWS);
  window.WebSocket.prototype = _OrigWS.prototype;
}

// ─── 4. MapLibre events ───────────────────────────────────────────────────

export function hookMapLibre(map) {
  if (!isActive() || !map) return;
  ["sourcedata", "styledata", "error"].forEach((evt) => {
    map.on(evt, (e) => {
      if (!isActive()) return;
      const detail =
        evt === "sourcedata"
          ? `src=${e.sourceId || "?"} isLoaded=${e.isSourceLoaded}`
          : evt === "error"
            ? `err=${e.error?.message || "?"}`
            : "ok";
      emit(`[QA] ${iso()} | MAP | ${evt} | ${detail}`);
    });
  });
}

// ─── 5. Zustand store subscription ────────────────────────────────────────

export function hookStore(storeApi) {
  if (!isActive() || !storeApi) return;
  let prevState = storeApi.getState();
  storeApi.subscribe((nextState) => {
    if (!isActive()) return;
    const changed = Object.keys(nextState).filter(
      (k) => nextState[k] !== prevState[k],
    );
    if (changed.length) {
      emit(`[QA] ${iso()} | STORE | changed=[${changed.join(",")}]`);
    }
    prevState = nextState;
  });
}

// ─── 6. Global error handlers ─────────────────────────────────────────────

function setupErrorHandlers() {
  window.addEventListener("error", (e) => {
    if (!isActive()) return;
    emit(
      `[QA] ${iso()} | !!! ERROR | ${e.message} | ${e.filename}:${e.lineno}`,
    );
  });
  window.addEventListener("unhandledrejection", (e) => {
    if (!isActive()) return;
    const msg =
      e.reason?.message || e.reason?.toString?.() || String(e.reason);
    emit(`[QA] ${iso()} | !!! UNHANDLED_REJECTION | ${truncate(msg)}`);
  });
}

// ─── 7. Ring buffer dump ──────────────────────────────────────────────────

function setupDump() {
  window.__QA_DUMP = () => {
    const text = _ring.join("\n");
    // Try clipboard
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => console.log("[QA] Copied to clipboard"))
        .catch(() => {});
    } else {
      // Fallback: console copy() available in Chrome DevTools
      try {
        // eslint-disable-next-line no-undef
        copy(text);
        console.log("[QA] Copied via copy()");
      } catch {
        console.log("[QA] Use console: copy(window.__QA_DUMP())");
      }
    }
    console.log(
      `[QA] === DUMP START (${_ring.length} entries) ===\n${text}\n[QA] === DUMP END ===`,
    );
    return text;
  };
}

// ─── Init ─────────────────────────────────────────────────────────────────

export function initQaLogger() {
  try {
    _active = localStorage.getItem(FLAG_KEY) === "1";
  } catch {
    _active = false;
  }

  if (!_active) return;

  setupUiDelegation();
  setupFetchPatch();
  setupWsPatch();
  setupErrorHandlers();
  setupDump();

  emit(
    `[QA] ${iso()} | INIT | dziki-qa logger active | ring_size=${RING_SIZE} | use window.__QA_DUMP() to export`,
  );
}
