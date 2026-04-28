import * as THREE from "../vendor/three.module.min.js";
import { GLTFLoader } from "../vendor/GLTFLoader.js";

function setPressed(buttons, activeValue, attrName) {
    buttons.forEach((button) => {
        const pressed = button.dataset[attrName] === activeValue;
        button.setAttribute("aria-pressed", pressed ? "true" : "false");
    });
}

class DemoWorkspace {
    constructor(config) {
        this.config = config;
        this.canvas = document.getElementById("demo-canvas");
        this.statusBadge = document.getElementById("demoStatusBadge");
        this.statusText = document.getElementById("demoStatusText");
        this.loading = document.getElementById("demoLoading");
        this.uploadForm = document.getElementById("demoUploadForm");
        this.modelFile = document.getElementById("demoModelFile");
        this.shareButton = document.getElementById("demoShare");
        this.exportButton = document.getElementById("demoExport");
        this.sampleButtons = Array.from(document.querySelectorAll("[data-demo-model]"));
        this.motionButtons = Array.from(document.querySelectorAll("[data-demo-motion]"));
        this.lightingButtons = Array.from(document.querySelectorAll("[data-demo-lighting]"));
        this.paletteButtons = Array.from(document.querySelectorAll("[data-demo-palette]"));

        this.loader = new GLTFLoader();
        this.clock = new THREE.Clock();
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x040b17);

        this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
        this.camera.position.set(0, 1.4, 4.3);

        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
        this.renderer.setSize(960, 1200, false);
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

        this.root = null;
        this.baseY = 0;
        this.mixer = null;
        this.clipAction = null;
        this.materials = [];
        this.currentModelUrl = "";
        this.motionMode = "idle";
        this.paletteMode = "original";
        this.lightingMode = "studio";
        this.animateToken = 0;

        this.initScene();
        this.bindEvents();
    }

    initScene() {
        const floor = new THREE.Mesh(
            new THREE.CircleGeometry(4.4, 80),
            new THREE.MeshStandardMaterial({ color: 0x0a1728, roughness: 0.92, metalness: 0.04 })
        );
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -1.25;
        floor.receiveShadow = true;
        this.scene.add(floor);

        this.ambientLight = new THREE.HemisphereLight(0xc7e4ff, 0x0e1218, 1.15);
        this.keyLight = new THREE.DirectionalLight(0xdff0ff, 2.1);
        this.keyLight.position.set(2.8, 5, 3.3);
        this.keyLight.castShadow = true;
        this.keyLight.shadow.mapSize.set(2048, 2048);

        this.fillLight = new THREE.DirectionalLight(0x9ad7ff, 0.9);
        this.fillLight.position.set(-3, 2.5, 1.2);

        this.rimLight = new THREE.PointLight(0x8cc8ff, 0.55, 12, 2);
        this.rimLight.position.set(-1.8, 1.5, -2.5);

        this.scene.add(this.ambientLight, this.keyLight, this.fillLight, this.rimLight);
    }

    bindEvents() {
        window.addEventListener("resize", () => this.resize());
        this.resize();

        this.sampleButtons.forEach((button) => {
            button.addEventListener("click", () => {
                const modelUrl = button.dataset.demoModel || "";
                this.loadModel(modelUrl, "Sample loaded");
            });
        });

        this.motionButtons.forEach((button) => {
            button.addEventListener("click", () => this.setMotion(button.dataset.demoMotion || "idle"));
        });
        this.lightingButtons.forEach((button) => {
            button.addEventListener("click", () => this.setLighting(button.dataset.demoLighting || "studio"));
        });
        this.paletteButtons.forEach((button) => {
            button.addEventListener("click", () => this.setPalette(button.dataset.demoPalette || "original"));
        });

        this.uploadForm?.addEventListener("submit", async (event) => {
            event.preventDefault();
            const file = this.modelFile?.files?.[0];
            if (!file) {
                this.setStatus("Pick a .glb or .gltf file first.");
                return;
            }

            const formData = new FormData(this.uploadForm);
            formData.set("model", file);
            this.setLoading(true);
            this.setStatus("Uploading model...");

            try {
                const response = await fetch(this.config.uploadUrl, {
                    method: "POST",
                    body: formData,
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok || !payload.url) {
                    throw new Error(payload?.error || "Upload failed.");
                }
                await this.loadModel(payload.url, `Uploaded: ${payload.filename || "model"}`);
            } catch (error) {
                this.setStatus(`Upload failed: ${error.message}`);
            } finally {
                this.setLoading(false);
            }
        });

        this.shareButton?.addEventListener("click", async () => {
            const shareUrl = `${this.config.shareBaseUrl}?model=${encodeURIComponent(this.currentModelUrl || this.config.initialModel)}`;
            if (navigator.share) {
                try {
                    await navigator.share({ title: "StyleBridge 3D Preview", url: shareUrl });
                    this.setStatus("Share sheet opened.");
                    return;
                } catch {
                    // Fall through to clipboard.
                }
            }

            if (navigator.clipboard?.writeText) {
                try {
                    await navigator.clipboard.writeText(shareUrl);
                    this.setStatus("Preview link copied.");
                    return;
                } catch {
                    // Fall through to manual fallback.
                }
            }

            window.location.href = shareUrl;
        });

        this.exportButton?.addEventListener("click", () => {
            const link = document.createElement("a");
            link.href = this.canvas.toDataURL("image/png");
            link.download = "stylebridge-preview.png";
            link.click();
            this.setStatus("Preview image exported.");
        });
    }

    setStatus(message) {
        if (this.statusText) {
            this.statusText.textContent = message;
        }
    }

    setBadge(message) {
        if (this.statusBadge) {
            this.statusBadge.textContent = message;
        }
    }

    setLoading(loading) {
        if (!this.loading) {
            return;
        }
        this.loading.classList.toggle("hidden", !loading);
        this.loading.classList.toggle("flex", loading);
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        const width = Math.max(1, Math.floor(rect.width));
        const height = Math.max(1, Math.floor(rect.height));
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height, false);
    }

    async loadModel(modelUrl, statusLabel = "Model loaded") {
        if (!modelUrl) {
            this.setStatus("Missing model URL.");
            return;
        }

        this.setLoading(true);
        this.setBadge("Loading");
        this.setStatus("Loading model...");

        const gltf = await new Promise((resolve, reject) => {
            this.loader.load(
                modelUrl,
                resolve,
                undefined,
                (error) => reject(error instanceof Error ? error : new Error("Could not load GLB"))
            );
        }).catch((error) => {
            this.setStatus(`Load failed: ${error.message}`);
            this.setBadge("Load failed");
            this.setLoading(false);
            return null;
        });

        if (!gltf) {
            return;
        }

        if (this.root) {
            this.scene.remove(this.root);
        }
        this.materials = [];
        this.root = gltf.scene;

        this.root.traverse((child) => {
            if (!child.isMesh) {
                return;
            }
            child.castShadow = true;
            child.receiveShadow = true;
            const mats = Array.isArray(child.material) ? child.material : [child.material];
            mats.forEach((material) => {
                if (!material) {
                    return;
                }
                this.materials.push({
                    material,
                    color: material.color?.clone?.(),
                    emissive: material.emissive?.clone?.(),
                    roughness: material.roughness,
                    metalness: material.metalness,
                });
            });
        });

        const bounds = new THREE.Box3().setFromObject(this.root);
        const size = bounds.getSize(new THREE.Vector3());
        const center = bounds.getCenter(new THREE.Vector3());

        this.root.position.sub(center);
        const maxDimension = Math.max(size.x, size.y, size.z) || 1;
        const targetScale = 2.2 / maxDimension;
        this.root.scale.setScalar(targetScale);
        this.root.position.y = -0.35;
        this.baseY = this.root.position.y;

        this.mixer = null;
        this.clipAction = null;
        if (Array.isArray(gltf.animations) && gltf.animations.length > 0) {
            this.mixer = new THREE.AnimationMixer(this.root);
            this.clipAction = this.mixer.clipAction(gltf.animations[0]);
            this.clipAction.play();
        }

        this.scene.add(this.root);
        this.currentModelUrl = modelUrl;
        this.setMotion(this.motionMode);
        this.setPalette(this.paletteMode);
        this.setLighting(this.lightingMode);
        this.setBadge("Live");
        this.setStatus(statusLabel);
        this.setLoading(false);
    }

    setMotion(mode) {
        this.motionMode = mode || "idle";
        setPressed(this.motionButtons, this.motionMode, "demoMotion");

        if (this.clipAction) {
            this.clipAction.enabled = true;
            this.clipAction.paused = false;
            if (this.motionMode === "idle") {
                this.clipAction.timeScale = 0.45;
            } else if (this.motionMode === "walk") {
                this.clipAction.timeScale = 1;
            } else {
                this.clipAction.timeScale = 0.8;
            }
        }
    }

    setLighting(mode) {
        this.lightingMode = mode || "studio";
        setPressed(this.lightingButtons, this.lightingMode, "demoLighting");

        const presets = {
            studio: { bg: 0x040b17, ambient: 1.15, key: 2.1, fill: 0.9, rim: 0.55 },
            day: { bg: 0x112033, ambient: 1.35, key: 1.65, fill: 1.1, rim: 0.35 },
            night: { bg: 0x02050e, ambient: 0.78, key: 1.35, fill: 0.55, rim: 0.88 },
        };
        const preset = presets[this.lightingMode] || presets.studio;
        this.scene.background.setHex(preset.bg);
        this.ambientLight.intensity = preset.ambient;
        this.keyLight.intensity = preset.key;
        this.fillLight.intensity = preset.fill;
        this.rimLight.intensity = preset.rim;
    }

    setPalette(mode) {
        this.paletteMode = mode || "original";
        setPressed(this.paletteButtons, this.paletteMode, "demoPalette");

        this.materials.forEach((entry) => {
            const { material, color, emissive, roughness, metalness } = entry;
            if (!material) {
                return;
            }

            if (color && material.color) {
                material.color.copy(color);
            }
            if (emissive && material.emissive) {
                material.emissive.copy(emissive);
            }
            if (typeof roughness === "number" && "roughness" in material) {
                material.roughness = roughness;
            }
            if (typeof metalness === "number" && "metalness" in material) {
                material.metalness = metalness;
            }

            if (this.paletteMode === "charcoal" && material.color) {
                material.color.multiply(new THREE.Color(0x7f8996));
                if ("roughness" in material) {
                    material.roughness = Math.min(1, (material.roughness ?? 0.7) + 0.16);
                }
            } else if (this.paletteMode === "sand" && material.color) {
                material.color.multiply(new THREE.Color(0xd7c39d));
                if ("roughness" in material) {
                    material.roughness = Math.max(0, (material.roughness ?? 0.7) - 0.08);
                }
            }

            material.needsUpdate = true;
        });
    }

    animate() {
        this.animateToken = window.requestAnimationFrame(() => this.animate());
        const delta = this.clock.getDelta();
        const elapsed = this.clock.elapsedTime;

        if (this.mixer) {
            this.mixer.update(delta);
        }
        if (this.root) {
            if (this.motionMode === "spin") {
                this.root.rotation.y += delta * 0.9;
                this.root.position.y = this.baseY + (Math.sin(elapsed * 1.2) * 0.03);
            } else if (this.motionMode === "walk") {
                this.root.rotation.y = Math.sin(elapsed * 0.6) * 0.08;
                this.root.position.y = this.baseY + (Math.sin(elapsed * 3.2) * 0.02);
            } else {
                this.root.rotation.y *= 0.94;
                this.root.position.y = this.baseY + (Math.sin(elapsed * 1.5) * 0.01);
            }
        }

        this.renderer.render(this.scene, this.camera);
    }

    async init() {
        await this.loadModel(this.config.initialModel, "Sample loaded");
        this.animate();
    }
}

export async function bootDemoWorkspace(config) {
    const workspace = new DemoWorkspace(config);
    await workspace.init();
    return workspace;
}
