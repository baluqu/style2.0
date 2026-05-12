import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { animate, motionValue } from "framer-motion";

const h = React.createElement;

const HERO_MODEL_URL = "/static/models/jujutsu_kaisen_toji_fushiguro.glb?v=20260512-hero4";
const HERO_MODEL_FALLBACK_URL = "/static/models/toji-reference.glb?v=20260402-toji1";
const DEFAULT_WORLD_SLUG = "quiet-luxury";

const WORLD_MOTION_PROFILES = {
  default: {
    tempo: 1,
    drift: 1,
    contrast: 1,
    blur: 0.55,
    rotation: 1,
    zoom: 1,
  },
  "quiet-luxury": {
    tempo: 0.74,
    drift: 0.88,
    contrast: 0.82,
    blur: 0.46,
    rotation: 0.82,
    zoom: 0.92,
  },
  "tokyo-street": {
    tempo: 1.2,
    drift: 0.62,
    contrast: 1.2,
    blur: 0.74,
    rotation: 1.08,
    zoom: 1.06,
  },
  "dark-academia": {
    tempo: 0.7,
    drift: 0.96,
    contrast: 0.9,
    blur: 0.56,
    rotation: 0.78,
    zoom: 0.88,
  },
  "neo-minimal": {
    tempo: 0.62,
    drift: 0.52,
    contrast: 0.68,
    blur: 0.3,
    rotation: 0.72,
    zoom: 0.78,
  },
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function damp(current, target, smoothing, delta) {
  const t = 1 - Math.exp(-smoothing * delta);
  return current + (target - current) * t;
}

function worldProfileFromValue(value) {
  if (!value) {
    return { ...WORLD_MOTION_PROFILES.default };
  }
  const slug = String(value).trim().toLowerCase();
  return {
    ...WORLD_MOTION_PROFILES.default,
    ...(WORLD_MOTION_PROFILES[slug] || {}),
  };
}

function normalizedWorldProfile(profile = {}, slug = DEFAULT_WORLD_SLUG) {
  const base = worldProfileFromValue(slug);
  return {
    tempo: clamp(Number(profile.tempo ?? base.tempo), 0.45, 1.35),
    drift: clamp(Number(profile.drift ?? base.drift), 0.45, 1.2),
    contrast: clamp(Number(profile.contrast ?? base.contrast), 0.6, 1.3),
    blur: clamp(Number(profile.blur ?? base.blur), 0.2, 0.9),
    rotation: clamp(Number(profile.rotation ?? base.rotation), 0.65, 1.2),
    zoom: clamp(Number(profile.zoom ?? base.zoom), 0.75, 1.12),
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

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function isLowMemoryDevice() {
  try {
    return Boolean(navigator.deviceMemory && navigator.deviceMemory <= 2);
  } catch {
    return false;
  }
}

function pickQuality() {
  if (prefersReducedMotion()) {
    return {
      maxDpr: 1,
      antialias: false,
      shadows: false,
      shadowSize: 512,
    };
  }
  if (isLowMemoryDevice() || window.innerWidth < 960) {
    return {
      maxDpr: 1.25,
      antialias: false,
      shadows: true,
      shadowSize: 1024,
    };
  }
  return {
    maxDpr: 1.7,
    antialias: true,
    shadows: true,
    shadowSize: 2048,
  };
}

async function loadGsap() {
  try {
    const mod = await import("https://cdn.jsdelivr.net/npm/gsap@3.12.5/index.js");
    return mod.gsap || mod.default || null;
  } catch {
    return null;
  }
}

function tuneMaterial(material) {
  if (!material) {
    return;
  }
  if (material.map) {
    material.map.colorSpace = THREE.SRGBColorSpace;
    material.map.needsUpdate = true;
  }
  if ("roughness" in material) {
    material.roughness = clamp((material.roughness || 0.45) * 0.94, 0.08, 1);
  }
  if ("metalness" in material) {
    material.metalness = clamp((material.metalness || 0.06) + 0.07, 0, 1);
  }
  if ("envMapIntensity" in material) {
    material.envMapIntensity = 1;
  }
  if ("clearcoat" in material) {
    material.clearcoat = Math.max(material.clearcoat || 0, 0.32);
    material.clearcoatRoughness = clamp(material.clearcoatRoughness || 0.24, 0.12, 0.5);
  }
  material.needsUpdate = true;
}

function prepareModel(sourceScene, shadowsEnabled) {
  const model = sourceScene.clone(true);

  model.traverse((node) => {
    if (!node.isMesh) {
      return;
    }

    node.castShadow = shadowsEnabled;
    node.receiveShadow = shadowsEnabled;

    if (Array.isArray(node.material)) {
      node.material = node.material.map((material) => {
        const cloned = material?.clone ? material.clone() : material;
        tuneMaterial(cloned);
        return cloned;
      });
    } else if (node.material) {
      node.material = node.material.clone ? node.material.clone() : node.material;
      tuneMaterial(node.material);
    }
  });

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  model.position.sub(center);

  const scale = 2.44 / Math.max(size.y, 0.0001);
  model.scale.setScalar(scale);

  const adjusted = new THREE.Box3().setFromObject(model);
  model.position.y += -adjusted.min.y - 1.16;
  model.position.x += 0.02;

  return model;
}

function useHeroModel({ modelUrl, fallbackUrl, onProgress, onError }) {
  const [scene, setScene] = useState(null);

  useEffect(() => {
    let active = true;
    const loader = new GLTFLoader();

    const loadWithUrl = (url, isFallback = false) => {
      loader.load(
        url,
        (gltf) => {
          if (!active) {
            return;
          }
          const payload = gltf?.scene || gltf?.scenes?.[0] || null;
          if (!payload) {
            onError?.(new Error("GLB scene payload missing."));
            return;
          }
          setScene(payload);
        },
        (progress) => {
          const total = progress.total || progress.loaded || 1;
          const percent = clamp(Math.round((progress.loaded / total) * 100), 0, 100);
          onProgress?.(percent, { fallback: isFallback });
        },
        (error) => {
          if (!active) {
            return;
          }
          if (!isFallback && fallbackUrl) {
            loadWithUrl(fallbackUrl, true);
            return;
          }
          onError?.(error);
        }
      );
    };

    loadWithUrl(modelUrl, false);

    return () => {
      active = false;
    };
  }, [modelUrl, fallbackUrl, onProgress, onError]);

  return scene;
}

function ArtifactModel({
  modelUrl,
  fallbackUrl,
  quality,
  onModelReady,
  onLoadProgress,
  onLoadError,
}) {
  const rawScene = useHeroModel({
    modelUrl,
    fallbackUrl,
    onProgress: onLoadProgress,
    onError: onLoadError,
  });

  const preparedScene = useMemo(() => {
    if (!rawScene) {
      return null;
    }
    return prepareModel(rawScene, quality.shadows);
  }, [rawScene, quality.shadows]);

  useEffect(() => {
    if (preparedScene) {
      onModelReady?.();
    }
  }, [preparedScene, onModelReady]);

  if (!preparedScene) {
    return null;
  }

  return h("primitive", { object: preparedScene, dispose: null });
}

function HeroScene({
  stateRef,
  phaseRef,
  quality,
  modelUrl,
  fallbackUrl,
  onModelReady,
  onLoadProgress,
  onLoadError,
}) {
  const orbitRef = useRef(null);
  const floatRef = useRef(null);
  const keyRef = useRef(null);
  const rimRef = useRef(null);
  const silverRef = useRef(null);
  const glowRef = useRef(null);
  const sideGlowRef = useRef(null);
  const { camera, size } = useThree();

  useEffect(() => {
    camera.fov = 34;
    camera.near = 0.1;
    camera.far = 60;
    camera.position.set(0.02, 0.18, 4.95);
    camera.updateProjectionMatrix();
  }, [camera]);

  useFrame((frame, delta) => {
    const stageState = stateRef.current;
    const phase = phaseRef.current;
    const t = frame.clock.getElapsedTime();
    const world = stageState.worldProfile || WORLD_MOTION_PROFILES.default;

    stageState.pointer.x = damp(stageState.pointer.x, stageState.pointerTarget.x, 6.2, delta);
    stageState.pointer.y = damp(stageState.pointer.y, stageState.pointerTarget.y, 6.2, delta);

    const driftX = Math.sin(t * 0.23 * world.tempo) * 0.07 * world.drift;
    const driftY = Math.cos(t * 0.17 * world.tempo) * 0.045 * world.drift;
    const breath = Math.sin(t * 0.2 * world.tempo) * 0.07 * world.zoom;

    stageState.spin += delta * 0.104 * world.rotation;
    const lift = Math.sin(t * 0.64 * world.tempo) * 0.052 * world.drift;
    const wave = Math.sin(t * 0.44 * world.tempo) * 0.06 * world.rotation;
    const roll = Math.sin(t * 0.34 * world.tempo) * 0.017 * world.rotation;

    const width = size.width || window.innerWidth || 1280;
    const baseScale = width < 700 ? 0.84 : width < 1100 ? 0.95 : 1;
    const revealScale = 0.9 + phase * 0.1;

    if (orbitRef.current) {
      orbitRef.current.rotation.y = damp(
        orbitRef.current.rotation.y,
        stageState.spin + stageState.pointer.x * 0.1 + wave,
        3.1,
        delta
      );
      orbitRef.current.rotation.x = damp(
        orbitRef.current.rotation.x,
        -0.02 + stageState.pointer.y * 0.05,
        3.0,
        delta
      );
      orbitRef.current.rotation.z = damp(orbitRef.current.rotation.z, roll, 2.7, delta);
      orbitRef.current.scale.setScalar(baseScale * revealScale);
    }

    if (floatRef.current) {
      floatRef.current.position.y = damp(floatRef.current.position.y, lift, 3.7, delta);
      floatRef.current.position.x = damp(floatRef.current.position.x, stageState.pointer.x * 0.045, 3.7, delta);
    }

    const targetCamX = 0.02 + stageState.pointer.x * 0.16 + driftX;
    const targetCamY = 0.18 - stageState.pointer.y * 0.09 + driftY + stageState.progress * 0.03;
    const targetCamZ = 4.95 - phase * 0.6 * world.zoom + breath + stageState.progress * 0.12;

    camera.position.x = damp(camera.position.x, targetCamX, 3.9, delta);
    camera.position.y = damp(camera.position.y, targetCamY, 3.9, delta);
    camera.position.z = damp(camera.position.z, targetCamZ, 3.55, delta);
    camera.lookAt(
      damp(0, stageState.pointer.x * 0.14, 3.4, delta),
      0.02 + stageState.pointer.y * 0.045,
      -0.08 - stageState.progress * 0.2
    );

    if (keyRef.current) {
      keyRef.current.position.x = 2.6 + Math.sin(t * 0.28) * 0.34;
      keyRef.current.position.y = 3.3 + Math.cos(t * 0.23) * 0.22;
    }
    if (rimRef.current) {
      rimRef.current.position.x = -3.1 + Math.sin(t * 0.2) * 0.2;
    }
    if (silverRef.current) {
      silverRef.current.intensity = (0.42 + Math.sin(t * 0.48 * world.tempo) * 0.05) * world.contrast;
    }
    if (glowRef.current?.material) {
      glowRef.current.rotation.z = -t * 0.035;
      glowRef.current.material.opacity = (0.2 + Math.sin(t * 0.35 * world.tempo) * 0.035) * world.blur;
    }
    if (sideGlowRef.current?.material) {
      sideGlowRef.current.rotation.z = t * 0.042;
      sideGlowRef.current.material.opacity = (0.12 + Math.cos(t * 0.33 * world.tempo) * 0.03) * world.blur;
    }

    const artifactX = clamp(stageState.pointer.x * 1.9 + Math.sin(t * 0.35) * 0.65, -5.6, 5.6);
    const artifactY = clamp(stageState.pointer.y * 1.1 + Math.cos(t * 0.26) * 0.4, -3.1, 3.1);
    const spinDeg = ((stageState.spin % (Math.PI * 2)) * 180) / Math.PI;
    const uiShiftX = clamp(stageState.pointer.x * 10 + Math.sin(t * 0.41) * 3, -14, 14);
    const uiShiftY = clamp(stageState.pointer.y * 7 + Math.cos(t * 0.33) * 2.4, -10, 10);
    const uiDepth = clamp(110 + phase * 78 + Math.sin(t * 0.28) * 10, 90, 220);
    const uiTilt = clamp(stageState.pointer.x * -1.8 + Math.sin(t * 0.37) * 0.9, -3.2, 3.2);
    const lightAlpha = clamp(
      (0.1 + Math.sin(t * 0.3 * world.tempo + stageState.spin * 0.2) * 0.07) * world.contrast,
      0.02,
      0.2
    );

    stageState.onSync?.({
      artifactX,
      artifactY,
      spinDeg,
      breathPx: breath * 16,
      lightAlpha,
      uiShiftX,
      uiShiftY,
      uiDepth,
      uiTilt,
    });
  });

  return h(
    React.Fragment,
    null,
    h("color", { attach: "background", args: [0x020306] }),
    h("fog", { attach: "fog", args: [0x030508, 5.2, 16.8] }),
    h("ambientLight", { color: 0xcfd8e2, intensity: 0.58 }),
    h("directionalLight", {
      ref: keyRef,
      color: 0xddeaff,
      intensity: 1.36,
      position: [2.6, 3.3, 3.9],
      castShadow: quality.shadows,
      "shadow-mapSize-width": quality.shadowSize,
      "shadow-mapSize-height": quality.shadowSize,
      "shadow-bias": -0.00028,
    }),
    h("directionalLight", {
      color: 0x8da9c7,
      intensity: 0.43,
      position: [-2.2, 1.3, 3.3],
    }),
    h("pointLight", {
      ref: rimRef,
      color: 0x85abd8,
      intensity: 0.74,
      distance: 16,
      decay: 2,
      position: [-3.1, 1.55, -2.8],
    }),
    h("pointLight", {
      ref: silverRef,
      color: 0xdde8f1,
      intensity: 0.42,
      distance: 12,
      decay: 2,
      position: [1.9, 0.45, 1.6],
    }),
    h(
      "mesh",
      {
        position: [0, -1.24, 0.05],
        rotation: [-Math.PI / 2, 0, 0],
        receiveShadow: quality.shadows,
      },
      h("circleGeometry", { args: [2.15, 72] }),
      h("meshPhysicalMaterial", {
        color: 0x080d13,
        roughness: 0.24,
        metalness: 0.22,
        clearcoat: 0.82,
        clearcoatRoughness: 0.18,
        transparent: true,
        opacity: 0.58,
      })
    ),
    quality.shadows
      ? h(
          "mesh",
          {
            position: [0, -1.236, 0],
            rotation: [-Math.PI / 2, 0, 0],
            receiveShadow: true,
          },
          h("planeGeometry", { args: [6.4, 6.4] }),
          h("shadowMaterial", { opacity: 0.28 })
        )
      : null,
    h(
      "mesh",
      { ref: glowRef, position: [-0.18, 0.24, -2.6] },
      h("planeGeometry", { args: [5.8, 5.8] }),
      h("meshBasicMaterial", {
        color: 0x74b1ff,
        transparent: true,
        opacity: 0.2,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    ),
    h(
      "mesh",
      { ref: sideGlowRef, position: [1.35, 0.5, -1.6] },
      h("planeGeometry", { args: [3.7, 3.7] }),
      h("meshBasicMaterial", {
        color: 0xd4e2f0,
        transparent: true,
        opacity: 0.12,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
    ),
    h(
      "group",
      { ref: floatRef },
      h(
        "group",
        { ref: orbitRef },
        h(ArtifactModel, {
          modelUrl,
          fallbackUrl,
          quality,
          onModelReady,
          onLoadProgress,
          onLoadError,
        })
      )
    )
  );
}

function HeroCanvas({
  stateRef,
  phaseRef,
  quality,
  modelUrl,
  fallbackUrl,
  onModelReady,
  onLoadProgress,
  onLoadError,
}) {
  return h(
    Canvas,
    {
      shadows: quality.shadows,
      dpr: [1, quality.maxDpr],
      gl: {
        antialias: quality.antialias,
        alpha: true,
        powerPreference: "high-performance",
      },
      camera: { position: [0.02, 0.18, 4.95], fov: 34, near: 0.1, far: 60 },
      frameloop: "always",
      eventSource: document.getElementById("sb-cinema-stage") || undefined,
      onCreated: ({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 0.94;
        gl.outputColorSpace = THREE.SRGBColorSpace;
        gl.shadowMap.enabled = quality.shadows;
        gl.shadowMap.type = THREE.PCFSoftShadowMap;
      },
    },
    h(
      Suspense,
      { fallback: null },
      h(HeroScene, {
        stateRef,
        phaseRef,
        quality,
        modelUrl,
        fallbackUrl,
        onModelReady,
        onLoadProgress,
        onLoadError,
      })
    )
  );
}

async function runRevealSequence(stage, phaseRef, { intro, statusEl } = {}) {
  const reduced = prefersReducedMotion();

  if (reduced) {
    phaseRef.current = 1;
    stage.classList.add("sb-hero-live", "sb-hero-ui-live", "sb-hero-model-on");
    stage.classList.remove("sb-hero-sequence");
    if (statusEl) {
      statusEl.textContent = "Artifact online";
      window.setTimeout(() => statusEl.classList.add("is-muted"), 900);
    }
    return;
  }

  stage.classList.add("sb-hero-sequence", "sb-hero-text-on");
  const gsap = await loadGsap();
  const wordmark = intro?.querySelector(".sb-hero-wordmark");
  const letters = intro?.querySelectorAll(".sb-hero-wordmark span");
  const sub = intro?.querySelector(".sb-hero-subline");
  const panelStack = stage.querySelector(".sb-panel-stack");
  const orbitCluster = stage.querySelector(".sb-orbit-cluster");
  const chapterRail = stage.querySelector(".sb-chapter-rail");
  const hud = stage.querySelector(".sb-cinema-hud");

  if (gsap && wordmark && letters?.length && sub && panelStack && orbitCluster && chapterRail && hud) {
    gsap.set(letters, { opacity: 0, z: -86, filter: "blur(9px)" });
    gsap.set(sub, { opacity: 0, y: 12, filter: "blur(6px)" });
    gsap.set([panelStack, orbitCluster, chapterRail, hud], { opacity: 0, y: 20, filter: "blur(10px)" });
    gsap.set(stage, { "--sb-hero-curtain-opacity": 1 });
    phaseRef.current = 0;

    const timeline = gsap.timeline({
      defaults: { ease: "power2.out" },
      onComplete: () => {
        phaseRef.current = 1;
        stage.classList.add("sb-hero-live", "sb-hero-ui-live", "sb-hero-model-on");
        stage.classList.remove("sb-hero-sequence", "sb-hero-text-on", "sb-hero-text-push");
        if (statusEl) {
          statusEl.textContent = "Artifact online";
          window.setTimeout(() => statusEl.classList.add("is-muted"), 800);
        }
      },
    });

    timeline
      .to(letters, { opacity: 1, z: 0, filter: "blur(0px)", duration: 0.9, stagger: 0.045 }, 0.08)
      .to(sub, { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.64 }, 0.36)
      .add(() => stage.classList.add("sb-hero-text-push"), 1.2)
      .to(wordmark, { opacity: 0, scale: 2.22, filter: "blur(14px)", duration: 1.0, ease: "power3.inOut" }, 1.2)
      .to(sub, { opacity: 0, y: -8, duration: 0.48 }, 1.28)
      .to(stage, { "--sb-hero-curtain-opacity": 0, duration: 1.2, ease: "sine.out" }, 1.55)
      .to(phaseRef, { current: 1, duration: 1.85, ease: "sine.inOut" }, 1.5)
      .add(() => stage.classList.add("sb-hero-model-on"), 1.6)
      .to([panelStack, orbitCluster, chapterRail, hud], { opacity: 1, y: 0, filter: "blur(0px)", duration: 1.02, stagger: 0.08 }, 2.0);
    return;
  }

  phaseRef.current = 0.16;
  window.setTimeout(() => stage.classList.add("sb-hero-text-push"), 1200);
  window.setTimeout(() => {
    stage.classList.add("sb-hero-model-on");
    phaseRef.current = 1;
  }, 1640);
  window.setTimeout(() => stage.classList.add("sb-hero-ui-live"), 2120);
  window.setTimeout(() => {
    stage.classList.add("sb-hero-live");
    stage.classList.remove("sb-hero-sequence", "sb-hero-text-on", "sb-hero-text-push");
    if (statusEl) {
      statusEl.textContent = "Artifact online";
      statusEl.classList.add("is-muted");
    }
  }, 2640);
}

export function bootHomeHeroScene({
  stageId = "sb-cinema-stage",
  canvasId = "sb-hero-model-canvas",
  introId = "sb-hero-intro",
  statusId = "sb-hero-status",
  modelUrl = HERO_MODEL_URL,
  fallbackUrl = HERO_MODEL_FALLBACK_URL,
} = {}) {
  const stage = document.getElementById(stageId);
  const mount = document.getElementById(canvasId);
  const intro = document.getElementById(introId);
  const statusEl = document.getElementById(statusId);

  if (!stage || !mount) {
    return null;
  }

  const updateStatus = (message, muted = false) => {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = message;
    statusEl.classList.toggle("is-muted", muted);
  };

  if (!supportsWebGL()) {
    stage.classList.add("sb-hero-fallback", "sb-hero-live", "sb-hero-ui-live", "sb-hero-model-on");
    updateStatus("Cinematic mode (2D)", true);
    return null;
  }

  const quality = pickQuality();
  const initialWorldSlug = (String(stage.dataset.world || DEFAULT_WORLD_SLUG).trim().toLowerCase() || DEFAULT_WORLD_SLUG);
  const stageStateRef = {
    current: {
      pointer: { x: 0, y: 0 },
      pointerTarget: { x: 0, y: 0 },
      progress: 0,
      spin: 0,
      onSync: null,
      worldSlug: initialWorldSlug,
      worldProfile: normalizedWorldProfile({}, initialWorldSlug),
    },
  };
  const phaseRef = { current: prefersReducedMotion() ? 1 : 0 };
  let revealed = false;
  let disposed = false;

  updateStatus("Loading artifact 0%");

  const root = createRoot(mount);

  const artifactXMV = motionValue(0);
  const artifactYMV = motionValue(0);
  const spinMV = motionValue(0);
  const breathMV = motionValue(0);
  const lightMV = motionValue(0.08);
  const uiShiftXMV = motionValue(0);
  const uiShiftYMV = motionValue(0);
  const uiDepthMV = motionValue(0);
  const uiTiltMV = motionValue(0);

  const unsubs = [
    artifactXMV.on("change", (value) => stage.style.setProperty("--sb-artifact-x", `${value.toFixed(3)}%`)),
    artifactYMV.on("change", (value) => stage.style.setProperty("--sb-artifact-y", `${value.toFixed(3)}%`)),
    spinMV.on("change", (value) => stage.style.setProperty("--sb-artifact-spin", `${value.toFixed(2)}deg`)),
    breathMV.on("change", (value) => stage.style.setProperty("--sb-artifact-breath", `${value.toFixed(2)}px`)),
    lightMV.on("change", (value) => stage.style.setProperty("--sb-light-alpha", value.toFixed(4))),
    uiShiftXMV.on("change", (value) => stage.style.setProperty("--sb-ui-shift-x", `${value.toFixed(2)}px`)),
    uiShiftYMV.on("change", (value) => stage.style.setProperty("--sb-ui-shift-y", `${value.toFixed(2)}px`)),
    uiDepthMV.on("change", (value) => stage.style.setProperty("--sb-ui-depth", `${value.toFixed(2)}px`)),
    uiTiltMV.on("change", (value) => stage.style.setProperty("--sb-ui-tilt", `${value.toFixed(3)}deg`)),
  ];

  stageStateRef.current.onSync = ({ artifactX, artifactY, spinDeg, breathPx, lightAlpha, uiShiftX, uiShiftY, uiDepth, uiTilt }) => {
    artifactXMV.set(artifactX);
    artifactYMV.set(artifactY);
    spinMV.set(spinDeg);
    breathMV.set(breathPx);
    lightMV.set(lightAlpha);
    uiShiftXMV.set(uiShiftX);
    uiShiftYMV.set(uiShiftY);
    uiDepthMV.set(uiDepth);
    uiTiltMV.set(uiTilt);
  };

  const onModelReady = async () => {
    if (disposed || revealed) {
      return;
    }
    revealed = true;
    animate(uiDepthMV, 148, { duration: 1.85, ease: [0.22, 1, 0.36, 1] });
    await runRevealSequence(stage, phaseRef, { intro, statusEl });
    animate(uiDepthMV, 194, { duration: 1.7, ease: [0.22, 1, 0.36, 1] });
    animate(lightMV, 0.12, { duration: 2.1, ease: "easeOut" });
  };

  const onLoadProgress = (percent, { fallback } = {}) => {
    const label = fallback ? "Loading backup artifact" : "Loading artifact";
    updateStatus(`${label} ${percent}%`);
  };

  const onLoadError = (error) => {
    console.error("Hero model failed to load:", error);
    stage.classList.add("sb-hero-live", "sb-hero-ui-live", "sb-hero-model-on", "sb-hero-fallback");
    stage.classList.remove("sb-hero-sequence", "sb-hero-text-on", "sb-hero-text-push");
    updateStatus("Artifact load fallback", true);
  };

  root.render(
    h(HeroCanvas, {
      stateRef: stageStateRef,
      phaseRef,
      quality,
      modelUrl,
      fallbackUrl,
      onModelReady,
      onLoadProgress,
      onLoadError,
    })
  );

  const handlePointerMove = (event) => {
    const rect = stage.getBoundingClientRect();
    const nx = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1;
    const ny = ((event.clientY - rect.top) / Math.max(rect.height, 1)) * 2 - 1;
    stageStateRef.current.pointerTarget.x = clamp(nx, -1, 1);
    stageStateRef.current.pointerTarget.y = clamp(ny, -1, 1);
  };

  const handlePointerLeave = () => {
    stageStateRef.current.pointerTarget.x = 0;
    stageStateRef.current.pointerTarget.y = 0;
  };

  const handleProgress = (event) => {
    const progress = event?.detail?.progress;
    if (Number.isFinite(progress)) {
      stageStateRef.current.progress = clamp(progress, 0, 1);
    }
  };

  const handleWorldProfile = (event) => {
    const detail = event?.detail || {};
    const nextSlug =
      typeof detail.slug === "string" && detail.slug.trim()
        ? detail.slug.trim().toLowerCase()
        : stageStateRef.current.worldSlug || DEFAULT_WORLD_SLUG;
    const motionProfile =
      detail.motionProfile && typeof detail.motionProfile === "object" ? detail.motionProfile : detail;
    stageStateRef.current.worldSlug = nextSlug;
    stageStateRef.current.worldProfile = normalizedWorldProfile(motionProfile, nextSlug);
  };

  stage.addEventListener("pointermove", handlePointerMove, { passive: true });
  stage.addEventListener("pointerleave", handlePointerLeave, { passive: true });
  stage.addEventListener("sb:home-progress", handleProgress);
  stage.addEventListener("sb:world-profile", handleWorldProfile);

  return {
    destroy() {
      if (disposed) {
        return;
      }
      disposed = true;
      stage.removeEventListener("pointermove", handlePointerMove);
      stage.removeEventListener("pointerleave", handlePointerLeave);
      stage.removeEventListener("sb:home-progress", handleProgress);
      stage.removeEventListener("sb:world-profile", handleWorldProfile);
      unsubs.forEach((unsubscribe) => unsubscribe?.());
      artifactXMV.destroy();
      artifactYMV.destroy();
      spinMV.destroy();
      breathMV.destroy();
      lightMV.destroy();
      uiShiftXMV.destroy();
      uiShiftYMV.destroy();
      uiDepthMV.destroy();
      uiTiltMV.destroy();
      root.unmount();
    },
    setProgress(value) {
      if (!Number.isFinite(value)) {
        return;
      }
      stageStateRef.current.progress = clamp(value, 0, 1);
    },
  };
}
