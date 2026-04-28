import { FilesetResolver, PoseLandmarker } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/vision_bundle.mjs";

const VISION_WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.21/wasm";
const POSE_MODEL_URL =
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

const LANDMARK = {
    nose: 0,
    leftEar: 7,
    rightEar: 8,
    leftShoulder: 11,
    rightShoulder: 12,
    leftElbow: 13,
    rightElbow: 14,
    leftWrist: 15,
    rightWrist: 16,
    leftPinky: 17,
    rightPinky: 18,
    leftIndex: 19,
    rightIndex: 20,
    leftThumb: 21,
    rightThumb: 22,
    leftHip: 23,
    rightHip: 24,
    leftKnee: 25,
    rightKnee: 26,
    leftAnkle: 27,
    rightAnkle: 28,
    leftHeel: 29,
    rightHeel: 30,
    leftFoot: 31,
    rightFoot: 32,
};

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function lerp(a, b, t) {
    return a + ((b - a) * t);
}

function point(x, y) {
    return { x, y };
}

function add(a, b) {
    return point(a.x + b.x, a.y + b.y);
}

function subtract(a, b) {
    return point(a.x - b.x, a.y - b.y);
}

function scaleVector(v, factor) {
    return point(v.x * factor, v.y * factor);
}

function midpoint(a, b) {
    return point((a.x + b.x) / 2, (a.y + b.y) / 2);
}

function lerpPoint(a, b, t) {
    return point(lerp(a.x, b.x, t), lerp(a.y, b.y, t));
}

function lengthOf(v) {
    return Math.hypot(v.x, v.y);
}

function distanceBetween(a, b) {
    return lengthOf(subtract(a, b));
}

function normalize(v) {
    const magnitude = lengthOf(v) || 1;
    return point(v.x / magnitude, v.y / magnitude);
}

function rotate90(v) {
    return point(-v.y, v.x);
}

function average(values) {
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

function computeCoverRect(sourceWidth, sourceHeight, targetWidth, targetHeight) {
    const sourceAspect = sourceWidth / Math.max(sourceHeight, 1);
    const targetAspect = targetWidth / Math.max(targetHeight, 1);
    if (sourceAspect > targetAspect) {
        const drawHeight = targetHeight;
        const drawWidth = drawHeight * sourceAspect;
        return { dx: (targetWidth - drawWidth) / 2, dy: 0, dw: drawWidth, dh: drawHeight };
    }
    const drawWidth = targetWidth;
    const drawHeight = drawWidth / Math.max(sourceAspect, 0.001);
    return { dx: 0, dy: (targetHeight - drawHeight) / 2, dw: drawWidth, dh: drawHeight };
}

function loadImage(sourceUrl) {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.decoding = "async";
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error(`Could not load image: ${sourceUrl.slice(0, 60)}`));
        image.src = sourceUrl;
    });
}

function createRasterCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width));
    canvas.height = Math.max(1, Math.round(height));
    return canvas;
}

function drawImageCover(ctx, source, rect) {
    ctx.drawImage(source, rect.dx, rect.dy, rect.dw, rect.dh);
}

function landmarkToCanvas(landmarks, index, coverRect) {
    const landmark = landmarks[index];
    if (!landmark) {
        return null;
    }
    return {
        x: coverRect.dx + (landmark.x * coverRect.dw),
        y: coverRect.dy + (landmark.y * coverRect.dh),
        visibility: landmark.visibility ?? 1,
    };
}

function visibleLandmark(landmarks, index, threshold = 0.35) {
    const landmark = landmarks[index];
    return Boolean(landmark && (landmark.visibility ?? 1) >= threshold);
}

function averageVisibility(landmarks, indices) {
    return average(
        indices
            .map((index) => landmarks[index]?.visibility ?? 0)
            .filter((value) => Number.isFinite(value))
    );
}

function copyLandmarks(landmarks) {
    return landmarks.map((entry) => ({
        x: entry.x,
        y: entry.y,
        z: entry.z ?? 0,
        visibility: entry.visibility ?? 1,
        presence: entry.presence ?? 1,
    }));
}

function smoothLandmarks(previous, next) {
    if (!previous?.length) {
        return copyLandmarks(next);
    }
    return next.map((entry, index) => {
        const prior = previous[index] || entry;
        const delta = Math.hypot((entry.x ?? 0) - (prior.x ?? 0), (entry.y ?? 0) - (prior.y ?? 0));
        const alpha = clamp(0.24 + (delta * 5.2), 0.24, 0.74);
        return {
            x: lerp(prior.x ?? 0, entry.x ?? 0, alpha),
            y: lerp(prior.y ?? 0, entry.y ?? 0, alpha),
            z: lerp(prior.z ?? 0, entry.z ?? 0, alpha),
            visibility: lerp(prior.visibility ?? 1, entry.visibility ?? 1, 0.38),
            presence: lerp(prior.presence ?? 1, entry.presence ?? 1, 0.38),
        };
    });
}

function cropLayerToCanvas(image, bounds) {
    const sx = image.naturalWidth * bounds.x;
    const sy = image.naturalHeight * bounds.y;
    const sw = image.naturalWidth * bounds.w;
    const sh = image.naturalHeight * bounds.h;
    const canvas = createRasterCanvas(sw, sh);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(image, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    return canvas;
}

function buildMaskCanvas(mask) {
    if (!mask) {
        return null;
    }
    const width = Number(mask.width || 0);
    const height = Number(mask.height || 0);
    if (!width || !height) {
        return null;
    }
    const buffer = typeof mask.getAsFloat32Array === "function"
        ? mask.getAsFloat32Array()
        : typeof mask.getAsUint8Array === "function"
            ? mask.getAsUint8Array()
            : null;
    if (!buffer?.length) {
        return null;
    }
    const canvas = createRasterCanvas(width, height);
    const ctx = canvas.getContext("2d");
    const imageData = ctx.createImageData(width, height);
    const floatMask = buffer instanceof Float32Array;
    for (let index = 0; index < buffer.length; index += 1) {
        const alpha = floatMask ? clamp(Math.round(buffer[index] * 255), 0, 255) : buffer[index];
        const offset = index * 4;
        imageData.data[offset] = 255;
        imageData.data[offset + 1] = 255;
        imageData.data[offset + 2] = 255;
        imageData.data[offset + 3] = alpha;
    }
    ctx.putImageData(imageData, 0, 0);
    return canvas;
}

function withClip(ctx, drawClip, drawContent) {
    ctx.save();
    ctx.beginPath();
    drawClip();
    ctx.clip();
    drawContent();
    ctx.restore();
}

function drawTriangle(ctx, image, sourceTriangle, destinationTriangle) {
    const [s0, s1, s2] = sourceTriangle;
    const [d0, d1, d2] = destinationTriangle;
    const denominator =
        (s0.x * (s1.y - s2.y)) +
        (s1.x * (s2.y - s0.y)) +
        (s2.x * (s0.y - s1.y));
    if (!denominator) {
        return;
    }
    const a = (
        (d0.x * (s1.y - s2.y)) +
        (d1.x * (s2.y - s0.y)) +
        (d2.x * (s0.y - s1.y))
    ) / denominator;
    const b = (
        (d0.y * (s1.y - s2.y)) +
        (d1.y * (s2.y - s0.y)) +
        (d2.y * (s0.y - s1.y))
    ) / denominator;
    const c = (
        (d0.x * (s2.x - s1.x)) +
        (d1.x * (s0.x - s2.x)) +
        (d2.x * (s1.x - s0.x))
    ) / denominator;
    const d = (
        (d0.y * (s2.x - s1.x)) +
        (d1.y * (s0.x - s2.x)) +
        (d2.y * (s1.x - s0.x))
    ) / denominator;
    const e = (
        (d0.x * ((s1.x * s2.y) - (s2.x * s1.y))) +
        (d1.x * ((s2.x * s0.y) - (s0.x * s2.y))) +
        (d2.x * ((s0.x * s1.y) - (s1.x * s0.y)))
    ) / denominator;
    const f = (
        (d0.y * ((s1.x * s2.y) - (s2.x * s1.y))) +
        (d1.y * ((s2.x * s0.y) - (s0.x * s2.y))) +
        (d2.y * ((s0.x * s1.y) - (s1.x * s0.y)))
    ) / denominator;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(d0.x, d0.y);
    ctx.lineTo(d1.x, d1.y);
    ctx.lineTo(d2.x, d2.y);
    ctx.closePath();
    ctx.clip();
    ctx.setTransform(a, b, c, d, e, f);
    ctx.drawImage(image, 0, 0);
    ctx.restore();
}

function drawQuad(ctx, image, sourceRect, quad) {
    const sourceTopLeft = point(sourceRect.x, sourceRect.y);
    const sourceTopRight = point(sourceRect.x + sourceRect.w, sourceRect.y);
    const sourceBottomRight = point(sourceRect.x + sourceRect.w, sourceRect.y + sourceRect.h);
    const sourceBottomLeft = point(sourceRect.x, sourceRect.y + sourceRect.h);
    drawTriangle(ctx, image, [sourceTopLeft, sourceTopRight, sourceBottomRight], [quad[0], quad[1], quad[2]]);
    drawTriangle(ctx, image, [sourceTopLeft, sourceBottomRight, sourceBottomLeft], [quad[0], quad[2], quad[3]]);
}

function drawStripWarp(ctx, image, sourceRect, topLeft, topRight, bottomRight, bottomLeft, segments = 6) {
    for (let index = 0; index < segments; index += 1) {
        const t0 = index / segments;
        const t1 = (index + 1) / segments;
        const quad = [
            lerpPoint(topLeft, bottomLeft, t0),
            lerpPoint(topRight, bottomRight, t0),
            lerpPoint(topRight, bottomRight, t1),
            lerpPoint(topLeft, bottomLeft, t1),
        ];
        drawQuad(
            ctx,
            image,
            {
                x: sourceRect.x,
                y: sourceRect.y + (sourceRect.h * t0),
                w: sourceRect.w,
                h: sourceRect.h * (t1 - t0),
            },
            quad
        );
    }
}

function lineEndpoints(center, axis, halfWidth) {
    return [subtract(center, scaleVector(axis, halfWidth)), add(center, scaleVector(axis, halfWidth))];
}

function buildTopGeometry(landmarks, coverRect, arProfile, scaleAdjust, offsetX, offsetY) {
    if (
        !visibleLandmark(landmarks, LANDMARK.leftShoulder) ||
        !visibleLandmark(landmarks, LANDMARK.rightShoulder) ||
        !visibleLandmark(landmarks, LANDMARK.leftHip) ||
        !visibleLandmark(landmarks, LANDMARK.rightHip)
    ) {
        return null;
    }
    const leftShoulder = landmarkToCanvas(landmarks, LANDMARK.leftShoulder, coverRect);
    const rightShoulder = landmarkToCanvas(landmarks, LANDMARK.rightShoulder, coverRect);
    const leftHip = landmarkToCanvas(landmarks, LANDMARK.leftHip, coverRect);
    const rightHip = landmarkToCanvas(landmarks, LANDMARK.rightHip, coverRect);
    const shoulderCenter = midpoint(leftShoulder, rightShoulder);
    const hipCenter = midpoint(leftHip, rightHip);
    const shoulderSpan = distanceBetween(leftShoulder, rightShoulder);
    const hipSpan = distanceBetween(leftHip, rightHip);
    const downAxis = normalize(subtract(hipCenter, shoulderCenter));
    let rightAxis = rotate90(downAxis);
    const actualRight = normalize(subtract(rightShoulder, leftShoulder));
    if ((rightAxis.x * actualRight.x) + (rightAxis.y * actualRight.y) < 0) {
        rightAxis = scaleVector(rightAxis, -1);
    }

    const fit = arProfile.top_fit || {};
    const shoulderHalf = (shoulderSpan * (fit.shoulder_width || 1.2) * scaleAdjust) / 2;
    const hipHalf = (Math.max(hipSpan, shoulderSpan * 0.78) * (fit.hip_width || 1.08) * scaleAdjust) / 2;
    const torsoHeight = distanceBetween(shoulderCenter, hipCenter) * (fit.torso_height || 1) * scaleAdjust;
    const yShift = (fit.y_shift || 0) + offsetY;
    const xShift = offsetX;

    const translatedShoulderCenter = add(shoulderCenter, add(scaleVector(downAxis, torsoHeight * yShift), scaleVector(rightAxis, shoulderSpan * xShift)));
    const translatedHipCenter = add(translatedShoulderCenter, scaleVector(downAxis, torsoHeight));
    const midCenter = add(translatedShoulderCenter, scaleVector(downAxis, torsoHeight * 0.56));

    return {
        shoulder: lineEndpoints(translatedShoulderCenter, rightAxis, shoulderHalf),
        mid: lineEndpoints(midCenter, rightAxis, lerp(shoulderHalf, hipHalf, 0.62)),
        hip: lineEndpoints(translatedHipCenter, rightAxis, hipHalf),
    };
}

function buildBottomGeometry(landmarks, coverRect, arProfile, scaleAdjust, offsetX, offsetY) {
    if (
        !visibleLandmark(landmarks, LANDMARK.leftHip) ||
        !visibleLandmark(landmarks, LANDMARK.rightHip) ||
        !visibleLandmark(landmarks, LANDMARK.leftKnee, 0.2) ||
        !visibleLandmark(landmarks, LANDMARK.rightKnee, 0.2) ||
        !visibleLandmark(landmarks, LANDMARK.leftAnkle, 0.2) ||
        !visibleLandmark(landmarks, LANDMARK.rightAnkle, 0.2)
    ) {
        return null;
    }
    const leftHip = landmarkToCanvas(landmarks, LANDMARK.leftHip, coverRect);
    const rightHip = landmarkToCanvas(landmarks, LANDMARK.rightHip, coverRect);
    const leftKnee = landmarkToCanvas(landmarks, LANDMARK.leftKnee, coverRect);
    const rightKnee = landmarkToCanvas(landmarks, LANDMARK.rightKnee, coverRect);
    const leftAnkle = landmarkToCanvas(landmarks, LANDMARK.leftAnkle, coverRect);
    const rightAnkle = landmarkToCanvas(landmarks, LANDMARK.rightAnkle, coverRect);

    const hipCenter = midpoint(leftHip, rightHip);
    const kneeCenter = midpoint(leftKnee, rightKnee);
    const ankleCenter = midpoint(leftAnkle, rightAnkle);
    const hipSpan = distanceBetween(leftHip, rightHip);
    const kneeSpan = Math.max(distanceBetween(leftKnee, rightKnee), hipSpan * 0.5);
    const ankleSpan = Math.max(distanceBetween(leftAnkle, rightAnkle), hipSpan * 0.34);
    const downAxis = normalize(subtract(ankleCenter, hipCenter));
    let rightAxis = rotate90(downAxis);
    const actualRight = normalize(subtract(rightHip, leftHip));
    if ((rightAxis.x * actualRight.x) + (rightAxis.y * actualRight.y) < 0) {
        rightAxis = scaleVector(rightAxis, -1);
    }

    const fit = arProfile.bottom_fit || {};
    const hipHalf = (hipSpan * (fit.hip_width || 1.02) * scaleAdjust) / 2;
    const hemHalf = (Math.max(ankleSpan, hipSpan * 0.44) * (fit.hem_width || 1) * scaleAdjust) / 2;
    const legLength = distanceBetween(hipCenter, ankleCenter) * (fit.leg_length || 1) * scaleAdjust;
    const yShift = (fit.y_shift || 0) + offsetY;
    const xShift = offsetX;

    const translatedHipCenter = add(hipCenter, add(scaleVector(downAxis, legLength * yShift), scaleVector(rightAxis, hipSpan * xShift)));
    const translatedKneeCenter = add(translatedHipCenter, scaleVector(downAxis, distanceBetween(hipCenter, kneeCenter) * scaleAdjust));
    const translatedHemCenter = add(translatedHipCenter, scaleVector(downAxis, legLength));

    return {
        waist: lineEndpoints(translatedHipCenter, rightAxis, hipHalf),
        knee: lineEndpoints(translatedKneeCenter, rightAxis, Math.max(kneeSpan * 0.46 * scaleAdjust, lerp(hipHalf, hemHalf, 0.42))),
        hem: lineEndpoints(translatedHemCenter, rightAxis, hemHalf),
    };
}

function clipCircle(ctx, center, radius) {
    ctx.moveTo(center.x + radius, center.y);
    ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
}

function clipEllipse(ctx, center, radiusX, radiusY, rotation = 0) {
    ctx.ellipse(center.x, center.y, radiusX, radiusY, rotation, 0, Math.PI * 2);
}

function drawForegroundCutouts(ctx, source, coverRect, landmarks) {
    const leftShoulder = landmarkToCanvas(landmarks, LANDMARK.leftShoulder, coverRect);
    const rightShoulder = landmarkToCanvas(landmarks, LANDMARK.rightShoulder, coverRect);
    if (leftShoulder && rightShoulder) {
        const shoulderSpan = distanceBetween(leftShoulder, rightShoulder);
        const nose = landmarkToCanvas(landmarks, LANDMARK.nose, coverRect)
            || midpoint(
                landmarkToCanvas(landmarks, LANDMARK.leftEar, coverRect) || leftShoulder,
                landmarkToCanvas(landmarks, LANDMARK.rightEar, coverRect) || rightShoulder
            );
        withClip(
            ctx,
            () => {
                clipEllipse(ctx, point(nose.x, nose.y - (shoulderSpan * 0.12)), shoulderSpan * 0.34, shoulderSpan * 0.42);
            },
            () => drawImageCover(ctx, source, coverRect)
        );
    }

    [
        [LANDMARK.leftWrist, LANDMARK.leftIndex, LANDMARK.leftThumb, LANDMARK.leftPinky, LANDMARK.leftElbow],
        [LANDMARK.rightWrist, LANDMARK.rightIndex, LANDMARK.rightThumb, LANDMARK.rightPinky, LANDMARK.rightElbow],
    ].forEach((set) => {
        const wrist = landmarkToCanvas(landmarks, set[0], coverRect);
        const index = landmarkToCanvas(landmarks, set[1], coverRect);
        const thumb = landmarkToCanvas(landmarks, set[2], coverRect);
        const pinky = landmarkToCanvas(landmarks, set[3], coverRect);
        const elbow = landmarkToCanvas(landmarks, set[4], coverRect);
        if (!wrist || !index || !thumb || !pinky || !elbow) {
            return;
        }
        const palmCenter = midpoint(midpoint(index, thumb), midpoint(pinky, wrist));
        const handRadius = Math.max(distanceBetween(wrist, elbow) * 0.32, distanceBetween(index, pinky) * 0.82);
        withClip(
            ctx,
            () => clipCircle(ctx, palmCenter, handRadius),
            () => drawImageCover(ctx, source, coverRect)
        );
    });
}

class TryOnStudio {
    constructor(config) {
        this.config = config;
        this.looks = Array.isArray(config.looks) ? config.looks : [];
        this.lookMap = new Map(this.looks.map((look) => [look.slug, look]));
        this.layerAssetCache = new Map();
        this.poseLandmarker = null;
        this.runningMode = "IMAGE";
        this.lastVideoTime = -1;
        this.lastDetectionAt = 0;
        this.lastPose = null;
        this.smoothedLandmarks = null;
        this.activeLoop = 0;
        this.resizeObserver = null;
        this.cameraStartPromise = null;
        this.autoCameraQueued = false;
        this.state = {
            look: config.initialLook || this.looks[0]?.slug || "",
            layer: "full",
            sourceMode: config.latestSelfieUrl ? "photo" : "none",
            sourceUrl: config.latestSelfieUrl || "",
            sourceName: config.latestSelfieName || "",
            scanReport: config.initialScan && typeof config.initialScan === "object" ? config.initialScan : null,
            suggestions: Array.isArray(config.initialSuggestions) ? config.initialSuggestions : [],
            stream: null,
            controls: {
                scale: 100,
                offsetX: 0,
                offsetY: 0,
                rotation: 0,
                opacity: 88,
            },
        };
        this.elements = {
            stage: document.getElementById("stage"),
            stageLabel: document.getElementById("stageLabel"),
            status: document.getElementById("status"),
            fitBadge: document.getElementById("fitBadge"),
            canvas: document.getElementById("arCanvas"),
            photo: document.getElementById("photoSource"),
            video: document.getElementById("videoSource"),
            empty: document.getElementById("empty"),
            lookTitle: document.getElementById("lookTitle"),
            lookMeta: document.getElementById("lookMeta"),
            lookImage: document.getElementById("lookImage"),
            lookStyles: document.getElementById("lookStyles"),
            lookSummary: document.getElementById("lookSummary"),
            lookLink: document.getElementById("lookLink"),
            file: document.getElementById("file"),
            form: document.getElementById("uploadForm"),
            csrf: document.querySelector("#uploadForm [name='csrf_token']"),
            cameraStart: document.getElementById("cameraStart"),
            cameraCapture: document.getElementById("cameraCapture"),
            cameraStop: document.getElementById("cameraStop"),
            download: document.getElementById("download"),
            resetFit: document.getElementById("resetFit"),
            liftFit: document.getElementById("liftFit"),
            dropFit: document.getElementById("dropFit"),
            lookButtons: [...document.querySelectorAll("[data-look]")],
            layerButtons: [...document.querySelectorAll("[data-layer]")],
            scale: document.getElementById("scale"),
            scaleValue: document.getElementById("scaleValue"),
            offsetX: document.getElementById("offsetX"),
            xValue: document.getElementById("xValue"),
            offsetY: document.getElementById("offsetY"),
            yValue: document.getElementById("yValue"),
            rotation: document.getElementById("rotation"),
            rotationValue: document.getElementById("rotationValue"),
            opacity: document.getElementById("opacity"),
            opacityValue: document.getElementById("opacityValue"),
            scanHeadline: document.getElementById("scanHeadline"),
            scanSummary: document.getElementById("scanSummary"),
            scanChips: document.getElementById("scanChips"),
            scanSuggestions: document.getElementById("scanSuggestions"),
        };
    }

    currentLook() {
        return this.lookMap.get(this.state.look) || this.looks[0] || null;
    }

    currentLayerPayload(layerId) {
        const look = this.currentLook();
        return look?.try_on?.layers?.find((layer) => layer.id === layerId) || null;
    }

    setStatus(message, tone = "text-slate-400") {
        if (!this.elements.status) {
            return;
        }
        this.elements.status.textContent = message;
        this.elements.status.className = `mt-3 text-sm ${tone}`;
    }

    setFitBadge(message) {
        if (this.elements.fitBadge) {
            this.elements.fitBadge.textContent = message;
        }
    }

    describeCameraError(error) {
        if (!window.isSecureContext) {
            return "Camera access only works on localhost or HTTPS. Open this page from a secure address and try again.";
        }
        switch (error?.name) {
            case "NotAllowedError":
            case "SecurityError":
                return "Camera access was blocked. Allow camera access in the browser address bar and reload this page.";
            case "NotFoundError":
            case "OverconstrainedError":
                return "No usable front camera was found on this device.";
            case "NotReadableError":
            case "TrackStartError":
                return "The camera is already in use by another app or browser tab.";
            case "AbortError":
                return "The camera request was interrupted. Try again.";
            default:
                return "Camera permission was denied or the device camera is unavailable.";
        }
    }

    currentSourceElement() {
        if (this.state.sourceMode === "camera") {
            return this.elements.video;
        }
        if (this.state.sourceMode === "photo") {
            return this.elements.photo;
        }
        return null;
    }

    renderSuggestionPanel() {
        const report = this.state.scanReport;
        const suggestions = Array.isArray(this.state.suggestions) ? this.state.suggestions : [];

        if (this.elements.scanHeadline) {
            this.elements.scanHeadline.textContent = report?.headline || "No scan yet";
        }
        if (this.elements.scanSummary) {
            this.elements.scanSummary.textContent =
                report?.summary ||
                "Take or upload a clear photo and StyleBridge will scan the frame, then suggest looks to wear next.";
        }
        if (this.elements.scanChips) {
            this.elements.scanChips.innerHTML = "";
            (report?.chips || []).forEach((chip) => {
                const pill = document.createElement("span");
                pill.className =
                    "rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-black uppercase tracking-[0.14em] text-slate-200";
                pill.textContent = `${chip.label}: ${chip.value}`;
                this.elements.scanChips.appendChild(pill);
            });
        }
        if (!this.elements.scanSuggestions) {
            return;
        }
        this.elements.scanSuggestions.innerHTML = "";
        if (!suggestions.length) {
            const empty = document.createElement("div");
            empty.className = "rounded-[1.5rem] border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm leading-7 text-slate-400";
            empty.textContent = "Your next-look suggestions will appear here after the scan finishes.";
            this.elements.scanSuggestions.appendChild(empty);
            return;
        }

        suggestions.forEach((suggestion) => {
            const card = document.createElement("a");
            card.href = suggestion.shop_url || "#";
            card.className =
                "rounded-[1.5rem] border border-white/10 bg-white/5 p-4 transition hover:-translate-y-0.5 hover:bg-white/[0.07]";
            const styles = Array.isArray(suggestion.styles) ? suggestion.styles.slice(0, 3).join(" | ") : "";
            const price = Number.isFinite(Number(suggestion.price_total))
                ? `$${Number(suggestion.price_total).toFixed(2)}`
                : "";
            card.innerHTML = `
                <div class="flex items-start gap-3">
                  <img src="${suggestion.image_url || ""}" alt="${suggestion.title || "Suggested look"}" class="h-20 w-20 rounded-[1.1rem] object-cover" loading="lazy" referrerpolicy="no-referrer">
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-black uppercase tracking-[0.14em] text-cyan-200">${suggestion.creator || "StyleBridge edit"}</div>
                    <div class="mt-1 text-lg font-black text-white">${suggestion.title || "Suggested look"}</div>
                    <div class="mt-1 text-xs font-black uppercase tracking-[0.14em] text-slate-500">${styles}</div>
                    <div class="mt-2 text-sm leading-6 text-emerald-100">${suggestion.scan_reason || suggestion.match_reason || ""}</div>
                    <div class="mt-1 text-xs leading-5 text-slate-400">${suggestion.match_reason || ""}</div>
                  </div>
                  <div class="shrink-0 text-sm font-black text-white">${price}</div>
                </div>
            `;
            this.elements.scanSuggestions.appendChild(card);
        });
    }

    sampleSourceAppearance() {
        const source = this.currentSourceElement();
        const sourceWidth = source?.videoWidth || source?.naturalWidth || 0;
        const sourceHeight = source?.videoHeight || source?.naturalHeight || 0;
        if (!source || !sourceWidth || !sourceHeight) {
            return { palette: "neutral", lighting: "balanced" };
        }

        const sampleCanvas = createRasterCanvas(48, 60);
        const ctx = sampleCanvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(source, 0, 0, sampleCanvas.width, sampleCanvas.height);
        const { data } = ctx.getImageData(0, 0, sampleCanvas.width, sampleCanvas.height);
        let totalR = 0;
        let totalG = 0;
        let totalB = 0;
        let count = 0;

        for (let y = 10; y < sampleCanvas.height - 6; y += 1) {
            for (let x = 8; x < sampleCanvas.width - 8; x += 1) {
                const offset = ((y * sampleCanvas.width) + x) * 4;
                totalR += data[offset];
                totalG += data[offset + 1];
                totalB += data[offset + 2];
                count += 1;
            }
        }

        if (!count) {
            return { palette: "neutral", lighting: "balanced" };
        }

        const avgR = totalR / count;
        const avgG = totalG / count;
        const avgB = totalB / count;
        const warmth = avgR - avgB;
        const luminance = (0.2126 * avgR) + (0.7152 * avgG) + (0.0722 * avgB);

        return {
            palette: warmth > 10 ? "warm" : warmth < -10 ? "cool" : "neutral",
            lighting: luminance > 168 ? "bright" : luminance < 92 ? "low-light" : "balanced",
        };
    }

    buildScanContext() {
        const appearance = this.sampleSourceAppearance();
        const scan = {
            coverage: "",
            silhouette: "",
            palette: appearance.palette,
            lighting: appearance.lighting,
            confidence: 0,
        };

        const landmarks = this.lastPose?.landmarks;
        if (!landmarks?.length) {
            return scan;
        }

        scan.confidence = Number(
            averageVisibility(landmarks, [
                LANDMARK.leftShoulder,
                LANDMARK.rightShoulder,
                LANDMARK.leftHip,
                LANDMARK.rightHip,
                LANDMARK.leftKnee,
                LANDMARK.rightKnee,
                LANDMARK.leftAnkle,
                LANDMARK.rightAnkle,
            ]).toFixed(3)
        );

        const hasUpper =
            visibleLandmark(landmarks, LANDMARK.leftShoulder, 0.25) &&
            visibleLandmark(landmarks, LANDMARK.rightShoulder, 0.25) &&
            visibleLandmark(landmarks, LANDMARK.leftHip, 0.25) &&
            visibleLandmark(landmarks, LANDMARK.rightHip, 0.25);
        const hasLower =
            visibleLandmark(landmarks, LANDMARK.leftKnee, 0.2) &&
            visibleLandmark(landmarks, LANDMARK.rightKnee, 0.2) &&
            visibleLandmark(landmarks, LANDMARK.leftAnkle, 0.2) &&
            visibleLandmark(landmarks, LANDMARK.rightAnkle, 0.2);

        if (hasUpper && hasLower) {
            scan.coverage = "full-body";
        } else if (hasUpper) {
            scan.coverage = "upper-body";
        } else {
            scan.coverage = "portrait";
        }

        if (hasUpper) {
            const leftShoulder = landmarks[LANDMARK.leftShoulder];
            const rightShoulder = landmarks[LANDMARK.rightShoulder];
            const leftHip = landmarks[LANDMARK.leftHip];
            const rightHip = landmarks[LANDMARK.rightHip];
            const shoulderSpan = Math.hypot(
                (rightShoulder?.x || 0) - (leftShoulder?.x || 0),
                (rightShoulder?.y || 0) - (leftShoulder?.y || 0)
            );
            const hipSpan = Math.max(
                Math.hypot(
                    (rightHip?.x || 0) - (leftHip?.x || 0),
                    (rightHip?.y || 0) - (leftHip?.y || 0)
                ),
                0.001
            );
            const ratio = shoulderSpan / hipSpan;
            scan.silhouette = ratio > 1.08 ? "top-dominant" : ratio < 0.92 ? "bottom-dominant" : "balanced";
        }

        return scan;
    }

    buildLocalScanReport(scan) {
        const coverageLabels = {
            portrait: "Portrait crop",
            "upper-body": "Upper-body crop",
            "full-body": "Full-body framing",
        };
        const silhouetteLabels = {
            balanced: "Balanced frame",
            "top-dominant": "Top-led frame",
            "bottom-dominant": "Bottom-led frame",
        };
        const paletteLabels = {
            warm: "Warm palette",
            cool: "Cool palette",
            neutral: "Neutral palette",
        };
        const lightingLabels = {
            bright: "Bright light",
            balanced: "Balanced light",
            "low-light": "Low light",
        };

        const chips = [];
        if (scan.coverage) {
            chips.push({ label: "Frame", value: coverageLabels[scan.coverage] });
        }
        if (scan.silhouette) {
            chips.push({ label: "Shape", value: silhouetteLabels[scan.silhouette] });
        }
        if (scan.palette) {
            chips.push({ label: "Palette", value: paletteLabels[scan.palette] });
        }
        if (scan.lighting) {
            chips.push({ label: "Light", value: lightingLabels[scan.lighting] });
        }
        if (scan.confidence) {
            chips.push({ label: "Confidence", value: `${Math.round(scan.confidence * 100)}%` });
        }

        if (!chips.length) {
            return {
                headline: "Scan pending",
                summary: "The photo was saved, but we still need a clearer body read before tightening the suggestions.",
                chips: [{ label: "Status", value: "Waiting for a stronger scan" }],
            };
        }

        const summaryParts = [scan.coverage, scan.silhouette, scan.palette]
            .filter(Boolean)
            .map((part) => ({
                portrait: "portrait framing",
                "upper-body": "an upper-body crop",
                "full-body": "full-body framing",
                balanced: "a balanced frame",
                "top-dominant": "a stronger shoulder line",
                "bottom-dominant": "a lower-body-led frame",
                warm: "warmer color cues",
                cool: "cooler color cues",
                neutral: "neutral color cues",
            }[part] || part));

        return {
            headline: "Scan complete",
            summary: `We detected ${summaryParts.join(", ")} and used that to shape the next looks to try.`,
            chips,
        };
    }

    localScanFitScore(look, scan) {
        let score = 0;
        const bodyTypes = new Set(Array.isArray(look.body_types) ? look.body_types : []);
        const styles = new Set(Array.isArray(look.styles) ? look.styles : []);
        const fitMode = look.try_on?.fit_mode || "";
        const color = String(look.color || "").toLowerCase();

        if (scan.silhouette === "top-dominant" && ["Athletic", "Straight", "Tall"].some((entry) => bodyTypes.has(entry))) {
            score += 6;
        } else if (scan.silhouette === "bottom-dominant" && ["Curvy", "Plus size", "Straight"].some((entry) => bodyTypes.has(entry))) {
            score += 6;
        } else if (scan.silhouette === "balanced" && ["Straight", "Petite", "Tall"].some((entry) => bodyTypes.has(entry))) {
            score += 4;
        }

        if (scan.coverage === "full-body") {
            score += fitMode === "full-body" ? 3 : 1;
        } else if (scan.coverage) {
            score += fitMode === "full-body" ? 0 : 2;
        }

        if (scan.palette === "warm" && ["brown", "rose", "pearl", "white", "neutral"].includes(color)) {
            score += 4;
        } else if (scan.palette === "cool" && ["black", "blue", "emerald", "green"].includes(color)) {
            score += 4;
        } else if (scan.palette === "neutral" && ["black", "white", "brown", "neutral"].includes(color)) {
            score += 3;
        }

        if (scan.lighting === "low-light" && [...styles].some((style) => ["Formal", "Minimalist", "Modest"].includes(style))) {
            score += 2;
        } else if (scan.lighting === "bright" && [...styles].some((style) => ["Casual", "Streetwear", "Athleisure"].includes(style))) {
            score += 2;
        }

        return score;
    }

    buildLocalSuggestionReason(look, scan) {
        const reasons = [];
        const bodyTypes = new Set(Array.isArray(look.body_types) ? look.body_types : []);
        const color = String(look.color || "").toLowerCase();

        if (scan.silhouette === "top-dominant" && ["Athletic", "Straight", "Tall"].some((entry) => bodyTypes.has(entry))) {
            reasons.push("supports a stronger shoulder line");
        } else if (scan.silhouette === "bottom-dominant" && ["Curvy", "Plus size", "Straight"].some((entry) => bodyTypes.has(entry))) {
            reasons.push("balances a lower-body-led frame");
        } else if (scan.silhouette === "balanced") {
            reasons.push("keeps a balanced frame looking clean");
        }

        if (scan.palette === "warm" && ["brown", "rose", "pearl", "white", "neutral"].includes(color)) {
            reasons.push("its warmer tones should sit smoothly on camera");
        } else if (scan.palette === "cool" && ["black", "blue", "emerald", "green"].includes(color)) {
            reasons.push("its cooler tones should read cleanly in this shot");
        }

        if (!reasons.length) {
            return look.match_reason || "Recommended from your saved style profile.";
        }
        return `Scan pick: ${reasons.slice(0, 2).join("; ")}.`;
    }

    buildLocalSuggestions(scan) {
        return [...this.looks]
            .sort((left, right) => {
                const leftScore = this.localScanFitScore(left, scan);
                const rightScore = this.localScanFitScore(right, scan);
                if (rightScore !== leftScore) {
                    return rightScore - leftScore;
                }
                return (left.title || "").localeCompare(right.title || "");
            })
            .slice(0, 3)
            .map((look) => ({
                slug: look.slug,
                title: look.title,
                creator: look.creator,
                image_url: look.image_url,
                styles: look.styles || [],
                price_total: look.price_total || 0,
                shop_url: look.shop_url,
                match_reason: look.match_reason || "",
                scan_reason: this.buildLocalSuggestionReason(look, scan),
            }));
    }

    updateLocalSuggestions() {
        const scan = this.buildScanContext();
        this.state.scanReport = this.buildLocalScanReport(scan);
        this.state.suggestions = this.buildLocalSuggestions(scan);
        this.renderSuggestionPanel();
        return scan;
    }

    applySuggestionPayload(payload) {
        if (payload?.scan && typeof payload.scan === "object") {
            this.state.scanReport = payload.scan;
        }
        if (Array.isArray(payload?.suggestions)) {
            this.state.suggestions = payload.suggestions;
        }
        this.renderSuggestionPanel();
    }

    syncControls() {
        const controls = this.state.controls;
        this.elements.scale.value = String(controls.scale);
        this.elements.scaleValue.textContent = `${controls.scale}%`;
        this.elements.offsetX.value = String(controls.offsetX);
        this.elements.xValue.textContent = `${controls.offsetX}`;
        this.elements.offsetY.value = String(controls.offsetY);
        this.elements.yValue.textContent = `${controls.offsetY}`;
        this.elements.rotation.value = String(controls.rotation);
        this.elements.rotationValue.textContent = `${controls.rotation}deg`;
        this.elements.opacity.value = String(controls.opacity);
        this.elements.opacityValue.textContent = `${controls.opacity}%`;
    }

    applyLookCalibration() {
        const profile = this.currentLook()?.try_on?.ar_profile?.calibration || {};
        this.state.controls = {
            scale: clamp(Math.round(100 + ((profile.scale_bias || 0) * 100)), 82, 126),
            offsetX: clamp(Math.round((profile.offset_x || 0) * 100), -14, 14),
            offsetY: clamp(Math.round((profile.offset_y || 0) * 100), -18, 18),
            rotation: 0,
            opacity: clamp(Math.round((profile.opacity || 0.88) * 100), 60, 100),
        };
        this.syncControls();
    }

    async loadLookAssets(look) {
        if (!look) {
            return null;
        }
        const profile = look.try_on?.ar_profile || {};
        const jobs = ["top", "bottom", "full"].map(async (layerId) => {
            const cacheKey = `${look.slug}:${layerId}`;
            if (this.layerAssetCache.has(cacheKey)) {
                return [layerId, this.layerAssetCache.get(cacheKey)];
            }
            const layer = this.currentLayerPayload(layerId) || look.try_on?.layers?.find((entry) => entry.id === layerId);
            if (!layer) {
                return [layerId, null];
            }
            const image = await loadImage(layer.image_url);
            const bounds = layerId === "top"
                ? profile.top_bounds
                : layerId === "bottom"
                    ? profile.bottom_bounds
                    : { x: 0.18, y: 0.12, w: 0.64, h: 0.74 };
            const raster = cropLayerToCanvas(image, bounds);
            const asset = { image, raster };
            this.layerAssetCache.set(cacheKey, asset);
            return [layerId, asset];
        });
        await Promise.all(jobs);
        return true;
    }

    renderLookMeta() {
        const look = this.currentLook();
        if (!look) {
            return;
        }
        if (this.elements.lookTitle) {
            this.elements.lookTitle.textContent = look.title;
        }
        if (this.elements.lookMeta) {
            this.elements.lookMeta.textContent = `${look.creator} | $${Number(look.price_total || 0).toFixed(2)}`;
        }
        if (this.elements.lookImage) {
            this.elements.lookImage.src = look.image_url;
        }
        if (this.elements.lookLink) {
            this.elements.lookLink.href = look.shop_url;
        }
        if (this.elements.lookSummary) {
            this.elements.lookSummary.textContent = (look.try_on?.wearable_summary || []).join(" | ") || look.tagline;
        }
        if (this.elements.lookStyles) {
            this.elements.lookStyles.innerHTML = "";
            (look.styles || []).slice(0, 4).forEach((style) => {
                const chip = document.createElement("span");
                chip.className =
                    "rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-black uppercase tracking-[0.14em] text-slate-200";
                chip.textContent = style;
                this.elements.lookStyles.appendChild(chip);
            });
        }
        if (this.elements.stageLabel) {
            this.elements.stageLabel.textContent = `Live AR fit: ${look.title}`;
        }
        this.elements.lookButtons.forEach((button) => {
            button.setAttribute("aria-pressed", button.dataset.look === look.slug ? "true" : "false");
        });
        this.elements.layerButtons.forEach((button) => {
            button.setAttribute("aria-pressed", button.dataset.layer === this.state.layer ? "true" : "false");
        });
    }

    async ensureTracker() {
        if (this.poseLandmarker) {
            return this.poseLandmarker;
        }
        this.setStatus("Loading live body tracking...", "text-cyan-200");
        const vision = await FilesetResolver.forVisionTasks(VISION_WASM_URL);
        this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
            baseOptions: { modelAssetPath: POSE_MODEL_URL },
            runningMode: "IMAGE",
            numPoses: 1,
            minPoseDetectionConfidence: 0.55,
            minPosePresenceConfidence: 0.55,
            minTrackingConfidence: 0.55,
            outputSegmentationMasks: true,
        });
        this.runningMode = "IMAGE";
        this.setStatus("Body tracking ready. Start the camera or upload a clear front-facing photo.", "text-emerald-300");
        return this.poseLandmarker;
    }

    async ensureRunningMode(mode) {
        if (!this.poseLandmarker || this.runningMode === mode) {
            return;
        }
        await this.poseLandmarker.setOptions({ runningMode: mode });
        this.runningMode = mode;
    }

    setEmptyState() {
        const hasSource = this.state.sourceMode !== "none";
        this.elements.empty.classList.toggle("hidden", hasSource);
        this.elements.cameraCapture.disabled = !this.state.stream;
        this.elements.cameraStop.disabled = !this.state.stream;
        this.elements.download.disabled = !hasSource;
    }

    resizeCanvas() {
        const canvas = this.elements.canvas;
        const stage = this.elements.stage;
        if (!canvas || !stage) {
            return;
        }
        const bounds = stage.getBoundingClientRect();
        const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
        const nextWidth = Math.max(1, Math.round(bounds.width * dpr));
        const nextHeight = Math.max(1, Math.round(bounds.height * dpr));
        if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
            canvas.width = nextWidth;
            canvas.height = nextHeight;
            canvas.style.width = `${bounds.width}px`;
            canvas.style.height = `${bounds.height}px`;
        }
    }

    async runPhotoDetection() {
        if (!this.state.sourceUrl || !this.elements.photo.complete) {
            return;
        }
        await this.ensureTracker();
        await this.ensureRunningMode("IMAGE");
        const result = this.poseLandmarker.detect(this.elements.photo);
        this.ingestPoseResult(result);
        this.drawCurrentFrame();
    }

    ingestPoseResult(result) {
        const landmarks = result?.landmarks?.[0];
        if (!landmarks?.length) {
            this.lastPose = null;
            this.smoothedLandmarks = null;
            this.setFitBadge("No body found yet");
            return;
        }
        const confidence = averageVisibility(landmarks, [
            LANDMARK.leftShoulder,
            LANDMARK.rightShoulder,
            LANDMARK.leftHip,
            LANDMARK.rightHip,
        ]);
        this.smoothedLandmarks = smoothLandmarks(this.smoothedLandmarks, landmarks);
        this.lastPose = {
            confidence,
            landmarks: this.smoothedLandmarks,
            maskCanvas: buildMaskCanvas(result?.segmentationMasks?.[0]),
        };
        const confidenceLabel = confidence >= 0.72 ? "Locked" : confidence >= 0.54 ? "Tracking" : "Searching";
        this.setFitBadge(`${confidenceLabel} | ${Math.round(confidence * 100)}%`);
    }

    async startCamera({ auto = false } = {}) {
        if (this.state.stream) {
            return;
        }
        if (this.cameraStartPromise) {
            return this.cameraStartPromise;
        }
        if (!window.isSecureContext) {
            this.setStatus(
                "Camera access only works on localhost or HTTPS. Open this page from a secure address and try again.",
                "text-rose-300"
            );
            return;
        }
        if (!navigator.mediaDevices?.getUserMedia) {
            this.setStatus("Camera access is not available in this browser.", "text-rose-300");
            return;
        }
        this.cameraStartPromise = (async () => {
            this.elements.cameraStart.disabled = true;
            this.setStatus(
                auto ? "Requesting camera permission..." : "Requesting camera access...",
                "text-cyan-200"
            );
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: "user",
                        width: { ideal: 1080 },
                        height: { ideal: 1350 },
                    },
                    audio: false,
                });
                this.state.stream = stream;
                this.state.sourceMode = "camera";
                this.elements.video.srcObject = stream;
                await this.elements.video.play();
                this.lastVideoTime = -1;
                this.lastDetectionAt = 0;
                this.setEmptyState();
                this.setFitBadge("Camera live | loading tracker");
                this.renderLoop();
                this.setStatus("Camera is live. Loading body tracking...", "text-cyan-200");
                try {
                    await this.ensureTracker();
                    this.setStatus("Camera is live. Tracking updates automatically while you move.", "text-emerald-300");
                } catch (trackerError) {
                    console.error("Body tracker failed after camera start:", trackerError);
                    this.setFitBadge("Camera live | tracker unavailable");
                    this.setStatus(
                        "Camera is live, but body tracking could not finish loading. Refresh to retry or upload a photo.",
                        "text-amber-300"
                    );
                }
            } catch (error) {
                this.setStatus(this.describeCameraError(error), "text-rose-300");
            } finally {
                this.elements.cameraStart.disabled = false;
                this.setEmptyState();
                this.cameraStartPromise = null;
            }
        })();
        return this.cameraStartPromise;
    }

    stopCamera() {
        if (this.state.stream) {
            this.state.stream.getTracks().forEach((track) => track.stop());
        }
        this.state.stream = null;
        this.elements.video.srcObject = null;
        this.state.sourceMode = this.state.sourceUrl ? "photo" : "none";
        this.activeLoop += 1;
        this.setEmptyState();
        this.drawCurrentFrame();
    }

    renderLoop() {
        const loopToken = ++this.activeLoop;
        const step = async () => {
            if (loopToken !== this.activeLoop || this.state.sourceMode !== "camera" || !this.state.stream) {
                return;
            }
            if (this.elements.video.readyState >= 2) {
                const now = performance.now();
                if (
                    this.poseLandmarker &&
                    this.elements.video.currentTime !== this.lastVideoTime &&
                    now - this.lastDetectionAt >= 44
                ) {
                    await this.ensureRunningMode("VIDEO");
                    const result = this.poseLandmarker.detectForVideo(this.elements.video, now);
                    this.lastDetectionAt = now;
                    this.lastVideoTime = this.elements.video.currentTime;
                    this.ingestPoseResult(result);
                }
                this.drawCurrentFrame();
            }
            window.requestAnimationFrame(step);
        };
        window.requestAnimationFrame(step);
    }

    renderFallbackOverlay(ctx, targetRect) {
        const look = this.currentLook();
        if (!look) {
            return;
        }
        const asset = this.layerAssetCache.get(`${look.slug}:full`) || this.layerAssetCache.get(`${look.slug}:top`);
        if (!asset?.raster) {
            return;
        }
        const scale = this.state.controls.scale / 100;
        const width = targetRect.w * 0.64 * scale;
        const height = width * (asset.raster.height / Math.max(asset.raster.width, 1));
        const x = targetRect.dx + (targetRect.w / 2) - (width / 2) + (targetRect.w * this.state.controls.offsetX / 100);
        const y = targetRect.dy + (targetRect.h * 0.18) + (targetRect.h * this.state.controls.offsetY / 100);
        ctx.save();
        ctx.globalAlpha = this.state.controls.opacity / 100;
        ctx.translate(x + (width / 2), y + (height / 2));
        ctx.rotate((this.state.controls.rotation * Math.PI) / 180);
        ctx.drawImage(asset.raster, -width / 2, -height / 2, width, height);
        ctx.restore();
    }

    renderGarmentLayer(ctx, asset, geometry, split = false) {
        if (!asset?.raster || !geometry) {
            return;
        }
        const sourceRect = { x: 0, y: 0, w: asset.raster.width, h: asset.raster.height };
        if (!split) {
            drawStripWarp(ctx, asset.raster, sourceRect, geometry[0], geometry[1], geometry[2], geometry[3], 8);
            return;
        }
        drawStripWarp(
            ctx,
            asset.raster,
            { x: 0, y: 0, w: sourceRect.w, h: sourceRect.h * 0.54 },
            geometry.upper[0],
            geometry.upper[1],
            geometry.upper[2],
            geometry.upper[3],
            6
        );
        drawStripWarp(
            ctx,
            asset.raster,
            { x: 0, y: sourceRect.h * 0.54, w: sourceRect.w, h: sourceRect.h * 0.46 },
            geometry.lower[0],
            geometry.lower[1],
            geometry.lower[2],
            geometry.lower[3],
            6
        );
    }

    drawCurrentFrame() {
        this.resizeCanvas();
        const canvas = this.elements.canvas;
        const ctx = canvas.getContext("2d");
        const source = this.state.sourceMode === "camera" ? this.elements.video : this.elements.photo;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#020617";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (
            this.state.sourceMode === "none" ||
            !source ||
            (this.state.sourceMode === "photo" && !this.elements.photo.complete) ||
            (this.state.sourceMode === "camera" && this.elements.video.readyState < 2)
        ) {
            this.setEmptyState();
            return;
        }

        const sourceWidth = source.videoWidth || source.naturalWidth || 1080;
        const sourceHeight = source.videoHeight || source.naturalHeight || 1350;
        const coverRect = computeCoverRect(sourceWidth, sourceHeight, canvas.width, canvas.height);
        drawImageCover(ctx, source, coverRect);

        const look = this.currentLook();
        if (!look) {
            this.setEmptyState();
            return;
        }

        if (!this.lastPose?.landmarks?.length) {
            this.renderFallbackOverlay(ctx, coverRect);
            this.setEmptyState();
            return;
        }

        const arProfile = look.try_on?.ar_profile || {};
        const garmentCanvas = createRasterCanvas(canvas.width, canvas.height);
        const garmentCtx = garmentCanvas.getContext("2d");
        garmentCtx.clearRect(0, 0, garmentCanvas.width, garmentCanvas.height);

        const scaleAdjust = this.state.controls.scale / 100;
        const offsetX = this.state.controls.offsetX / 100;
        const offsetY = this.state.controls.offsetY / 100;

        const topGeometry = buildTopGeometry(this.lastPose.landmarks, coverRect, arProfile, scaleAdjust, offsetX, offsetY);
        const bottomGeometry = buildBottomGeometry(this.lastPose.landmarks, coverRect, arProfile, scaleAdjust, offsetX, offsetY);
        const rotation = (this.state.controls.rotation * Math.PI) / 180;

        const rotatePoints = (points, center) => points.map((entry) => {
            const shifted = subtract(entry, center);
            return point(
                center.x + (shifted.x * Math.cos(rotation)) - (shifted.y * Math.sin(rotation)),
                center.y + (shifted.x * Math.sin(rotation)) + (shifted.y * Math.cos(rotation))
            );
        });

        const topAsset = this.layerAssetCache.get(`${look.slug}:top`);
        const bottomAsset = this.layerAssetCache.get(`${look.slug}:bottom`);

        if (topGeometry && (this.state.layer === "full" || this.state.layer === "top")) {
            const center = midpoint(topGeometry.shoulder[0], topGeometry.hip[1]);
            this.renderGarmentLayer(
                garmentCtx,
                topAsset,
                {
                    upper: rotatePoints([topGeometry.shoulder[0], topGeometry.shoulder[1], topGeometry.mid[1], topGeometry.mid[0]], center),
                    lower: rotatePoints([topGeometry.mid[0], topGeometry.mid[1], topGeometry.hip[1], topGeometry.hip[0]], center),
                },
                true
            );
        }

        if (bottomGeometry && (this.state.layer === "full" || this.state.layer === "bottom")) {
            const center = midpoint(bottomGeometry.waist[0], bottomGeometry.hem[1]);
            this.renderGarmentLayer(
                garmentCtx,
                bottomAsset,
                {
                    upper: rotatePoints([bottomGeometry.waist[0], bottomGeometry.waist[1], bottomGeometry.knee[1], bottomGeometry.knee[0]], center),
                    lower: rotatePoints([bottomGeometry.knee[0], bottomGeometry.knee[1], bottomGeometry.hem[1], bottomGeometry.hem[0]], center),
                },
                true
            );
        }

        if (this.lastPose.maskCanvas) {
            garmentCtx.save();
            garmentCtx.globalCompositeOperation = "destination-in";
            garmentCtx.filter = "blur(1px)";
            garmentCtx.drawImage(this.lastPose.maskCanvas, coverRect.dx, coverRect.dy, coverRect.dw, coverRect.dh);
            garmentCtx.restore();
        }

        ctx.save();
        ctx.globalAlpha = this.state.controls.opacity / 100;
        ctx.drawImage(garmentCanvas, 0, 0);
        ctx.restore();
        drawForegroundCutouts(ctx, source, coverRect, this.lastPose.landmarks);
        this.setEmptyState();
    }

    async setPhoto(sourceUrl, sourceName = "") {
        this.state.sourceUrl = sourceUrl;
        this.state.sourceName = sourceName;
        this.state.sourceMode = "photo";
        this.elements.photo.src = sourceUrl;
        await new Promise((resolve, reject) => {
            if (this.elements.photo.complete) {
                resolve();
                return;
            }
            this.elements.photo.onload = () => resolve();
            this.elements.photo.onerror = () => reject(new Error("Image preview failed to load."));
        });
        await this.runPhotoDetection();
    }

    async persistSelfie(blob, filename, scanContext = null) {
        const formData = new FormData();
        formData.append("csrf_token", this.elements.csrf?.value || "");
        formData.append("selfie", new File([blob], filename, { type: blob.type || "image/png" }));
        if (scanContext) {
            formData.append("scan_context", JSON.stringify(scanContext));
        }
        const response = await fetch(this.config.uploadUrl, { method: "POST", body: formData });
        const payload = await response.json();
        if (!payload.ok) {
            throw new Error(payload.error || "Upload failed");
        }
        this.state.sourceUrl = payload.url || this.state.sourceUrl;
        this.state.sourceName = payload.filename || filename;
        this.applySuggestionPayload(payload);
        return payload;
    }

    async handleFile(file) {
        if (!file) {
            return;
        }
        const previewUrl = URL.createObjectURL(file);
        try {
            await this.setPhoto(previewUrl, file.name);
            const scanContext = this.updateLocalSuggestions();
            this.setStatus("Saving selfie and fitting the AR layer...", "text-cyan-200");
            await this.persistSelfie(file, file.name, scanContext);
            this.setStatus(`AR photo saved${this.state.sourceName ? `: ${this.state.sourceName}` : ""}. Scan suggestions are ready below.`, "text-emerald-300");
            window.sbToast?.("AR photo saved.");
        } catch (error) {
            this.renderSuggestionPanel();
            this.setStatus(`Using local preview only. ${error.message}`, "text-rose-300");
        }
    }

    async captureFrame() {
        if (!this.state.stream || this.elements.video.readyState < 2) {
            return;
        }
        const canvas = createRasterCanvas(this.elements.video.videoWidth || 1080, this.elements.video.videoHeight || 1350);
        const ctx = canvas.getContext("2d");
        ctx.drawImage(this.elements.video, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png", 0.96));
        if (!blob) {
            this.setStatus("Could not capture the current frame.", "text-rose-300");
            return;
        }
        const filename = `stylebridge-ar-${Date.now()}.png`;
        const previewUrl = URL.createObjectURL(blob);
        this.stopCamera();
        try {
            await this.setPhoto(previewUrl, filename);
            const scanContext = this.updateLocalSuggestions();
            this.setStatus("Saving the captured AR frame...", "text-cyan-200");
            await this.persistSelfie(blob, filename, scanContext);
            this.setStatus("Captured frame saved to your account. Scan suggestions are ready below.", "text-emerald-300");
            window.sbToast?.("Frame captured.");
        } catch (error) {
            this.renderSuggestionPanel();
            this.setStatus(`Using the captured frame locally only. ${error.message}`, "text-rose-300");
        }
    }

    downloadPreview() {
        if (this.state.sourceMode === "none") {
            this.setStatus("Add a photo or start the camera before exporting.", "text-rose-300");
            return;
        }
        const link = document.createElement("a");
        link.href = this.elements.canvas.toDataURL("image/png");
        link.download = `${this.currentLook()?.slug || "stylebridge"}-ar-preview.png`;
        link.click();
        this.setStatus("AR preview downloaded.", "text-emerald-300");
        window.sbToast?.("Preview exported.");
    }

    async switchLook(slug) {
        this.state.look = slug;
        this.applyLookCalibration();
        await this.loadLookAssets(this.currentLook());
        this.renderLookMeta();
        if (this.state.sourceMode === "photo") {
            await this.runPhotoDetection();
        } else {
            this.drawCurrentFrame();
        }
    }

    bindEvents() {
        this.elements.lookButtons.forEach((button) => {
            button.addEventListener("click", () => {
                this.switchLook(button.dataset.look);
            });
        });
        this.elements.layerButtons.forEach((button) => {
            button.addEventListener("click", () => {
                this.state.layer = button.dataset.layer;
                this.renderLookMeta();
                this.drawCurrentFrame();
            });
        });
        [
            ["scale", "scale"],
            ["offsetX", "offsetX"],
            ["offsetY", "offsetY"],
            ["rotation", "rotation"],
            ["opacity", "opacity"],
        ].forEach(([id, key]) => {
            this.elements[id].addEventListener("input", () => {
                this.state.controls[key] = Number(this.elements[id].value);
                this.syncControls();
                this.drawCurrentFrame();
            });
        });
        this.elements.form.addEventListener("submit", async (event) => {
            event.preventDefault();
            await this.handleFile(this.elements.file.files?.[0]);
        });
        this.elements.file.addEventListener("change", async () => {
            await this.handleFile(this.elements.file.files?.[0]);
        });
        this.elements.cameraStart.addEventListener("click", () => this.startCamera());
        this.elements.cameraStop.addEventListener("click", () => {
            this.stopCamera();
            this.setStatus("Camera stopped.", "text-slate-400");
        });
        this.elements.cameraCapture.addEventListener("click", () => this.captureFrame());
        this.elements.download.addEventListener("click", () => this.downloadPreview());
        this.elements.resetFit.addEventListener("click", () => {
            this.applyLookCalibration();
            this.drawCurrentFrame();
        });
        this.elements.liftFit.addEventListener("click", () => {
            this.state.controls.offsetY = clamp(this.state.controls.offsetY - 3, -18, 18);
            this.syncControls();
            this.drawCurrentFrame();
        });
        this.elements.dropFit.addEventListener("click", () => {
            this.state.controls.offsetY = clamp(this.state.controls.offsetY + 3, -18, 18);
            this.syncControls();
            this.drawCurrentFrame();
        });
        window.addEventListener("resize", () => this.drawCurrentFrame());
        window.addEventListener("pagehide", () => this.stopCamera());
        if ("ResizeObserver" in window) {
            this.resizeObserver = new ResizeObserver(() => this.drawCurrentFrame());
            this.resizeObserver.observe(this.elements.stage);
        }
    }

    queueAutoCameraStart() {
        if (this.autoCameraQueued || this.config.autoStartCamera === false) {
            return;
        }
        this.autoCameraQueued = true;
        const requestCamera = () => {
            window.setTimeout(() => {
                this.startCamera({ auto: true });
            }, 180);
        };
        if (document.visibilityState === "visible") {
            requestCamera();
            return;
        }
        const onVisible = () => {
            if (document.visibilityState !== "visible") {
                return;
            }
            document.removeEventListener("visibilitychange", onVisible);
            requestCamera();
        };
        document.addEventListener("visibilitychange", onVisible);
    }

    async init() {
        this.applyLookCalibration();
        this.syncControls();
        this.bindEvents();
        await this.loadLookAssets(this.currentLook());
        this.renderLookMeta();
        this.renderSuggestionPanel();
        this.setFitBadge("Tracker warming up");
        if (this.state.sourceUrl) {
            try {
                await this.setPhoto(this.state.sourceUrl, this.state.sourceName);
                if (!this.state.suggestions.length) {
                    this.updateLocalSuggestions();
                } else {
                    this.renderSuggestionPanel();
                }
                this.queueAutoCameraStart();
            } catch {
                this.setStatus("Saved photo could not be loaded. Upload a new selfie to start tracking.", "text-rose-300");
                this.queueAutoCameraStart();
            }
        } else {
            this.setStatus("Requesting camera permission. If the browser does not prompt, click Allow camera.", "text-cyan-200");
            this.drawCurrentFrame();
            this.queueAutoCameraStart();
        }
    }
}

export async function bootTryOnStudio(config) {
    const studio = new TryOnStudio(config);
    try {
        await studio.init();
    } catch (error) {
        console.error("Try-on studio failed to boot:", error);
        const status = document.getElementById("status");
        if (status) {
            status.textContent = "The AR tracker could not start on this device. Try refreshing or using a newer browser.";
            status.className = "mt-3 text-sm text-rose-300";
        }
        const fitBadge = document.getElementById("fitBadge");
        if (fitBadge) {
            fitBadge.textContent = "AR unavailable";
        }
    }
    return studio;
}
