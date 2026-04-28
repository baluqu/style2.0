import * as THREE from "../vendor/three.module.min.js";
import { GLTFLoader } from "../vendor/GLTFLoader.js?v=20260331-emerald10";

const LOOK_PARAM = new URLSearchParams(window.location.search).get("look");
const LOOK_LIBRARY = {
    dress: {
        modelUrl: "/static/models/satin-slip-dress.glb?v=20260331-emerald10",
        posterUrl: "/static/images/satin-slip-poster.jpg?v=20260331-emerald10",
        materialSignals: {
            satin: "Material: Deep emerald liquid satin",
            matte: "Material: Black matte silk",
            pearl: "Material: Champagne pearl satin",
        },
        readyMetric: "Fallback dress active",
    },
    formal: {
        modelUrl: "/static/models/toji-reference.glb?v=20260402-toji1",
        posterUrl: "/static/img/toji-reference-poster.png?v=20260402-toji2",
        materialSignals: {
            satin: "Palette: Original import",
            matte: "Palette: Charcoal grade",
            pearl: "Palette: Sand grade",
        },
        readyMetric: "Reference model ready",
    },
};
const LOOK_ORDER = LOOK_PARAM === "dress" ? ["dress", "formal"] : ["formal", "dress"];
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const lowMemoryDevice = Boolean(navigator.deviceMemory && navigator.deviceMemory <= 2);
const DRESS_MESH_PREFIX = "Dress_";

const MATERIAL_PRESETS = {
    satin: {
        color: 0x187660,
        emissive: 0x000000,
        roughness: 0.09,
        metalness: 0.08,
        clearcoat: 1,
        clearcoatRoughness: 0.04,
        sheen: 0.92,
        sheenRoughness: 0.18,
        sheenColor: 0xe8fff7,
        signal: "Material: Deep emerald liquid satin",
    },
    matte: {
        color: 0x141416,
        emissive: 0x000000,
        roughness: 0.58,
        metalness: 0.03,
        clearcoat: 0.18,
        clearcoatRoughness: 0.52,
        sheen: 0.16,
        sheenRoughness: 0.72,
        sheenColor: 0xbcbcbc,
        signal: "Material: Black matte silk",
    },
    pearl: {
        color: 0xd9c097,
        emissive: 0x000000,
        roughness: 0.16,
        metalness: 0.05,
        clearcoat: 0.92,
        clearcoatRoughness: 0.11,
        sheen: 0.72,
        sheenRoughness: 0.24,
        sheenColor: 0xfff5ea,
        signal: "Material: Champagne pearl satin",
    },
};

const FORMAL_MATERIAL_PRESETS = {
    satin: {
        color: 0xffffff,
        emissive: 0x000000,
        roughness: 0.72,
        metalness: 0.02,
        clearcoat: 0.18,
        clearcoatRoughness: 0.44,
        sheen: 0.12,
        sheenRoughness: 0.58,
        sheenColor: 0xe9efe0,
        signal: "Palette: Original import",
        bodyTint: 0xb9b2a9,
        headTint: 0xf3e7d7,
        hairTint: 0x09090b,
        outfitColor: 0x15181f,
        accentColor: 0xb89d73,
        trimColor: 0x31394a,
    },
    matte: {
        color: 0x91979a,
        emissive: 0x000000,
        roughness: 0.84,
        metalness: 0.02,
        clearcoat: 0.08,
        clearcoatRoughness: 0.68,
        sheen: 0.06,
        sheenRoughness: 0.72,
        sheenColor: 0xd5d9dc,
        signal: "Palette: Charcoal grade",
        bodyTint: 0xa89d96,
        headTint: 0xe9d8cc,
        hairTint: 0x151313,
        outfitColor: 0x4a1016,
        accentColor: 0xd0b694,
        trimColor: 0x1d1115,
    },
    pearl: {
        color: 0xe8dcc3,
        emissive: 0x000000,
        roughness: 0.78,
        metalness: 0.02,
        clearcoat: 0.12,
        clearcoatRoughness: 0.48,
        sheen: 0.08,
        sheenRoughness: 0.6,
        sheenColor: 0xf7f0df,
        signal: "Palette: Sand grade",
        bodyTint: 0xd8cbb8,
        headTint: 0xf7efe3,
        hairTint: 0x2e231b,
        outfitColor: 0xe6dcc6,
        accentColor: 0x554637,
        trimColor: 0xbeac88,
    },
};

const LIGHTING_PRESETS = {
    studio: { background: 0x06101a, ambient: 0.9, key: 2.1, fill: 0.82, rim: 1.55 },
    day: { background: 0x0b1726, ambient: 1.04, key: 1.72, fill: 1.0, rim: 1.08 },
    evening: { background: 0x040912, ambient: 0.72, key: 1.38, fill: 0.62, rim: 1.68 },
};

const SIZE_PRESETS = {
    size2: {
        scale: 1,
        morphWeights: { size2: 1, size10: 0 },
        fitLabel: "Fit confidence: Size 2 close fit",
        bust: "Close through bust",
        waist: "Clean waist skim",
        drape: "8.7 / 10",
    },
    size6: {
        scale: 1,
        morphWeights: { size2: 0, size10: 0 },
        fitLabel: "Fit confidence: Size 6 balanced",
        bust: "Balanced contour",
        waist: "Bias cut settles",
        drape: "9.1 / 10",
    },
    size10: {
        scale: 1,
        morphWeights: { size2: 0, size10: 1 },
        fitLabel: "Fit confidence: Size 10 relaxed",
        bust: "Easy at bust",
        waist: "Relaxed through waist",
        drape: "8.8 / 10",
    },
};

const FORMAL_SIZE_PRESETS = {
    size2: {
        scale: 1,
        morphWeights: { size2: 1, size10: 0 },
        fitLabel: "Scale profile: Compact framing",
        bust: "Tighter crop",
        waist: "Closer stance",
        drape: "Lean silhouette",
    },
    size6: {
        scale: 1,
        morphWeights: { size2: 0, size10: 0 },
        fitLabel: "Scale profile: Balanced framing",
        bust: "Centered framing",
        waist: "Neutral stance",
        drape: "Balanced silhouette",
    },
    size10: {
        scale: 1,
        morphWeights: { size2: 0, size10: 1 },
        fitLabel: "Scale profile: Hero framing",
        bust: "Broader presence",
        waist: "Bolder stance",
        drape: "Expanded silhouette",
    },
};

const CAMERA_PRESETS = {
    hero: { position: [0.18, 0.34, 4.05], lookAt: [0, -0.06, 0], minHeight: 460 },
    fit: { position: [0.12, 0.3, 3.7], lookAt: [0, -0.08, 0], minHeight: 420 },
    studio: { position: [0.34, 0.34, 3.95], lookAt: [0, -0.05, 0], minHeight: 440 },
};

const FORMAL_CAMERA_PRESETS = {
    hero: { position: [0.0, 0.14, 3.6], lookAt: [0, -0.22, 0], minHeight: 500 },
    fit: { position: [0.0, 0.12, 3.45], lookAt: [0, -0.22, 0], minHeight: 440 },
    studio: { position: [0.04, 0.16, 3.72], lookAt: [0, -0.2, 0], minHeight: 450 },
};

const QUALITY_PROFILES = {
    high: { maxDpr: 1.6, antialias: true },
    medium: { maxDpr: 1.25, antialias: true },
    low: { maxDpr: 1, antialias: false },
};


function supportsWebGL() {
    try {
        const canvas = document.createElement("canvas");
        return Boolean(
            window.WebGLRenderingContext &&
            (canvas.getContext("webgl2") || canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
        );
    } catch {
        return false;
    }
}


function setButtonState(button, active) {
    button.classList.toggle("bg-white/10", active);
    button.classList.toggle("border-white/15", active);
    button.classList.toggle("text-white", active);
    button.classList.toggle("bg-white/5", !active);
    button.classList.toggle("border-white/10", !active);
    button.classList.toggle("text-slate-300", !active);
}


function chooseQualityProfile() {
    if (prefersReducedMotion || lowMemoryDevice) {
        return QUALITY_PROFILES.low;
    }
    if (window.innerWidth < 900) {
        return QUALITY_PROFILES.medium;
    }
    return QUALITY_PROFILES.high;
}


function isDressMesh(mesh) {
    return (mesh.name || "").startsWith(DRESS_MESH_PREFIX);
}


function createPhysicalMaterial(sourceMaterial) {
    const material = new THREE.MeshPhysicalMaterial({
        color: sourceMaterial?.color?.clone?.() || new THREE.Color(0xffffff),
        map: sourceMaterial?.map || null,
        normalMap: sourceMaterial?.normalMap || null,
        roughnessMap: sourceMaterial?.roughnessMap || null,
        metalnessMap: sourceMaterial?.metalnessMap || null,
        alphaMap: sourceMaterial?.alphaMap || null,
        transparent: Boolean(sourceMaterial?.transparent),
        alphaTest: sourceMaterial?.alphaTest ?? 0,
        side: THREE.DoubleSide,
        roughness: sourceMaterial?.roughness ?? 0.18,
        metalness: sourceMaterial?.metalness ?? 0.05,
    });

    if (sourceMaterial?.emissive) {
        material.emissive.copy(sourceMaterial.emissive);
        material.emissiveIntensity = sourceMaterial.emissiveIntensity ?? 1;
    }
    if ("clearcoat" in material) {
        material.clearcoat = 0.85;
        material.clearcoatRoughness = 0.08;
        material.sheen = 0.75;
        material.sheenRoughness = 0.2;
        material.sheenColor = new THREE.Color(0xf5fff9);
    }
    material.needsUpdate = true;
    return material;
}


function cloneImportedMaterial(sourceMaterial) {
    const material = sourceMaterial?.clone?.() || new THREE.MeshStandardMaterial({ color: 0xffffff });
    if (material.map) {
        material.map.colorSpace = THREE.SRGBColorSpace;
    }
    material.side = THREE.DoubleSide;
    material.alphaTest = Math.max(material.alphaTest ?? 0, 0.32);
    material.transparent = material.alphaTest > 0 || Boolean(material.transparent);
    material.needsUpdate = true;
    return material;
}


function loadTexture(textureLoader, url) {
    return new Promise((resolve, reject) => {
        textureLoader.load(url, resolve, undefined, reject);
    });
}


function captureBaseTransform(node) {
    node.userData.basePosition = node.position.clone();
    node.userData.baseRotation = node.rotation.clone();
    node.userData.baseScale = node.scale.clone();
}


function resetToBaseTransform(node) {
    if (node.userData.basePosition) {
        node.position.copy(node.userData.basePosition);
    }
    if (node.userData.baseRotation) {
        node.rotation.copy(node.userData.baseRotation);
    }
    if (node.userData.baseScale) {
        node.scale.copy(node.userData.baseScale);
    }
}


function getFormalMeshRole(mesh) {
    const materialName = String(mesh.material?.name || "").toLowerCase();
    const meshName = String(mesh.name || "").toLowerCase();
    const label = `${materialName} ${meshName}`;

    if (label.includes("hair")) {
        return "hair";
    }
    if (materialName === "head" || (label.includes("head") && !label.includes("body"))) {
        return "head";
    }
    return "body";
}


class RunwayScene {
    constructor(canvas, variant) {
        this.canvas = canvas;
        this.variant = variant;
        this.stage = canvas.closest("[data-scene-stage]");
        this.metricEl = document.querySelector(`[data-scene-metric-for="${canvas.id}"]`);
        this.fitEl = document.querySelector(`[data-fit-signal-for="${canvas.id}"]`);
        this.materialEl = document.querySelector(`[data-material-signal-for="${canvas.id}"]`);
        this.bustDetailEl = document.querySelector(`[data-fit-bust-for="${canvas.id}"]`);
        this.waistDetailEl = document.querySelector(`[data-fit-waist-for="${canvas.id}"]`);
        this.drapeDetailEl = document.querySelector(`[data-fit-drape-for="${canvas.id}"]`);
        this.loadingEl = this.stage?.querySelector("[data-scene-loading]");
        this.progressEl = this.stage?.querySelector("[data-scene-progress]");
        this.posterEl = this.stage?.querySelector(".scene-poster");
        this.profile = chooseQualityProfile();
        this.pointer = { x: 0, y: 0 };
        this.clock = new THREE.Clock();
        this.loader = new GLTFLoader();
        this.textureLoader = new THREE.TextureLoader();
        this.running = false;
        this.isVisible = false;
        this.loaded = false;
        this.rafId = 0;
        this.frameCount = 0;
        this.fpsWindowStart = performance.now();
        this.motionMode = variant === "fit" ? "idle" : "catwalk";
        this.materialMode = "satin";
        this.lightingMode = variant === "fit" ? "evening" : "studio";
        this.sizeMode = "size6";
        this.viewMode = "rendered";
        this.meshes = [];
        this.dressMeshes = [];
        this.animationClips = [];
        this.mixer = null;
        this.walkAction = null;
        this.formalCutout = null;
        this.formalRigNodes = null;
        this.formalOutfit = null;
        this.formalOutfitNodes = null;
        this.formalPartMeshes = { body: null, head: null, hair: null };
        this.elapsedTime = 0;
        this.lookOrder = [...LOOK_ORDER];
        this.loadAttemptIndex = 0;
        this.activeLook = this.lookOrder[0];

        this.setup();
    }

    setup() {
        const preset = this.getCameraPreset();
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
        this.camera.position.set(...preset.position);

        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: this.profile.antialias,
            alpha: true,
            powerPreference: "high-performance",
        });
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.04;
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.profile.maxDpr));
        this.renderer.setClearAlpha(0);

        this.modelPivot = new THREE.Group();
        this.modelScaleGroup = new THREE.Group();
        this.modelPivot.add(this.modelScaleGroup);
        this.scene.add(this.modelPivot);

        this.createEnvironment();
        this.bindEvents();
        this.resize();
        this.loadModel();
    }

    createEnvironment() {
        this.backdrop = new THREE.Mesh(
            new THREE.PlaneGeometry(14, 9),
            new THREE.MeshBasicMaterial({ color: 0x07111f, transparent: true, opacity: 0.56 })
        );
        this.backdrop.position.set(0, 0.2, -5.2);
        this.scene.add(this.backdrop);

        this.halo = new THREE.Mesh(
            new THREE.CircleGeometry(1.75, 48),
            new THREE.MeshBasicMaterial({ color: 0x23dbff, transparent: true, opacity: 0.09 })
        );
        this.halo.position.set(0, 0.35, -4.85);
        this.scene.add(this.halo);

        this.sideGlow = new THREE.Mesh(
            new THREE.CircleGeometry(1.05, 40),
            new THREE.MeshBasicMaterial({ color: 0xffd49a, transparent: true, opacity: 0.05 })
        );
        this.sideGlow.scale.set(1.6, 0.95, 1);
        this.sideGlow.position.set(1.02, -0.12, -4.8);
        this.scene.add(this.sideGlow);

        this.floor = new THREE.Mesh(
            new THREE.CircleGeometry(1.95, 64),
            new THREE.MeshPhysicalMaterial({
                color: 0x0a1018,
                roughness: 0.3,
                metalness: 0.14,
                clearcoat: 0.8,
                clearcoatRoughness: 0.16,
            })
        );
        this.floor.rotation.x = -Math.PI / 2;
        this.floor.position.y = -1.48;
        this.scene.add(this.floor);

        this.runwayRing = new THREE.Mesh(
            new THREE.TorusGeometry(1.75, 0.022, 12, 96),
            new THREE.MeshBasicMaterial({ color: 0x6ef1ff, transparent: true, opacity: 0.58 })
        );
        this.runwayRing.rotation.x = Math.PI / 2;
        this.runwayRing.position.y = -1.45;
        this.scene.add(this.runwayRing);

        this.ambientLight = new THREE.AmbientLight(0xf1f7ff, 0.9);
        this.keyLight = new THREE.DirectionalLight(0xc8f6ff, 2.1);
        this.keyLight.position.set(2.2, 3.4, 2.6);
        this.fillLight = new THREE.DirectionalLight(0x5ecbff, 0.82);
        this.fillLight.position.set(-2.8, 1.45, 2.2);
        this.rimLight = new THREE.DirectionalLight(0xffd39b, 1.55);
        this.rimLight.position.set(0.65, 2.5, -3.0);
        this.scene.add(this.ambientLight, this.keyLight, this.fillLight, this.rimLight);
    }

    bindEvents() {
        this.handleResize = () => this.resize();
        this.handlePointerMove = (event) => {
            const bounds = this.canvas.getBoundingClientRect();
            const x = (event.clientX - bounds.left) / Math.max(bounds.width, 1);
            const y = (event.clientY - bounds.top) / Math.max(bounds.height, 1);
            this.pointer.x = (x - 0.5) * 2;
            this.pointer.y = (y - 0.5) * 2;
        };
        this.handlePointerLeave = () => {
            this.pointer.x = 0;
            this.pointer.y = 0;
        };

        window.addEventListener("resize", this.handleResize);
        this.canvas.addEventListener("pointermove", this.handlePointerMove);
        this.canvas.addEventListener("pointerleave", this.handlePointerLeave);
    }

    resize() {
        const width = this.canvas.clientWidth || this.canvas.parentElement?.clientWidth || 800;
        const preset = this.getCameraPreset();
        const height = this.canvas.clientHeight || preset.minHeight;
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.profile.maxDpr));
        this.renderer.setSize(width, height, false);
        this.camera.aspect = width / Math.max(height, 1);
        this.camera.updateProjectionMatrix();
    }

    loadModel() {
        if (this.metricEl) {
            this.metricEl.textContent = "Loading GLB...";
        }
        this.updateProgress(0);
        this.loadAttemptIndex = 0;
        this.loadLook(this.lookOrder[this.loadAttemptIndex]);
    }

    getLookConfig(lookKey) {
        return LOOK_LIBRARY[lookKey] || LOOK_LIBRARY.dress;
    }

    getCameraPreset() {
        const presetTable = this.activeLook === "formal" ? FORMAL_CAMERA_PRESETS : CAMERA_PRESETS;
        return presetTable[this.variant] || presetTable.hero;
    }

    getBaseYaw() {
        if (this.activeLook === "formal") {
            return this.variant === "studio" ? 0.05 : this.variant === "hero" ? 0.025 : 0.018;
        }
        return this.variant === "studio" ? 0.3 : this.variant === "hero" ? 0.22 : 0.16;
    }

    getSizePreset(mode) {
        const presetTable = this.activeLook === "formal" ? FORMAL_SIZE_PRESETS : SIZE_PRESETS;
        return presetTable[mode] || presetTable.size6;
    }

    setPosterForLook(lookKey) {
        if (this.posterEl) {
            this.posterEl.src = this.getLookConfig(lookKey).posterUrl;
        }
    }

    loadLook(lookKey) {
        const look = this.getLookConfig(lookKey);
        this.setPosterForLook(lookKey);

        if (lookKey === "formal" && look.metadataUrl) {
            this.loadFormalReferenceLook(lookKey, look);
            return;
        }

        this.loader.load(
            look.modelUrl,
            (gltf) => this.handleLoad(gltf, lookKey),
            (progress) => {
                const total = progress.total || progress.loaded || 1;
                const percent = Math.max(0, Math.min(100, Math.round((progress.loaded / total) * 100)));
                this.updateProgress(percent);
            },
            (error) => this.handleLookError(error, lookKey)
        );
    }

    async loadFormalReferenceLook(lookKey, look) {
        try {
            const response = await fetch(look.metadataUrl, { cache: "no-store" });
            if (!response.ok) {
                throw new Error(`Failed to load formal metadata (${response.status})`);
            }
            const metadata = await response.json();
            const model = metadata.asset_mode === "rig" && Array.isArray(metadata.segments_data)
                ? await this.buildFormalRig(metadata)
                : await this.buildFormalCutout(metadata);

            this.activeLook = lookKey;
            this.model = model;
            this.animationClips = [];
            this.normalizeModel(this.model, lookKey);
            this.collectMeshes(this.model);
            this.setupAnimation();
            this.modelScaleGroup.add(this.model);
            this.modelPivot.position.y = -1.6;
            this.loaded = true;
            this.applyMaterial(this.materialMode);
            this.applyLighting(this.lightingMode);
            this.applySize(this.sizeMode);
            this.setViewMode(this.viewMode);
            this.stage?.classList.remove("scene-poster-only");
            this.stage?.classList.add("scene-ready");
            this.updateProgress(100);
            if (this.metricEl) {
                this.metricEl.textContent = this.getLookConfig(lookKey).readyMetric || "Starting render...";
            }
            if (this.isVisible) {
                this.start();
            }
        } catch (error) {
            this.handleLookError(error, lookKey);
        }
    }

    async buildFormalCutout(metadata) {
        const textureUrl = `/static/images/${metadata.cutout_image}?v=20260331-emerald10`;
        const texture = await loadTexture(this.textureLoader, textureUrl);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());

        const planeWidth = metadata.cutout_plane_width || 1.05;
        const planeHeight = metadata.cutout_plane_height || 2.82;
        const front = new THREE.Mesh(
            new THREE.PlaneGeometry(planeWidth, planeHeight),
            new THREE.MeshBasicMaterial({
                map: texture,
                transparent: true,
                alphaTest: 0.18,
                color: 0xffffff,
                side: THREE.DoubleSide,
                toneMapped: false,
            })
        );
        front.name = "Formal_Cutout";

        const shadow = new THREE.Mesh(
            new THREE.PlaneGeometry(planeWidth * 1.03, planeHeight * 1.01),
            new THREE.MeshBasicMaterial({
                map: texture,
                transparent: true,
                alphaTest: 0.18,
                color: 0x09111a,
                opacity: 0.16,
                side: THREE.DoubleSide,
                toneMapped: false,
            })
        );
        shadow.position.set(0.02, -0.01, -0.045);
        shadow.name = "Formal_Shadow";

        const model = new THREE.Group();
        model.add(shadow, front);
        model.userData.cutoutMesh = front;
        this.formalCutout = front;
        this.formalRigNodes = null;
        return model;
    }

    async buildFormalRig(metadata) {
        const baseTexture = await loadTexture(this.textureLoader, `/static/images/${metadata.cutout_image}?v=20260331-emerald10`);
        baseTexture.colorSpace = THREE.SRGBColorSpace;
        baseTexture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());

        const baseMesh = new THREE.Mesh(
            new THREE.PlaneGeometry(metadata.cutout_plane_width || 1.05, metadata.cutout_plane_height || 2.82),
            new THREE.MeshBasicMaterial({
                map: baseTexture,
                transparent: true,
                alphaTest: 0.18,
                color: 0xffffff,
                side: THREE.DoubleSide,
                toneMapped: false,
            })
        );
        baseMesh.name = "Formal_Base";
        baseMesh.position.z = -0.03;
        baseMesh.renderOrder = 0;

        const entries = await Promise.all(
            metadata.segments_data.map(async (segment, index) => {
                const texture = await loadTexture(this.textureLoader, `/static/images/${segment.image}?v=20260331-emerald10`);
                texture.colorSpace = THREE.SRGBColorSpace;
                texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
                const geometry = new THREE.PlaneGeometry(segment.plane_width, segment.plane_height);
                const material = new THREE.MeshBasicMaterial({
                    map: texture,
                    transparent: true,
                    alphaTest: 0.14,
                    color: 0xffffff,
                    side: THREE.DoubleSide,
                    toneMapped: false,
                });
                const mesh = new THREE.Mesh(geometry, material);
                mesh.name = segment.name;
                mesh.position.fromArray(segment.position);
                mesh.renderOrder = index + 1;
                return [segment.name, mesh];
            })
        );

        const model = new THREE.Group();
        model.add(baseMesh);
        this.formalRigNodes = Object.fromEntries(entries);

        Object.values(this.formalRigNodes).forEach((mesh) => {
            mesh.userData.basePosition = mesh.position.clone();
            model.add(mesh);
        });

        this.formalCutout = baseMesh;
        return model;
    }

    setupAnimation() {
        if (!this.animationClips.length || !this.model) {
            return;
        }

        this.mixer = new THREE.AnimationMixer(this.model);
        const walkClip = this.animationClips.find((clip) => /runway|walk/i.test(clip.name)) || this.animationClips[0];
        this.walkAction = this.mixer.clipAction(walkClip);
        this.walkAction.enabled = true;
        this.walkAction.clampWhenFinished = false;
        this.walkAction.play();
        this.syncMotionMode();
    }

    syncMotionMode() {
        if (!this.walkAction) {
            return;
        }

        if (this.motionMode === "idle") {
            this.walkAction.paused = true;
            this.walkAction.time = 0;
            this.mixer?.setTime?.(0);
        } else if (this.motionMode === "wind") {
            this.walkAction.paused = false;
            this.walkAction.timeScale = 0.88;
        } else {
            this.walkAction.paused = false;
            this.walkAction.timeScale = 1;
        }
    }

    handleLoad(gltf, lookKey) {
        this.activeLook = lookKey;
        this.model = gltf.scene.clone(true);
        this.animationClips = gltf.animations || [];
        this.normalizeModel(this.model, lookKey);
        this.collectMeshes(this.model);
        this.setupAnimation();
        this.modelScaleGroup.add(this.model);
        this.modelPivot.position.y = lookKey === "formal" ? -1.54 : -1.48;
        this.loaded = true;
        this.applyMaterial(this.materialMode);
        this.applyLighting(this.lightingMode);
        this.applySize(this.sizeMode);
        this.setViewMode(this.viewMode);
        this.stage?.classList.remove("scene-poster-only");
        this.stage?.classList.add("scene-ready");
        this.updateProgress(100);
        if (this.metricEl) {
            this.metricEl.textContent = this.getLookConfig(lookKey).readyMetric || "Starting render...";
        }
        if (this.isVisible) {
            this.start();
        }
    }

    normalizeModel(model, lookKey = this.activeLook) {
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        model.position.sub(center);
        const targetHeight = lookKey === "formal"
            ? (this.variant === "hero" ? 2.78 : 2.66)
            : (this.variant === "hero" ? 2.85 : 2.7);
        const scale = targetHeight / Math.max(size.y, 0.001);
        model.scale.setScalar(scale);
        const scaledBox = new THREE.Box3().setFromObject(model);
        model.position.y -= scaledBox.min.y;
        model.position.z = 0;
        if (lookKey === "formal") {
            model.position.y -= 0.03;
        }
    }

    collectMeshes(root) {
        this.meshes = [];
        this.dressMeshes = [];
        this.formalPartMeshes = { body: null, head: null, hair: null };
        const preserveImportedMaterial = this.activeLook === "formal";
        root.traverse((child) => {
            if (!child.isMesh) {
                return;
            }
            child.castShadow = false;
            child.receiveShadow = false;
            child.material = preserveImportedMaterial
                ? cloneImportedMaterial(child.material)
                : createPhysicalMaterial(child.material);
            child.userData.originalMaterial = {
                color: child.material.color.clone(),
                emissive: child.material.emissive?.clone?.() || new THREE.Color(0x000000),
                roughness: child.material.roughness ?? 0.8,
                metalness: child.material.metalness ?? 0,
            };
            captureBaseTransform(child);
            if (this.activeLook === "formal") {
                const role = getFormalMeshRole(child);
                child.userData.formalRole = role;
                if (!this.formalPartMeshes[role]) {
                    this.formalPartMeshes[role] = child;
                }
            }
            if (isDressMesh(child)) {
                this.dressMeshes.push(child);
            }
            this.meshes.push(child);
        });
    }

    setupFormalOutfit() {
        if (this.activeLook !== "formal" || this.formalRigNodes || !this.model) {
            return;
        }

        if (this.formalOutfit) {
            this.formalOutfit.removeFromParent();
        }

        const box = new THREE.Box3().setFromObject(this.model);
        const size = box.getSize(new THREE.Vector3());
        const min = box.min.clone();

        const torsoHeight = size.y * 0.36;
        const torsoY = min.y + size.y * 0.59;
        const torsoRadiusTop = Math.max(size.x * 0.18, 0.15);
        const torsoRadiusBottom = Math.max(size.x * 0.24, 0.2);
        const depthOffset = Math.max(size.z * 0.12, 0.08);

        const createFabricMaterial = () => new THREE.MeshPhysicalMaterial({
            color: 0x15181f,
            roughness: 0.82,
            metalness: 0.05,
            clearcoat: 0.18,
            clearcoatRoughness: 0.5,
            side: THREE.DoubleSide,
        });
        const createAccentMaterial = () => new THREE.MeshPhysicalMaterial({
            color: 0xb89d73,
            roughness: 0.48,
            metalness: 0.16,
            clearcoat: 0.32,
            clearcoatRoughness: 0.22,
            side: THREE.DoubleSide,
        });

        const group = new THREE.Group();
        group.name = "Formal_Outfit";

        const coatBody = new THREE.Mesh(
            new THREE.CylinderGeometry(torsoRadiusTop, torsoRadiusBottom, torsoHeight, 32, 1, true, Math.PI * 0.18, Math.PI * 1.64),
            createFabricMaterial()
        );
        coatBody.position.set(0, torsoY, 0);
        coatBody.rotation.y = Math.PI / 2;
        coatBody.renderOrder = 5;

        const panelWidth = size.x * 0.21;
        const panelHeight = torsoHeight * 0.98;
        const leftPanel = new THREE.Mesh(
            new THREE.PlaneGeometry(panelWidth, panelHeight),
            createFabricMaterial()
        );
        leftPanel.position.set(-size.x * 0.11, torsoY - torsoHeight * 0.02, depthOffset);
        leftPanel.rotation.y = Math.PI * 0.1;
        leftPanel.renderOrder = 6;

        const rightPanel = leftPanel.clone();
        rightPanel.material = createFabricMaterial();
        rightPanel.position.x *= -1;
        rightPanel.rotation.y *= -1;

        const sash = new THREE.Mesh(
            new THREE.TorusGeometry(size.x * 0.16, size.y * 0.012, 14, 60),
            createAccentMaterial()
        );
        sash.position.set(0, min.y + size.y * 0.46, depthOffset * 0.22);
        sash.rotation.x = Math.PI / 2;
        sash.renderOrder = 7;

        const legHeight = size.y * 0.34;
        const legRadius = Math.max(size.x * 0.08, 0.08);
        const leftLeg = new THREE.Mesh(
            new THREE.CylinderGeometry(legRadius * 0.82, legRadius, legHeight, 20, 1, true),
            createFabricMaterial()
        );
        leftLeg.position.set(-size.x * 0.1, min.y + size.y * 0.24, 0.01);
        leftLeg.renderOrder = 5;

        const rightLeg = leftLeg.clone();
        rightLeg.material = createFabricMaterial();
        rightLeg.position.x *= -1;

        const leftBoot = new THREE.Mesh(
            new THREE.BoxGeometry(size.x * 0.14, size.y * 0.06, Math.max(size.z * 0.48, 0.22)),
            createAccentMaterial()
        );
        leftBoot.position.set(-size.x * 0.11, min.y + size.y * 0.03, size.z * 0.08);
        leftBoot.rotation.x = Math.PI * 0.03;
        leftBoot.renderOrder = 7;

        const rightBoot = leftBoot.clone();
        rightBoot.material = createAccentMaterial();
        rightBoot.position.x *= -1;

        const collar = new THREE.Mesh(
            new THREE.TorusGeometry(size.x * 0.12, size.y * 0.01, 10, 40, Math.PI),
            createAccentMaterial()
        );
        collar.position.set(0, min.y + size.y * 0.71, depthOffset * 0.12);
        collar.rotation.z = Math.PI;
        collar.renderOrder = 7;

        group.add(coatBody, leftPanel, rightPanel, sash, leftLeg, rightLeg, leftBoot, rightBoot, collar);
        group.traverse((child) => {
            if (!child.isMesh) {
                return;
            }
            captureBaseTransform(child);
            child.castShadow = false;
            child.receiveShadow = false;
        });

        this.formalOutfit = group;
        this.formalOutfitNodes = {
            coatBody,
            leftPanel,
            rightPanel,
            sash,
            leftLeg,
            rightLeg,
            leftBoot,
            rightBoot,
            collar,
        };
        this.model.add(group);
    }

    applyFormalOutfitMaterial(preset) {
        if (!this.formalOutfitNodes) {
            return;
        }

        const applyToNode = (node, color, roughness = 0.72, metalness = 0.08, clearcoat = 0.18) => {
            if (!node?.material) {
                return;
            }
            node.material.color.setHex(color);
            if ("roughness" in node.material) {
                node.material.roughness = roughness;
            }
            if ("metalness" in node.material) {
                node.material.metalness = metalness;
            }
            if ("clearcoat" in node.material) {
                node.material.clearcoat = clearcoat;
                node.material.clearcoatRoughness = 0.34;
            }
            node.material.wireframe = this.viewMode === "wireframe";
            node.material.needsUpdate = true;
        };

        applyToNode(this.formalOutfitNodes.coatBody, preset.outfitColor, 0.76, 0.06, 0.16);
        applyToNode(this.formalOutfitNodes.leftPanel, preset.outfitColor, 0.72, 0.06, 0.14);
        applyToNode(this.formalOutfitNodes.rightPanel, preset.outfitColor, 0.72, 0.06, 0.14);
        applyToNode(this.formalOutfitNodes.leftLeg, preset.trimColor, 0.84, 0.04, 0.08);
        applyToNode(this.formalOutfitNodes.rightLeg, preset.trimColor, 0.84, 0.04, 0.08);
        applyToNode(this.formalOutfitNodes.leftBoot, preset.accentColor, 0.46, 0.18, 0.28);
        applyToNode(this.formalOutfitNodes.rightBoot, preset.accentColor, 0.46, 0.18, 0.28);
        applyToNode(this.formalOutfitNodes.sash, preset.accentColor, 0.4, 0.14, 0.34);
        applyToNode(this.formalOutfitNodes.collar, preset.accentColor, 0.42, 0.16, 0.32);
    }

    applyMaterial(mode) {
        const presetTable = this.activeLook === "formal" ? FORMAL_MATERIAL_PRESETS : MATERIAL_PRESETS;
        const preset = presetTable[mode] || presetTable.satin;
        const signal = this.getLookConfig(this.activeLook).materialSignals?.[mode] || preset.signal;
        this.materialMode = mode;
        const targetMeshes = this.activeLook === "formal" ? this.meshes : this.dressMeshes;
        targetMeshes.forEach((mesh) => {
            const material = mesh.material;
            const original = mesh.userData.originalMaterial;
            if (this.activeLook === "formal") {
                material.color.copy(original?.color || new THREE.Color(0xffffff));
                material.color.multiply(new THREE.Color(preset.color));
            } else {
                material.color.setHex(preset.color);
            }
            if (material.emissive) {
                material.emissive.setHex(preset.emissive);
            }
            if ("roughness" in material) {
                material.roughness = preset.roughness;
            }
            if ("metalness" in material) {
                material.metalness = preset.metalness;
            }
            if ("clearcoat" in material) {
                material.clearcoat = preset.clearcoat;
                material.clearcoatRoughness = preset.clearcoatRoughness;
                material.sheen = preset.sheen;
                material.sheenRoughness = preset.sheenRoughness;
                material.sheenColor = new THREE.Color(preset.sheenColor);
            }
            material.wireframe = this.viewMode === "wireframe";
            material.needsUpdate = true;
        });
        if (this.materialEl) {
            this.materialEl.textContent = signal;
        }
    }

    applyLighting(mode) {
        const preset = LIGHTING_PRESETS[mode] || LIGHTING_PRESETS.studio;
        this.lightingMode = mode;
        this.backdrop.material.color.setHex(preset.background);
        this.ambientLight.intensity = preset.ambient;
        this.keyLight.intensity = preset.key;
        this.fillLight.intensity = preset.fill;
        this.rimLight.intensity = preset.rim;
    }

    applySize(mode) {
        const preset = this.getSizePreset(mode);
        this.sizeMode = mode;
        let morphDriven = false;
        this.meshes.forEach((mesh) => {
            if (!mesh.morphTargetInfluences?.length || !mesh.morphTargetDictionary) {
                return;
            }

            const influences = mesh.morphTargetInfluences;
            influences.fill(0);
            const size2Index = mesh.morphTargetDictionary.size2;
            const size10Index = mesh.morphTargetDictionary.size10;
            if (size2Index !== undefined) {
                morphDriven = true;
                influences[size2Index] = preset.morphWeights?.size2 ?? 0;
            }
            if (size10Index !== undefined) {
                morphDriven = true;
                influences[size10Index] = preset.morphWeights?.size10 ?? 0;
            }
        });
        const formalScale = mode === "size2" ? 0.975 : mode === "size10" ? 1.045 : 1;
        this.modelScaleGroup.scale.setScalar(preset.scale * (!morphDriven && this.activeLook === "formal" ? formalScale : 1));
        if (this.fitEl) {
            this.fitEl.textContent = preset.fitLabel;
        }
        if (this.bustDetailEl) {
            this.bustDetailEl.textContent = preset.bust;
        }
        if (this.waistDetailEl) {
            this.waistDetailEl.textContent = preset.waist;
        }
        if (this.drapeDetailEl) {
            this.drapeDetailEl.textContent = preset.drape;
        }
    }

    setViewMode(mode) {
        this.viewMode = mode;
        this.meshes.forEach((mesh) => {
            mesh.material.wireframe = mode === "wireframe";
            mesh.material.needsUpdate = true;
        });
    }

    setMotionMode(mode) {
        this.motionMode = mode;
        this.syncMotionMode();
    }

    updateFormalRig(t) {
        if (!this.formalRigNodes) {
            return;
        }

        const cycle = (t % 10) / 10;
        const phase = cycle * Math.PI * 2;
        const stride = Math.sin(phase);
        const opposing = Math.sin(phase + Math.PI);
        const bounce = Math.sin(phase * 2);
        const settle = Math.sin(phase + Math.PI / 3);
        const motionScale = this.motionMode === "idle" ? 0.35 : this.motionMode === "wind" ? 0.7 : 1;

        const setRotation = (name, x, y, z) => {
            const node = this.formalRigNodes[name];
            if (!node) {
                return;
            }
            node.rotation.set(x, y, z);
        };

        const setYOffset = (name, value) => {
            const node = this.formalRigNodes[name];
            if (!node?.userData?.basePosition) {
                return;
            }
            node.position.copy(node.userData.basePosition);
            node.position.y += value;
        };

        setRotation("Head", 0.002 * bounce * motionScale, 0.004 * settle * motionScale, -0.002 * bounce * motionScale);
        setRotation("Torso", -0.005 * bounce * motionScale, -0.006 * settle * motionScale, -0.004 * settle * motionScale);
        setRotation("Hip", 0.004 * bounce * motionScale, 0.0, -0.006 * settle * motionScale);
        setRotation("LeftArm", -0.028 * opposing * motionScale, 0.0, 0.01 * settle * motionScale);
        setRotation("RightArm", -0.028 * stride * motionScale, 0.0, -0.01 * settle * motionScale);
        setRotation("LeftUpperLeg", 0.024 * stride * motionScale, 0.0, 0.005 * settle * motionScale);
        setRotation("RightUpperLeg", 0.024 * opposing * motionScale, 0.0, -0.005 * settle * motionScale);
        setRotation("LeftLowerLeg", -0.018 * Math.max(0, opposing) * motionScale, 0.0, 0.0);
        setRotation("RightLowerLeg", -0.018 * Math.max(0, stride) * motionScale, 0.0, 0.0);
        setRotation("LeftFoot", -0.012 * Math.max(0, stride) * motionScale, 0.0, 0.0);
        setRotation("RightFoot", -0.012 * Math.max(0, opposing) * motionScale, 0.0, 0.0);

        setYOffset("Head", 0.004 * Math.abs(bounce) * motionScale);
        setYOffset("Torso", 0.006 * Math.abs(bounce) * motionScale);
        setYOffset("Hip", 0.008 * Math.abs(bounce) * motionScale);
        setYOffset("LeftArm", 0.006 * Math.abs(bounce) * motionScale);
        setYOffset("RightArm", 0.006 * Math.abs(bounce) * motionScale);
        setYOffset("LeftUpperLeg", 0.004 * Math.abs(bounce) * motionScale);
        setYOffset("RightUpperLeg", 0.004 * Math.abs(bounce) * motionScale);
        setYOffset("LeftLowerLeg", 0.003 * Math.abs(bounce) * motionScale);
        setYOffset("RightLowerLeg", 0.003 * Math.abs(bounce) * motionScale);
        setYOffset("LeftFoot", 0.002 * Math.abs(bounce) * motionScale);
        setYOffset("RightFoot", 0.002 * Math.abs(bounce) * motionScale);
    }

    updateFormalLookMotion(t) {
        if (this.formalRigNodes) {
            this.updateFormalRig(t);
            return;
        }

        const body = this.formalPartMeshes.body;
        const head = this.formalPartMeshes.head;
        const hair = this.formalPartMeshes.hair;
        [body, head, hair].forEach((node) => node && resetToBaseTransform(node));

        if (this.formalOutfitNodes) {
            Object.values(this.formalOutfitNodes).forEach((node) => node && resetToBaseTransform(node));
        }

        const pace = this.motionMode === "catwalk" ? 1.75 : this.motionMode === "wind" ? 1.05 : 0.62;
        const stride = Math.sin(t * pace);
        const bounce = Math.sin(t * pace * 2);
        const settle = Math.sin(t * 0.84 + Math.PI / 5);
        const motionScale = this.motionMode === "catwalk" ? 1 : this.motionMode === "wind" ? 0.78 : 0.42;

        if (body) {
            body.position.y += Math.abs(bounce) * 0.012 * motionScale;
            body.rotation.y += stride * 0.038 * motionScale;
            body.rotation.z += settle * 0.022 * motionScale;
        }

        if (head) {
            head.rotation.y += settle * 0.09 * motionScale;
            head.rotation.x += bounce * 0.018 * motionScale;
            head.position.y += Math.abs(bounce) * 0.008 * motionScale;
        }

        if (hair) {
            hair.rotation.z += settle * 0.12 * motionScale;
            hair.rotation.x += bounce * 0.035 * motionScale;
        }

        if (!this.formalOutfitNodes) {
            return;
        }

        const {
            coatBody,
            leftPanel,
            rightPanel,
            sash,
            leftLeg,
            rightLeg,
            leftBoot,
            rightBoot,
            collar,
        } = this.formalOutfitNodes;

        coatBody.rotation.z += settle * 0.03 * motionScale;
        leftPanel.rotation.y += stride * 0.14 * motionScale;
        leftPanel.rotation.z += settle * 0.04 * motionScale;
        rightPanel.rotation.y -= stride * 0.14 * motionScale;
        rightPanel.rotation.z -= settle * 0.04 * motionScale;
        sash.rotation.z += stride * 0.06 * motionScale;
        leftLeg.rotation.x += Math.max(0, stride) * 0.08 * motionScale;
        rightLeg.rotation.x += Math.max(0, -stride) * 0.08 * motionScale;
        leftBoot.rotation.x += Math.max(0, stride) * 0.04 * motionScale;
        rightBoot.rotation.x += Math.max(0, -stride) * 0.04 * motionScale;
        collar.rotation.z += settle * 0.05 * motionScale;

        if (this.motionMode === "wind") {
            coatBody.rotation.y += 0.08;
            leftPanel.rotation.y += 0.22;
            rightPanel.rotation.y += 0.05;
            sash.position.x += Math.sin(t * 1.8) * 0.028;
            collar.rotation.x += 0.14;
        } else if (this.motionMode === "idle") {
            coatBody.rotation.y -= 0.03;
            leftPanel.rotation.y += 0.03;
            rightPanel.rotation.y -= 0.03;
            sash.position.y += Math.sin(t * 1.1) * 0.01;
        }
    }

    setVisible(visible) {
        this.isVisible = visible;
        if (visible && this.loaded) {
            this.start();
        } else {
            this.stop();
        }
    }

    start() {
        if (this.running) {
            return;
        }
        this.running = true;
        this.elapsedTime = 0;
        this.clock.start();
        this.fpsWindowStart = performance.now();
        this.frameCount = 0;
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

    animate = () => {
        if (!this.running || !this.loaded) {
            return;
        }

        this.rafId = requestAnimationFrame(this.animate);
        const now = performance.now();
        const delta = this.clock.getDelta();
        this.elapsedTime += delta;
        const t = this.elapsedTime;
        const pointerX = prefersReducedMotion ? 0 : this.pointer.x * 0.12;
        const pointerY = prefersReducedMotion ? 0 : this.pointer.y * 0.05;
        const baseYaw = this.getBaseYaw();

        if (this.mixer && this.motionMode !== "idle") {
            this.mixer.update(delta);
        }

        if (this.motionMode === "catwalk") {
            const swing = this.activeLook === "formal" ? 0.02 : 0.09;
            this.modelPivot.rotation.y = baseYaw + Math.sin(t * 0.5) * swing + pointerX;
            this.modelPivot.position.x = Math.sin(t * 0.62) * 0.03;
            this.modelScaleGroup.position.y = Math.sin(t * 2.05) * 0.015;
            this.model.rotation.z = Math.sin(t * 0.92) * 0.014;
        } else if (this.motionMode === "wind") {
            const windBase = this.activeLook === "formal" ? 0.03 : 0.12;
            const windSwing = this.activeLook === "formal" ? 0.024 : 0.11;
            this.modelPivot.rotation.y = baseYaw + windBase + Math.sin(t * 0.7) * windSwing + pointerX;
            this.modelPivot.position.x = Math.sin(t * 0.46) * 0.05;
            this.modelScaleGroup.position.y = Math.sin(t * 1.32) * 0.012;
            this.model.rotation.z = Math.sin(t * 1.08) * 0.035;
        } else {
            const idleSwing = this.activeLook === "formal" ? 0.012 : 0.08;
            this.modelPivot.rotation.y = baseYaw + Math.sin(t * 0.24) * idleSwing + pointerX * 0.5;
            this.modelScaleGroup.position.y = Math.sin(t * 1.1) * 0.01;
            this.model.rotation.z = Math.sin(t * 0.66) * 0.01;
        }

        this.runwayRing.rotation.z = t * 0.3;
        this.halo.rotation.z = -t * 0.08;
        this.sideGlow.rotation.z = t * 0.04;

        const preset = this.getCameraPreset();
        this.camera.position.x += ((preset.position[0] + pointerX * 0.75) - this.camera.position.x) * 0.05;
        this.camera.position.y += ((preset.position[1] - pointerY) - this.camera.position.y) * 0.05;
        this.camera.position.z += (preset.position[2] - this.camera.position.z) * 0.04;
        this.camera.lookAt(...preset.lookAt);

        this.renderer.render(this.scene, this.camera);
        this.updateMetric(now);
    };

    updateMetric(now) {
        this.frameCount += 1;
        const elapsed = now - this.fpsWindowStart;
        if (elapsed < 1000) {
            return;
        }
        const fps = Math.round((this.frameCount * 1000) / elapsed);
        this.frameCount = 0;
        this.fpsWindowStart = now;
        if (this.metricEl) {
            this.metricEl.textContent = `${fps} FPS`;
        }
    }

    updateProgress(percent) {
        if (this.progressEl) {
            this.progressEl.textContent = `${percent}%`;
        }
    }

    handleLookError(error, lookKey) {
        console.warn(`GLB load error for ${lookKey}:`, error);
        if (this.loadAttemptIndex < this.lookOrder.length - 1) {
            this.loadAttemptIndex += 1;
            const nextLook = this.lookOrder[this.loadAttemptIndex];
            if (this.metricEl) {
                this.metricEl.textContent = `Loading backup look (${nextLook})...`;
            }
            this.updateProgress(0);
            this.loadLook(nextLook);
            return;
        }
        this.handleError(error);
    }

    handleError(error) {
        console.error("GLB Load Error:", error);
        if (this.metricEl) {
            this.metricEl.textContent = "GLB load failed";
        }
        if (this.loadingEl) {
            this.loadingEl.innerHTML = '<p style="color:#ff8e8e;">Failed to load 3D model.<br>Check console and file path.</p>';
        }
        this.stage?.classList.add("scene-poster-only");
    }
}


function initHeroVariants() {
    const headline = document.getElementById("hero-headline");
    const copy = document.getElementById("hero-copy");
    const buttons = Array.from(document.querySelectorAll(".hero-variant"));
    if (!headline || !copy || !buttons.length) {
        return;
    }

    let activeIndex = 0;
    const activate = (index) => {
        activeIndex = index;
        const button = buttons[index];
        headline.textContent = button.dataset.headline || headline.textContent;
        copy.textContent = button.dataset.copy || copy.textContent;
        buttons.forEach((item, currentIndex) => setButtonState(item, currentIndex === index));
    };

    buttons.forEach((button, index) => button.addEventListener("click", () => activate(index)));
    activate(0);

    if (!prefersReducedMotion) {
        window.setInterval(() => activate((activeIndex + 1) % buttons.length), 7000);
    }
}


function initRevealObserver() {
    const items = document.querySelectorAll(".reveal-card");
    if (!items.length) {
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.12 }
    );

    items.forEach((item) => observer.observe(item));
}


function initShareButtons() {
    document.querySelectorAll(".share-trigger").forEach((button) => {
        button.addEventListener("click", async () => {
            const title = button.dataset.shareTitle || "StyleBridge";
            const url = button.dataset.shareUrl || window.location.href;

            if (navigator.share) {
                try {
                    await navigator.share({ title, url });
                    window.sbToast?.("Share sheet opened.");
                    return;
                } catch {
                    // Continue to clipboard fallback.
                }
            }

            if (navigator.clipboard?.writeText) {
                try {
                    await navigator.clipboard.writeText(url);
                    window.sbToast?.("Demo link copied.");
                    return;
                } catch {
                    // Continue to manual navigation fallback.
                }
            }

            window.location.href = url;
        });
    });
}


function setPosterMode(canvas, label = "Dress poster preview") {
    const stage = canvas.closest("[data-scene-stage]");
    const metric = document.querySelector(`[data-scene-metric-for="${canvas.id}"]`);
    const loading = stage?.querySelector("[data-scene-loading]");
    const progress = stage?.querySelector("[data-scene-progress]");
    if (stage) {
        stage.classList.add("scene-poster-only");
    }
    if (metric) {
        metric.textContent = label;
    }
    if (progress) {
        progress.textContent = "Poster";
    }
    if (loading) {
        loading.style.opacity = "1";
    }
}


function isSceneLikelyVisible(canvas, threshold = 0.18) {
    const rect = canvas.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    if (rect.width <= 0 || rect.height <= 0 || viewportHeight <= 0 || viewportWidth <= 0) {
        return false;
    }

    const visibleHeight = Math.min(rect.bottom, viewportHeight) - Math.max(rect.top, 0);
    const visibleWidth = Math.min(rect.right, viewportWidth) - Math.max(rect.left, 0);
    return visibleHeight >= rect.height * threshold && visibleWidth > 0;
}


function initScenes() {
    const canvases = Array.from(document.querySelectorAll(".three-scene"));
    if (!canvases.length) {
        return new Map();
    }

    if (!supportsWebGL()) {
        canvases.forEach((canvas) => setPosterMode(canvas));
        return new Map();
    }

    const scenes = new Map();
    const buildScene = (canvas) => {
        if (scenes.has(canvas.id)) {
            return scenes.get(canvas.id);
        }
        try {
            const scene = new RunwayScene(canvas, canvas.dataset.scene || "hero");
            scenes.set(canvas.id, scene);
            return scene;
        } catch (error) {
            console.error("Scene setup failed:", error);
            setPosterMode(canvas, "Dress poster preview");
            return null;
        }
    };

    const observer = "IntersectionObserver" in window
        ? new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        buildScene(entry.target)?.setVisible(true);
                    } else {
                        scenes.get(entry.target.id)?.setVisible(false);
                    }
                });
            },
            { threshold: 0.18 }
        )
        : null;

    canvases.forEach((canvas) => {
        observer?.observe(canvas);

        // Eagerly initialize above-the-fold scenes so the hero does not depend
        // on IntersectionObserver timing quirks to start loading.
        if ((canvas.dataset.scene || "hero") === "hero" || isSceneLikelyVisible(canvas)) {
            buildScene(canvas)?.setVisible(true);
        }
    });

    return scenes;
}


function initControls(scenes) {
    document.querySelectorAll(".scene-control").forEach((button) => {
        button.addEventListener("click", () => {
            const scene = scenes.get(button.dataset.sceneTarget);
            if (!scene) {
                return;
            }

            const action = button.dataset.sceneAction;
            const value = button.dataset.sceneValue;
            if (action === "material") {
                scene.applyMaterial(value);
            } else if (action === "lighting") {
                scene.applyLighting(value);
            } else if (action === "motion") {
                scene.setMotionMode(value);
            } else if (action === "view") {
                scene.setViewMode(value);
            } else if (action === "size") {
                scene.applySize(value);
            }

            const siblings = document.querySelectorAll(
                `.scene-control[data-scene-target="${button.dataset.sceneTarget}"][data-scene-action="${action}"]`
            );
            siblings.forEach((item) => setButtonState(item, item === button));
        });
    });
}


document.addEventListener("DOMContentLoaded", () => {
    try {
        document.documentElement.classList.add("js-reveal");
        initHeroVariants();
        initRevealObserver();
        initShareButtons();
        const scenes = initScenes();
        initControls(scenes);
        document.documentElement.dataset.sceneBoot = "ok";
    } catch (error) {
        document.documentElement.dataset.sceneBoot = "error";
        document.documentElement.dataset.sceneBootError = error?.message || String(error);
        console.error("Scene bootstrap failed:", error);
        document.querySelectorAll(".three-scene").forEach((canvas) => setPosterMode(canvas, "Dress poster preview"));
    }
});
