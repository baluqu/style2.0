import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.module.js";

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function smoothstep(edge0, edge1, x) {
  const t = clamp01((x - edge0) / Math.max(edge1 - edge0, 1e-6));
  return t * t * (3 - 2 * t);
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

function pickQuality() {
  if (prefersReducedMotion()) {
    return { maxDpr: 1, particleCount: 220, antialias: false };
  }
  if (isLowMemoryDevice() || window.innerWidth < 900) {
    return { maxDpr: 1.25, particleCount: 520, antialias: false };
  }
  return { maxDpr: 1.6, particleCount: 900, antialias: true };
}

function getScrollProgress() {
  const doc = document.documentElement;
  const scrollTop = window.scrollY || doc.scrollTop || 0;
  const max = Math.max(1, (doc.scrollHeight || 1) - window.innerHeight);
  return clamp01(scrollTop / max);
}

function setFallbackGradient() {
  const body = document.body;
  if (!body) return;
  body.style.background =
    "radial-gradient(circle at 24% 18%, rgba(34,211,238,0.14), transparent 46%), radial-gradient(circle at 78% 34%, rgba(168,85,247,0.12), transparent 50%), radial-gradient(circle at 56% 84%, rgba(16,185,129,0.10), transparent 55%), linear-gradient(180deg, rgb(2,6,23), rgb(15,23,42))";
}

class HomeScene {
  constructor(canvas) {
    this.canvas = canvas;
    this.quality = pickQuality();
    this.running = false;
    this.rafId = 0;
    this.clock = new THREE.Clock();
    this.pointer = { x: 0, y: 0 };
    this.progress = 0;
    this.targetProgress = getScrollProgress();

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(46, 1, 0.1, 80);
    this.camera.position.set(0.15, 0.2, 7.8);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: this.quality.antialias,
      powerPreference: "high-performance",
    });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.setClearAlpha(0);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this.createEnvironment();
    this.createFloatingForms();
    this.createParticles();

    this.handleResize = () => this.resize();
    this.handleScroll = () => {
      this.targetProgress = getScrollProgress();
    };
    this.handlePointerMove = (event) => {
      const x = (event.clientX / Math.max(window.innerWidth, 1) - 0.5) * 2;
      const y = (event.clientY / Math.max(window.innerHeight, 1) - 0.5) * 2;
      this.pointer.x = x;
      this.pointer.y = y;
    };
    this.handleVisibility = () => {
      if (document.visibilityState === "hidden") {
        this.stop();
      } else {
        this.start();
      }
    };

    window.addEventListener("resize", this.handleResize, { passive: true });
    window.addEventListener("scroll", this.handleScroll, { passive: true });
    window.addEventListener("pointermove", this.handlePointerMove, { passive: true });
    document.addEventListener("visibilitychange", this.handleVisibility);

    this.resize();
  }

  destroy() {
    this.stop();
    window.removeEventListener("resize", this.handleResize);
    window.removeEventListener("scroll", this.handleScroll);
    window.removeEventListener("pointermove", this.handlePointerMove);
    document.removeEventListener("visibilitychange", this.handleVisibility);
    this.renderer.dispose();
  }

  createEnvironment() {
    this.ambient = new THREE.AmbientLight(0xe7f2ff, 0.9);
    this.key = new THREE.DirectionalLight(0xbff5ff, 1.4);
    this.key.position.set(2.8, 3.2, 2.2);
    this.rim = new THREE.PointLight(0xffd4a1, 0.75, 22, 2);
    this.rim.position.set(-2.8, 1.2, -3.2);
    this.accent = new THREE.PointLight(0x6ef1ff, 0.55, 18, 2);
    this.accent.position.set(1.6, 0.1, 1.2);
    this.scene.add(this.ambient, this.key, this.rim, this.accent);

    this.backdrop = new THREE.Mesh(
      new THREE.PlaneGeometry(22, 14),
      new THREE.MeshBasicMaterial({ color: 0x050b16, transparent: true, opacity: 0.65 })
    );
    this.backdrop.position.set(0, 0.35, -8.8);
    this.scene.add(this.backdrop);
  }

  createFloatingForms() {
    const ringMat = new THREE.MeshPhysicalMaterial({
      color: 0xa8bdd4,
      emissive: 0x1a2838,
      emissiveIntensity: 0.06,
      roughness: 0.32,
      metalness: 0.5,
      clearcoat: 0.62,
      clearcoatRoughness: 0.16,
      transparent: true,
      opacity: 0.4,
    });

    this.rings = [];
    for (let i = 0; i < 4; i += 1) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1.45 + i * 0.35, 0.02 + i * 0.004, 16, 140), ringMat);
      ring.position.set((i - 1.5) * 0.65, 0.1 + i * 0.12, -1.4 - i * 0.9);
      ring.rotation.x = Math.PI * (0.46 + i * 0.02);
      ring.rotation.y = Math.PI * (0.15 + i * 0.08);
      ring.userData = { speed: 0.08 + i * 0.03, wobble: 0.06 + i * 0.02 };
      this.root.add(ring);
      this.rings.push(ring);
    }

    const panelGeo = new THREE.PlaneGeometry(1.45, 2.35, 18, 18);
    const panelColors = [0x9aacbc, 0x7d8fa3, 0x6eb8e0];
    this.panels = [];
    for (let i = 0; i < 6; i += 1) {
      const mat = new THREE.MeshPhysicalMaterial({
        color: panelColors[i % panelColors.length],
        roughness: 0.42,
        metalness: 0.08,
        clearcoat: 0.55,
        clearcoatRoughness: 0.2,
        transparent: true,
        opacity: 0.12,
        side: THREE.DoubleSide,
      });
      const panel = new THREE.Mesh(panelGeo, mat);
      panel.position.set((Math.random() - 0.5) * 5.4, (Math.random() - 0.5) * 2.5, -2.2 - Math.random() * 5.6);
      panel.rotation.set(Math.random() * 0.3, Math.random() * Math.PI, Math.random() * 0.25);
      panel.scale.setScalar(0.75 + Math.random() * 0.55);
      panel.userData = { drift: 0.06 + Math.random() * 0.12, bob: 0.08 + Math.random() * 0.2 };
      this.root.add(panel);
      this.panels.push(panel);
    }
  }

  createParticles() {
    const count = this.quality.particleCount;
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 18;
      positions[i * 3 + 1] = (Math.random() - 0.35) * 12;
      positions[i * 3 + 2] = -Math.random() * 14;
      sizes[i] = 0.35 + Math.random() * 0.8;
    }
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));

    const material = new THREE.PointsMaterial({
      color: 0xc8d8e8,
      size: 0.045,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.particles = new THREE.Points(geo, material);
    this.particles.position.y = 0.25;
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
    if (this.running || prefersReducedMotion()) return;
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

  applyScrollChapters(progress) {
    const chapterA = smoothstep(0.0, 0.35, progress);
    const chapterB = smoothstep(0.35, 0.7, progress);
    const chapterC = smoothstep(0.7, 1.0, progress);

    const p0 = { pos: [0.15, 0.2, 7.8], look: [0, 0.05, 0], bg: 0x050b16 };
    const p1 = { pos: [-0.25, 0.55, 6.7], look: [0, 0.15, -0.8], bg: 0x061327 };
    const p2 = { pos: [0.25, 0.3, 6.1], look: [0, 0.0, -1.6], bg: 0x04101c };

    const pos01 = [
      lerp(p0.pos[0], p1.pos[0], chapterA),
      lerp(p0.pos[1], p1.pos[1], chapterA),
      lerp(p0.pos[2], p1.pos[2], chapterA),
    ];
    const look01 = [
      lerp(p0.look[0], p1.look[0], chapterA),
      lerp(p0.look[1], p1.look[1], chapterA),
      lerp(p0.look[2], p1.look[2], chapterA),
    ];

    const pos12 = [
      lerp(p1.pos[0], p2.pos[0], chapterB),
      lerp(p1.pos[1], p2.pos[1], chapterB),
      lerp(p1.pos[2], p2.pos[2], chapterB),
    ];
    const look12 = [
      lerp(p1.look[0], p2.look[0], chapterB),
      lerp(p1.look[1], p2.look[1], chapterB),
      lerp(p1.look[2], p2.look[2], chapterB),
    ];

    const w = chapterC;
    const pos = [
      lerp(pos01[0], pos12[0], w),
      lerp(pos01[1], pos12[1], w),
      lerp(pos01[2], pos12[2], w),
    ];
    const look = [
      lerp(look01[0], look12[0], w),
      lerp(look01[1], look12[1], w),
      lerp(look01[2], look12[2], w),
    ];

    const bg0 = new THREE.Color(p0.bg);
    const bg1 = new THREE.Color(p1.bg);
    const bg2 = new THREE.Color(p2.bg);
    const bg = bg0.clone().lerp(bg1, chapterA).lerp(bg2, chapterB * 0.9);

    return { pos, look, bg };
  }

  animate = () => {
    if (!this.running) return;
    this.rafId = requestAnimationFrame(this.animate);

    const delta = this.clock.getDelta();
    const t = this.clock.getElapsedTime();

    this.progress += (this.targetProgress - this.progress) * 0.06;
    const stage = this.applyScrollChapters(this.progress);

    const pointerX = this.pointer.x * 0.25;
    const pointerY = this.pointer.y * 0.12;

    this.camera.position.x += (stage.pos[0] + pointerX - this.camera.position.x) * 0.05;
    this.camera.position.y += (stage.pos[1] - pointerY - this.camera.position.y) * 0.05;
    this.camera.position.z += (stage.pos[2] - this.camera.position.z) * 0.04;
    this.camera.lookAt(stage.look[0], stage.look[1], stage.look[2]);

    if (this.backdrop?.material?.color) {
      this.backdrop.material.color.lerp(stage.bg, 0.08);
    }

    this.rings?.forEach((ring, index) => {
      ring.rotation.z += (ring.userData.speed || 0.1) * delta;
      ring.rotation.y += 0.04 * delta;
      ring.position.y = 0.05 + index * 0.12 + Math.sin(t * 0.9 + index) * (ring.userData.wobble || 0.08);
    });

    this.panels?.forEach((panel, index) => {
      panel.rotation.y += (panel.userData.drift || 0.1) * delta * 0.35;
      panel.rotation.x += 0.015 * delta;
      panel.position.y += Math.sin(t * 0.55 + index) * (panel.userData.bob || 0.12) * delta;
    });

    if (this.particles) {
      this.particles.rotation.y = t * 0.02;
      this.particles.rotation.x = Math.sin(t * 0.12) * 0.06;
    }

    this.renderer.render(this.scene, this.camera);
  };
}

export function bootHomeScene({ canvasId } = {}) {
  const canvas = document.getElementById(canvasId || "");
  if (!canvas) return null;

  if (!supportsWebGL() || prefersReducedMotion()) {
    canvas.style.display = "none";
    setFallbackGradient();
    return null;
  }

  const scene = new HomeScene(canvas);
  scene.start();
  return scene;
}

