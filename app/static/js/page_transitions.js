function isModifiedClick(event) {
  return Boolean(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey);
}

function isSameOrigin(url) {
  try {
    return new URL(url, window.location.href).origin === window.location.origin;
  } catch {
    return false;
  }
}

function isSafeGetAnchor(anchor) {
  if (!anchor) return false;
  const rel = (anchor.getAttribute("rel") || "").toLowerCase();
  if (rel.includes("external")) return false;
  const href = anchor.getAttribute("href") || "";
  if (!href) return false;
  const url = new URL(href, window.location.href);
  return url.protocol === "http:" || url.protocol === "https:";
}

function shouldIntercept(anchor) {
  if (!anchor) return false;
  const href = anchor.getAttribute("href") || "";
  if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return false;
  if (anchor.target && anchor.target !== "_self") return false;
  if (anchor.hasAttribute("download")) return false;
  if (!isSafeGetAnchor(anchor)) return false;
  if (anchor.dataset?.sbTransition === "off") return false;
  if (!isSameOrigin(href)) return false;
  return true;
}

function transitionMode(fromRoute, toRoute) {
  const from = String(fromRoute || "").trim();
  const to = String(toRoute || "").trim();
  if (from === "main.home" && to === "main.discover") {
    return "home-discover";
  }
  return "default";
}

function setMainEnterState(main, mode) {
  main.classList.add("sb-main-enter");
  if (mode === "home-discover") {
    main.classList.add("sb-tx-home-discover");
  }
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      main.classList.add("sb-main-enter-active");
    });
  });
}

function clearMainEnterState(main) {
  main.classList.remove("sb-main-enter", "sb-main-enter-active", "sb-tx-home-discover");
}

function parseHtml(htmlText) {
  const parser = new DOMParser();
  return parser.parseFromString(htmlText, "text/html");
}

function extractPayload(doc, mainId) {
  const nextMain = doc.getElementById(mainId);
  if (!nextMain) {
    return null;
  }
  const nextTitle = doc.title || "";
  const nextRoute = doc.body?.dataset?.sbRoute || "";
  const nextCartAvatar = doc.body?.dataset?.sbCartAvatar || "{}";
  const nextWorld = doc.body?.dataset?.sbWorld || "";
  return {
    title: nextTitle,
    route: nextRoute,
    cartAvatar: nextCartAvatar,
    world: nextWorld,
    mainInnerHtml: nextMain.innerHTML,
  };
}

async function fetchDocument(url) {
  const response = await fetch(url, {
    method: "GET",
    credentials: "same-origin",
    headers: { "X-Requested-With": "sb-page-transition" },
  });
  if (!response.ok) {
    throw new Error(`Fetch failed: ${response.status}`);
  }
  const text = await response.text();
  return parseHtml(text);
}

function emit(name, detail) {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

function runInlineScripts(container) {
  const scripts = [...container.querySelectorAll("script")];
  scripts.forEach((oldScript) => {
    const parent = oldScript.parentNode;
    if (!parent) return;
    const newScript = document.createElement("script");
    [...oldScript.attributes].forEach((attribute) => {
      newScript.setAttribute(attribute.name, attribute.value);
    });
    if (oldScript.textContent) {
      newScript.textContent = oldScript.textContent;
    }
    parent.replaceChild(newScript, oldScript);
  });
}

export function bootPageTransitions({ mainId = "sb-main", shell = null } = {}) {
  const main = document.getElementById(mainId);
  if (!main) return null;
  const overlay = document.getElementById("sb-nav-overlay");

  let navigating = false;
  let currentUrl = window.location.href;
  const cache = new Map();
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const setRouteDataset = (route) => {
    if (!document.body) return;
    document.body.dataset.sbRoute = route || "";
  };

  const setCartAvatarDataset = (cartAvatar) => {
    if (!document.body) return;
    document.body.dataset.sbCartAvatar = cartAvatar || "{}";
  };

  const setWorldDataset = (world) => {
    if (!document.body) return;
    document.body.dataset.sbWorld = world || "";
  };

  const applyPayload = (payload) => {
    if (!payload) return;
    if (payload.title) {
      document.title = payload.title;
    }
    setRouteDataset(payload.route);
    setCartAvatarDataset(payload.cartAvatar);
    setWorldDataset(payload.world);
    if (typeof window.__sbApplyWorldTheme === "function") {
      window.__sbApplyWorldTheme(payload.world || "");
    }
    main.innerHTML = payload.mainInnerHtml;
    runInlineScripts(main);
    emit("sb:content-replaced", { route: payload.route });
  };

  const animateExit = (mode) => {
    if (prefersReducedMotion) return Promise.resolve();
    overlay?.classList.add("sb-nav-overlay-active");
    main.classList.add("sb-main-exit");
    if (mode === "home-discover") {
      main.classList.add("sb-tx-home-discover");
    }
    const ms = mode === "home-discover" ? 400 : 320;
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  };

  const animateEnter = (mode) => {
    if (prefersReducedMotion) return Promise.resolve();
    main.classList.remove("sb-main-exit", "sb-tx-home-discover");
    clearMainEnterState(main);
    setMainEnterState(main, mode);
    const ms = mode === "home-discover" ? 520 : 500;
    return new Promise((resolve) => {
      window.setTimeout(() => {
        overlay?.classList.remove("sb-nav-overlay-active");
        clearMainEnterState(main);
        resolve();
      }, ms);
    });
  };

  const setCache = (url, payload) => {
    if (!payload) return;
    if (cache.size > 12) {
      const oldestKey = cache.keys().next().value;
      cache.delete(oldestKey);
    }
    cache.set(url, payload);
  };

  const getPayload = async (nextUrl) => {
    const cached = cache.get(nextUrl);
    if (cached) return cached;
    const doc = await fetchDocument(nextUrl);
    const payload = extractPayload(doc, mainId);
    setCache(nextUrl, payload);
    return payload;
  };

  const prefetch = async (url) => {
    const nextUrl = new URL(url, window.location.href).toString();
    if (nextUrl === currentUrl) {
      navigating = false;
      return;
    }
    if (cache.has(nextUrl) || nextUrl === currentUrl) return;
    try {
      await getPayload(nextUrl);
    } catch {
      // Prefetch is best-effort only.
    }
  };

  const navigateTo = async (url, { push = true } = {}) => {
    if (navigating) return;
    navigating = true;

    const nextUrl = new URL(url, window.location.href).toString();
    const fromRoute = document.body?.dataset?.sbRoute || "";

    document.documentElement.classList.add("sb-nav-freeze");
    emit("sb:navigate-start", { from: currentUrl, to: nextUrl, fromRoute });

    try {
      const payload = await getPayload(nextUrl);
      if (!payload) {
        window.location.href = nextUrl;
        return;
      }

      const mode = transitionMode(fromRoute, payload.route);
      shell?.onNavigateStart?.(payload.route, { fromRoute });
      await animateExit(mode);

      if (push) {
        window.history.pushState({ sb: 1 }, "", nextUrl);
      }

      applyPayload(payload);
      shell?.onNavigateEnd?.(payload.route);
      emit("sb:navigate-end", { to: nextUrl, route: payload.route });

      await animateEnter(mode);
      currentUrl = nextUrl;
      window.scrollTo({ top: 0, behavior: "auto" });
      const activeAutoFocus = main.querySelector("[autofocus]");
      if (activeAutoFocus instanceof HTMLElement) {
        activeAutoFocus.focus({ preventScroll: true });
      }
    } catch (error) {
      console.warn("Transition navigation failed; falling back.", error);
      window.location.href = nextUrl;
    } finally {
      document.documentElement.classList.remove("sb-nav-freeze");
      navigating = false;
    }
  };

  document.addEventListener(
    "click",
    (event) => {
      if (event.defaultPrevented) return;
      if (event.button !== 0) return;
      if (isModifiedClick(event)) return;

      const anchor = event.target?.closest?.("a");
      if (!shouldIntercept(anchor)) return;

      const href = anchor.getAttribute("href");
      if (!href) return;

      event.preventDefault();
      navigateTo(href, { push: true });
    },
    true
  );

  document.addEventListener(
    "pointerenter",
    (event) => {
      const anchor = event.target?.closest?.("a");
      if (!shouldIntercept(anchor)) return;
      const href = anchor.getAttribute("href");
      if (!href) return;
      prefetch(href);
    },
    true
  );

  document.addEventListener(
    "touchstart",
    (event) => {
      const anchor = event.target?.closest?.("a");
      if (!shouldIntercept(anchor)) return;
      const href = anchor.getAttribute("href");
      if (!href) return;
      prefetch(href);
    },
    { capture: true, passive: true }
  );

  window.addEventListener("popstate", () => {
    navigateTo(window.location.href, { push: false });
  });

  return { navigateTo };
}
