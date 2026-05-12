import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js";

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function smoothstep(edge0, edge1, x) {
  const t = clamp01((x - edge0) / Math.max(edge1 - edge0, 1e-6));
  return t * t * (3 - 2 * t);
}

function createSeededRandom(seed = 1337) {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

function supportsWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext("webgl2") ||
          canvas.getContext("webgl") ||
          canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}

function isLowMemoryDevice() {
  try {
    return Boolean(navigator.deviceMemory && navigator.deviceMemory <= 2);
  } catch {
    return false;
  }
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function normalizeRoute(rawRoute) {
  const route = String(rawRoute || "").trim();
  if (!route) return "unknown";
  if (route.startsWith("seller.")) return "seller";
  if (route.startsWith("admin.")) return "admin";
  if (route.startsWith("auth.")) return "auth";
  if (route.startsWith("main.")) return route.slice("main.".length);
  return route;
}

function normalizeWorld(rawWorld) {
  return String(rawWorld || "").trim().toLowerCase();
}

function worldAtmosphere(worldKey) {
  const key = normalizeWorld(worldKey);
  const worlds = {
    "neo-minimal": {
      accent: 0x8ec5ff,
      secondary: 0xbfd2e6,
      motionScale: 0.78,
      ambientScale: 1.06,
      keyScale: 1.02,
      driftScale: 0.68,
      ringScale: 0.84,
      particleScale: 0.74,
    },
    "dark-academia": {
      accent: 0xd2b48c,
      secondary: 0x6f5943,
      motionScale: 0.66,
      ambientScale: 0.86,
      keyScale: 0.84,
      driftScale: 0.58,
      ringScale: 0.72,
      particleScale: 0.66,
    },
    "monochrome-utility": {
      accent: 0xb6c2cf,
      secondary: 0x6b7480,
      motionScale: 1.08,
      ambientScale: 0.94,
      keyScale: 1.02,
      driftScale: 0.82,
      ringScale: 1.06,
      particleScale: 0.9,
    },
    "tokyo-street": {
      accent: 0x6eb8ff,
      secondary: 0x8b5cf6,
      motionScale: 1.28,
      ambientScale: 0.96,
      keyScale: 1.14,
      driftScale: 1.04,
      ringScale: 1.2,
      particleScale: 1.12,
    },
    "quiet-luxury": {
      accent: 0xe2c7a7,
      secondary: 0x8d765f,
      motionScale: 0.62,
      ambientScale: 1.04,
      keyScale: 0.92,
      driftScale: 0.52,
      ringScale: 0.68,
      particleScale: 0.58,
    },
    "futuristic-editorial": {
      accent: 0x7fd7ff,
      secondary: 0x6b73ff,
      motionScale: 1.34,
      ambientScale: 0.98,
      keyScale: 1.18,
      driftScale: 1.08,
      ringScale: 1.26,
      particleScale: 1.18,
    },
    "vintage-athletic": {
      accent: 0xe6a86f,
      secondary: 0x5f4a3b,
      motionScale: 1.12,
      ambientScale: 0.93,
      keyScale: 1.06,
      driftScale: 0.92,
      ringScale: 1.04,
      particleScale: 0.94,
    },
    "nordic-clean": {
      accent: 0x9fc8be,
      secondary: 0x6d817a,
      motionScale: 0.72,
      ambientScale: 1.05,
      keyScale: 0.92,
      driftScale: 0.58,
      ringScale: 0.74,
      particleScale: 0.66,
    },
    "avant-garde-structure": {
      accent: 0xd0d0df,
      secondary: 0x5f6072,
      motionScale: 1.24,
      ambientScale: 0.9,
      keyScale: 1.12,
      driftScale: 0.9,
      ringScale: 1.22,
      particleScale: 1.04,
    },
  };
  return (
    worlds[key] || {
      accent: 0x6eb8e0,
      secondary: 0xc9b8a8,
      motionScale: 1,
      ambientScale: 1,
      keyScale: 1,
      driftScale: 1,
      ringScale: 1,
      particleScale: 1,
    }
  );
}

function pickQuality() {
  if (prefersReducedMotion()) {
    return { maxDpr: 1, particleCount: 220, antialias: false };
  }
  if (isLowMemoryDevice() || window.innerWidth < 900) {
    return { maxDpr: 1.25, particleCount: 520, antialias: false };
  }
  return { maxDpr: 1.55, particleCount: 880, antialias: true };
}

function routeChapter(routeKey) {
  const key = normalizeRoute(routeKey);
  const common = {
    ambient: 0.82,
    key: 1.12,
    rim: 0.42,
    accent: 0.38,
  };

  const chapters = {
    home: {
      pos: [0.12, 0.18, 7.9],
      look: [0, 0.04, 0],
      bg: 0x05070c,
      ...common,
    },
    demo: {
      pos: [-0.2, 0.48, 6.85],
      look: [0, 0.12, -0.85],
      bg: 0x060a10,
      ambient: 0.88,
      key: 1.22,
      rim: 0.48,
      accent: 0.44,
    },
    feed: {
      pos: [0.18, 0.24, 6.35],
      look: [0, 0.0, -1.45],
      bg: 0x05080e,
      ambient: 0.84,
      key: 1.08,
      rim: 0.4,
      accent: 0.36,
    },
    discover: {
      pos: [-0.22, 0.32, 6.2],
      look: [0, 0.05, -1.42],
      bg: 0x060910,
      ambient: 0.8,
      key: 1.05,
      rim: 0.44,
      accent: 0.42,
    },
    accessories: {
      pos: [0.1, 0.28, 6.05],
      look: [0, 0.05, -1.55],
      bg: 0x05080f,
      ambient: 0.78,
      key: 1.02,
      rim: 0.4,
      accent: 0.36,
    },
    cart: {
      pos: [0.08, 0.16, 6.15],
      look: [0, 0.0, -1.38],
      bg: 0x04070c,
      ambient: 0.85,
      key: 1.0,
      rim: 0.38,
      accent: 0.34,
    },
    checkout: {
      pos: [-0.04, 0.14, 6.25],
      look: [0, 0.0, -1.25],
      bg: 0x04060b,
      ambient: 0.88,
      key: 0.95,
      rim: 0.36,
      accent: 0.32,
    },
    profile: {
      pos: [0.16, 0.26, 6.45],
      look: [0, 0.05, -1.48],
      bg: 0x05080e,
      ambient: 0.82,
      key: 1.04,
      rim: 0.4,
      accent: 0.36,
    },
    auth: {
      pos: [0.0, 0.14, 6.95],
      look: [0, 0.02, -0.85],
      bg: 0x05070d,
      ambient: 0.9,
      key: 1.0,
      rim: 0.34,
      accent: 0.3,
    },
    seller: {
      pos: [-0.18, 0.18, 6.5],
      look: [0, 0.02, -1.15],
      bg: 0x060807,
      ambient: 0.78,
      key: 0.98,
      rim: 0.36,
      accent: 0.32,
    },
    admin: {
      pos: [0.14, 0.12, 6.6],
      look: [0, 0.02, -1.1],
      bg: 0x060606,
      ambient: 0.76,
      key: 0.95,
      rim: 0.34,
      accent: 0.3,
    },
    unknown: {
      pos: [0.1, 0.14, 7.15],
      look: [0, 0.03, -0.65],
      bg: 0x05070c,
      ...common,
    },
  };

  return chapters[key] || chapters.unknown;
}

class SiteShell3D {
  constructor(canvas, getRoute, getWorld, getCartAvatar) {
    this.canvas = canvas;
    this.getRoute = getRoute || (() => "");
    this.getWorld = getWorld || (() => "");
    this.getCartAvatar = getCartAvatar || (() => ({}));
    this.quality = pickQuality();
    this.running = false;
    this.rafId = 0;
    this.clock = new THREE.Clock();
    this.pointer = { x: 0, y: 0 };
    this.navBoost = 0;
    this.sweepFromHome = false;
    this.motionLane = "idle";

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(46, 1, 0.1, 80);
    const initial = routeChapter(this.getRoute());
    this.camera.position.set(...initial.pos);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: this.quality.antialias,
      powerPreference: "high-performance",
    });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.98;
    this.renderer.setClearAlpha(0);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this.createEnvironment(initial);
    this.createWorldGeometry();
    this.createParticles();

    this.targetChapter = initial;
    this.currentChapter = { ...initial };
    this.targetRouteKey = normalizeRoute(this.getRoute());
    this.targetWorldKey = normalizeWorld(this.getWorld());
    this.targetWorld = worldAtmosphere(this.targetWorldKey);
    this.lookVector = new THREE.Vector3(...initial.look);
    this.tmpBgColor = new THREE.Color(initial.bg);
    this.tmpAccentColor = new THREE.Color(this.targetWorld.accent);
    this.tmpSecondaryColor = new THREE.Color(this.targetWorld.secondary);

    this.handleResize = () => this.resize();
    this.handlePointerMove = (event) => {
      const x = (event.clientX / Math.max(window.innerWidth, 1) - 0.5) * 2;
      const y = (event.clientY / Math.max(window.innerHeight, 1) - 0.5) * 2;
      this.pointer.x = x;
      this.pointer.y = y;
    };
    this.handleVisibility = () => {
      if (document.visibilityState === "hidden") this.stop();
      else this.start();
    };
    this.handleMotionLane = (event) => {
      const lane = String(event?.detail?.lane || document.documentElement?.dataset?.sbMotionLane || "idle")
        .trim()
        .toLowerCase();
      this.motionLane = lane || "idle";
    };

    window.addEventListener("resize", this.handleResize, { passive: true });
    window.addEventListener("pointermove", this.handlePointerMove, { passive: true });
    window.addEventListener("sb:motion-lane-change", this.handleMotionLane, { passive: true });
    document.addEventListener("visibilitychange", this.handleVisibility);

    this.resize();
  }

  destroy() {
    this.stop();
    window.removeEventListener("resize", this.handleResize);
    window.removeEventListener("pointermove", this.handlePointerMove);
    window.removeEventListener("sb:motion-lane-change", this.handleMotionLane);
    document.removeEventListener("visibilitychange", this.handleVisibility);
    this.renderer.dispose();
  }

  createEnvironment(initial) {
    this.ambient = new THREE.AmbientLight(0xe8eef5, initial.ambient ?? 0.82);
    this.key = new THREE.DirectionalLight(0xd4dce8, initial.key ?? 1.12);
    this.key.position.set(2.6, 3.0, 2.0);
    this.rim = new THREE.PointLight(0xc9b8a8, initial.rim ?? 0.42, 24, 2);
    this.rim.position.set(-2.6, 1.1, -3.0);
    this.accent = new THREE.PointLight(0x6eb8e0, initial.accent ?? 0.38, 20, 2);
    this.accent.position.set(1.4, 0.05, 1.0);
    this.scene.add(this.ambient, this.key, this.rim, this.accent);

    this.backdrop = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 14),
      new THREE.MeshBasicMaterial({
        color: initial.bg ?? 0x05070c,
        transparent: true,
        opacity: 0.58,
      })
    );
    this.backdrop.position.set(0, 0.32, -8.8);
    this.scene.add(this.backdrop);
  }

  createWorldGeometry() {
    const ringMat = new THREE.MeshPhysicalMaterial({
      color: 0xa8bdd4,
      emissive: 0x1a2838,
      emissiveIntensity: 0.08,
      roughness: 0.35,
      metalness: 0.55,
      clearcoat: 0.65,
      clearcoatRoughness: 0.18,
      transparent: true,
      opacity: 0.42,
    });

    this.rings = [];
    for (let i = 0; i < 3; i += 1) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(1.42 + i * 0.42, 0.018 + i * 0.003, 14, 120),
        ringMat
      );
      ring.position.set((i - 1) * 0.45, 0.06 + i * 0.1, -1.15 - i * 0.95);
      ring.rotation.x = Math.PI * (0.48 + i * 0.02);
      ring.rotation.y = Math.PI * (0.12 + i * 0.06);
      ring.userData = { speed: 0.045 + i * 0.018, wobble: 0.04 + i * 0.015 };
      this.root.add(ring);
      this.rings.push(ring);
    }

    const panelGeo = new THREE.PlaneGeometry(1.2, 1.95, 12, 12);
    const panelLayout = [
      { pos: [-2.22, 0.62, -2.85], rot: [0.09, 1.18, 0.04], scale: 0.78, drift: 0.11, bob: 0.12 },
      { pos: [2.05, -0.28, -3.5], rot: [0.06, 2.36, 0.08], scale: 0.92, drift: 0.07, bob: 0.1 },
      { pos: [-0.28, -0.86, -4.25], rot: [0.04, 0.54, 0.06], scale: 0.84, drift: 0.06, bob: 0.09 },
      { pos: [1.68, 0.82, -5.15], rot: [0.11, 1.72, 0.1], scale: 0.98, drift: 0.09, bob: 0.11 },
      { pos: [-1.54, -0.04, -6.05], rot: [0.07, 2.78, 0.03], scale: 0.86, drift: 0.08, bob: 0.1 },
    ];
    const panelTints = [0x9aacbc, 0x7d8fa3, 0x6eb8e0];
    this.panels = [];
    for (let i = 0; i < panelLayout.length; i += 1) {
      const layout = panelLayout[i];
      const mat = new THREE.MeshPhysicalMaterial({
        color: panelTints[i % panelTints.length],
        roughness: 0.48,
        metalness: 0.12,
        clearcoat: 0.45,
        clearcoatRoughness: 0.22,
        transparent: true,
        opacity: 0.12,
        side: THREE.DoubleSide,
      });
      const panel = new THREE.Mesh(panelGeo, mat);
      panel.position.set(layout.pos[0], layout.pos[1], layout.pos[2]);
      panel.rotation.set(layout.rot[0], layout.rot[1], layout.rot[2]);
      panel.scale.setScalar(layout.scale);
      panel.userData = { drift: layout.drift, bob: layout.bob };
      this.root.add(panel);
      this.panels.push(panel);
    }
  }

  createParticles() {
    const count = this.quality.particleCount;
    const random = createSeededRandom(44021);
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const angle = random() * Math.PI * 2;
      const radius = 2.8 + random() * 8.6 + (i / Math.max(count, 1)) * 4.2;
      const spread = 0.42 + random() * 0.5;
      positions[i * 3] = Math.cos(angle) * radius * spread;
      positions[i * 3 + 1] = (random() - 0.35) * 11.4;
      positions[i * 3 + 2] = -Math.abs(Math.sin(angle) * radius) - random() * 4.4;
    }
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
      color: 0xc8d8e8,
      size: 0.045,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.particles = new THREE.Points(geo, material);
    this.particles.position.y = 0.22;
    this.scene.add(this.particles);
  }

  resize() {
    const width = this.canvas.clientWidth || window.innerWidth || 800;
    const height = this.canvas.clientHeight || window.innerHeight || 600;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.quality.maxDpr));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / Math.max(height, 1);
    this.camera.updateProjectionMatrix();
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.clock.start();
    this.animate();
  }

  stop() {
    this.running = false;
    this.clock.stop();
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = 0;
    }
  }

  setRoute(routeKey, { immediate = false } = {}) {
    this.targetRouteKey = normalizeRoute(routeKey);
    this.targetChapter = routeChapter(this.targetRouteKey);
    if (immediate) {
      this.currentChapter = { ...this.targetChapter };
      this.camera.position.set(...this.currentChapter.pos);
      this.lookVector.set(...this.currentChapter.look);
      this.camera.lookAt(this.lookVector);
      this.backdrop.material.color.setHex(this.currentChapter.bg);
      this.ambient.intensity = this.currentChapter.ambient;
      this.key.intensity = this.currentChapter.key;
      this.rim.intensity = this.currentChapter.rim;
      this.accent.intensity = this.currentChapter.accent;
    }
  }

  setWorld(worldKey, { immediate = false } = {}) {
    this.targetWorldKey = normalizeWorld(worldKey);
    this.targetWorld = worldAtmosphere(this.targetWorldKey);
    if (immediate) {
      this.accent.color.setHex(this.targetWorld.accent);
      this.rim.color.setHex(this.targetWorld.secondary);
    }
  }

  onNavigateStart(nextRouteKey, { fromRoute = "" } = {}) {
    this.navBoost = 1;
    const from = String(fromRoute || "").trim();
    const toKey = normalizeRoute(nextRouteKey);
    this.sweepFromHome = from === "main.home" && toKey === "discover";
    if (nextRouteKey) this.setRoute(nextRouteKey);
  }

  onNavigateEnd(nextRouteKey) {
    if (nextRouteKey) this.setRoute(nextRouteKey);
    window.setTimeout(() => {
      this.sweepFromHome = false;
    }, 900);
    this.navBoost = Math.min(1, this.navBoost + 0.28);
  }

  setCartAvatar() {
    this.navBoost = Math.min(1, this.navBoost + 0.12);
  }

  animate = () => {
    if (!this.running) return;
    this.rafId = requestAnimationFrame(this.animate);

    const delta = Math.min(this.clock.getDelta(), 0.05);
    const t = this.clock.getElapsedTime();

    const nowRouteKey = normalizeRoute(this.getRoute());
    if (nowRouteKey && nowRouteKey !== this.targetRouteKey) {
      this.setRoute(nowRouteKey);
    }
    const nowWorldKey = normalizeWorld(this.getWorld());
    if (nowWorldKey !== this.targetWorldKey) {
      this.setWorld(nowWorldKey);
    }

    const lane = this.motionLane;
    const primaryLane = lane === "primary";
    const secondaryLane = lane === "secondary";
    const secondaryGain = primaryLane ? 0.46 : 1;
    const tertiaryGain = primaryLane ? 0.08 : secondaryLane ? 0.42 : 1;
    const ambientGain = primaryLane ? 0.2 : secondaryLane ? 0.6 : 1;

    const pointerX = this.pointer.x * 0.18 * tertiaryGain;
    const pointerY = this.pointer.y * 0.09 * tertiaryGain;

    const lerpSpeed = prefersReducedMotion() ? 0.12 : primaryLane ? 0.066 : 0.048;
    const boost = prefersReducedMotion() ? 0 : this.navBoost;
    const navEase = smoothstep(0, 1, boost);

    let posX = this.targetChapter.pos[0];
    let posY = this.targetChapter.pos[1];
    let posZ = this.targetChapter.pos[2];
    let lookX = this.targetChapter.look[0];
    let lookY = this.targetChapter.look[1];
    let lookZ = this.targetChapter.look[2];

    if (this.sweepFromHome && navEase > 0.05) {
      const sweep = Math.sin(navEase * Math.PI) * 0.55;
      posX += sweep;
      posZ += sweep * 0.22;
    }

    const driftX = Math.sin(t * 0.35) * 0.04 * this.targetWorld.driftScale * tertiaryGain;
    const driftY = Math.cos(t * 0.28) * 0.028 * this.targetWorld.driftScale * tertiaryGain;

    this.camera.position.x +=
      (posX + pointerX + driftX - this.camera.position.x) * (lerpSpeed + navEase * 0.04);
    this.camera.position.y +=
      (posY - pointerY + driftY - this.camera.position.y) * (lerpSpeed + navEase * 0.04);
    this.camera.position.z += (posZ - this.camera.position.z) * (lerpSpeed + navEase * 0.038);

    lookX += this.pointer.x * 0.04 * tertiaryGain;
    lookY += this.pointer.y * 0.018 * tertiaryGain;
    this.lookVector.x += (lookX - this.lookVector.x) * (lerpSpeed + navEase * 0.03);
    this.lookVector.y += (lookY - this.lookVector.y) * (lerpSpeed + navEase * 0.03);
    this.lookVector.z += (lookZ - this.lookVector.z) * (lerpSpeed + navEase * 0.03);
    this.camera.lookAt(this.lookVector);

    this.tmpBgColor.setHex(this.targetChapter.bg);
    this.backdrop.material.color.lerp(this.tmpBgColor, 0.05 + navEase * 0.05);

    this.ambient.intensity += (this.targetChapter.ambient * this.targetWorld.ambientScale - this.ambient.intensity) * 0.045;
    this.key.intensity += (this.targetChapter.key * this.targetWorld.keyScale - this.key.intensity) * 0.045;
    this.rim.intensity += (this.targetChapter.rim - this.rim.intensity) * 0.045;
    this.accent.intensity += (this.targetChapter.accent - this.accent.intensity) * 0.045;
    this.tmpAccentColor.setHex(this.targetWorld.accent);
    this.tmpSecondaryColor.setHex(this.targetWorld.secondary);
    this.accent.color.lerp(this.tmpAccentColor, 0.05);
    this.rim.color.lerp(this.tmpSecondaryColor, 0.04);

    const ringEnergy = (1 + navEase * 0.45) * this.targetWorld.motionScale * this.targetWorld.ringScale * secondaryGain;
    this.rings?.forEach((ring, index) => {
      ring.rotation.z += (ring.userData.speed || 0.06) * delta * ringEnergy;
      ring.rotation.y += 0.022 * delta * secondaryGain;
      ring.position.y =
        0.04 +
        index * 0.1 +
        Math.sin(t * 0.75 + index) * (ring.userData.wobble || 0.06) * (0.65 + navEase * 0.4) * secondaryGain;
    });

    this.panels?.forEach((panel, index) => {
      panel.rotation.y += (panel.userData.drift || 0.08) * delta * 0.28 * (0.7 + navEase * 0.5) * secondaryGain;
      panel.rotation.x += 0.01 * delta * secondaryGain;
      panel.position.y +=
        Math.sin(t * 0.48 + index) *
        (panel.userData.bob || 0.1) *
        delta *
        this.targetWorld.motionScale *
        secondaryGain;
    });

    if (this.particles) {
      this.particles.rotation.y =
        t * (0.014 + navEase * 0.028) * this.targetWorld.motionScale * this.targetWorld.particleScale * ambientGain;
      this.particles.rotation.x =
        Math.sin(t * 0.1) * (0.045 + navEase * 0.04) * this.targetWorld.motionScale * this.targetWorld.particleScale * ambientGain;
    }

    this.navBoost = Math.max(0, this.navBoost - delta * (primaryLane ? 0.62 : 0.85));
    this.renderer.render(this.scene, this.camera);
  };
}

export function bootSiteShell3D({ canvasId, getRoute, getWorld, getCartAvatar } = {}) {
  const canvas = document.getElementById(canvasId || "");
  if (!canvas) return null;

  if (!supportsWebGL()) {
    canvas.style.display = "none";
    return null;
  }

  const shell = new SiteShell3D(canvas, getRoute, getWorld, getCartAvatar);
  shell.start();
  shell.setRoute(getRoute?.(), { immediate: true });
  shell.setWorld(getWorld?.(), { immediate: true });
  return shell;
}
