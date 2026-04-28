# Satin Slip Dress - Runway Edition

This is the working asset brief for the StyleBridge hero model and the scene controls on the landing page.

## Garment

A sleek, bias-cut midi slip dress in liquid satin. The silhouette uses thin spaghetti straps, a deep V neckline, and a softly flared hem that lands around mid-calf. The dress should read as close through the bust and waist, then release into a natural, weighted drape through the skirt.

## Target Technical Standard

- Format: one compressed `.glb` file using glTF 2.0 binary
- Dress triangles: 40,000 to 80,000 max
- Total scene budget: under 150,000 triangles with a simple mannequin/avatar
- Texture set: base color, metallic-roughness, normal, and optional opacity/alpha
- Texture resolution: 1024 to 2048 max per map
- Animation: one baked runway walk loop plus one idle pose
- Fit states: at least 2 to 3 size variants or morph targets
- Delivery target: under 5 MB compressed with Draco and Meshopt

## Why This Dress

- Satin shows motion and lighting better than a stiffer garment
- A bias cut makes bust, waist, and hip fit cues easier to communicate
- It is premium enough for fashion teams but still practical to optimize for web

## Current Repo Status

- The landing page now ships a custom `satin-slip-dress.glb` asset with a simple avatar, a baked runway loop, and `size2` / `size10` morph targets
- The scene runtime in `app/static/js/three_scene.js` now preserves the imported PBR maps, plays the embedded runway animation, and maps the fit controls to morph target weights
- The poster fallback in `app/static/images/satin-slip-poster.jpg` reflects the live emerald satin runway variant

## Drop-In Asset Path

The current runtime GLB lives at:

`app/static/models/satin-slip-dress.glb`

## Current Delivery

- Format: glTF 2.0 binary (`.glb`)
- Dress triangles: about 46k
- Total scene triangles: about 49k
- Texture set: 1024 base color, metallic-roughness, and normal maps
- Animation: one 10-second looping runway walk clip
- Fit states: embedded `size2` and `size10` morph targets with `size6` as the base state
- Runtime variants: deep emerald liquid satin, black matte silk, and champagne pearl
