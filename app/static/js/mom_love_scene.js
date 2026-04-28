(function () {
  const canvas = document.getElementById("love-scene");
  if (!canvas || typeof window.THREE === "undefined") {
    return;
  }

  const THREE = window.THREE;

  function supportsWebGL() {
    try {
      const testCanvas = document.createElement("canvas");
      return Boolean(
        window.WebGLRenderingContext &&
        (testCanvas.getContext("webgl") || testCanvas.getContext("experimental-webgl"))
      );
    } catch {
      return false;
    }
  }

  if (!supportsWebGL()) {
    return;
  }

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight, false);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0.4, 8.5);

  const ambient = new THREE.AmbientLight(0xffffff, 1.1);
  scene.add(ambient);

  const pinkLight = new THREE.PointLight(0xff78b7, 2.2, 30, 2);
  pinkLight.position.set(4, 5, 5);
  scene.add(pinkLight);

  const redLight = new THREE.PointLight(0xff5b8f, 1.4, 20, 2);
  redLight.position.set(-5, -1, 4);
  scene.add(redLight);

  const heartShape = new THREE.Shape();
  heartShape.moveTo(0, 0.35);
  heartShape.bezierCurveTo(0, 0.85, -0.8, 1.15, -1.15, 0.45);
  heartShape.bezierCurveTo(-1.45, -0.15, -0.75, -0.85, 0, -1.45);
  heartShape.bezierCurveTo(0.75, -0.85, 1.45, -0.15, 1.15, 0.45);
  heartShape.bezierCurveTo(0.8, 1.15, 0, 0.85, 0, 0.35);

  const heartGeometry = new THREE.ExtrudeGeometry(heartShape, {
    depth: 0.34,
    bevelEnabled: true,
    bevelSegments: 4,
    steps: 1,
    bevelSize: 0.08,
    bevelThickness: 0.08,
  });
  heartGeometry.center();

  const mainHeart = new THREE.Mesh(
    heartGeometry,
    new THREE.MeshPhysicalMaterial({
      color: 0xff7fb8,
      emissive: 0x5d102f,
      emissiveIntensity: 0.45,
      roughness: 0.22,
      metalness: 0.1,
      clearcoat: 0.9,
      clearcoatRoughness: 0.14,
    })
  );
  mainHeart.scale.setScalar(1.35);
  scene.add(mainHeart);

  const hearts = [];
  const colors = [0xffa0ce, 0xff7fb8, 0xff90c9, 0xff5d8f, 0xffc1dd];

  for (let i = 0; i < 10; i += 1) {
    const heart = new THREE.Mesh(
      heartGeometry,
      new THREE.MeshPhysicalMaterial({
        color: colors[i % colors.length],
        emissive: 0x3d0b24,
        emissiveIntensity: 0.35,
        roughness: 0.3,
        metalness: 0.06,
        clearcoat: 0.7,
        clearcoatRoughness: 0.18,
        transparent: true,
        opacity: 0.95,
      })
    );

    const angle = (i / 10) * Math.PI * 2;
    const radius = 2.2 + (i % 2) * 0.8;
    heart.position.set(Math.cos(angle) * radius, Math.sin(angle * 1.3) * 1.15, Math.sin(angle) * 1.5);
    heart.rotation.x = Math.random() * 0.8;
    heart.rotation.y = Math.random() * 0.8;
    heart.scale.setScalar(0.28 + (i % 3) * 0.07);
    heart.userData = {
      angle,
      radius,
      speed: 0.22 + i * 0.025,
      lift: 0.15 + (i % 4) * 0.04,
    };
    hearts.push(heart);
    scene.add(heart);
  }

  const particleCount = 140;
  const particleGeometry = new THREE.BufferGeometry();
  const particlePositions = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount; i += 1) {
    particlePositions[i * 3] = (Math.random() - 0.5) * 18;
    particlePositions[i * 3 + 1] = (Math.random() - 0.25) * 14;
    particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 10;
  }

  particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));

  const particles = new THREE.Points(
    particleGeometry,
    new THREE.PointsMaterial({
      color: 0xffdceb,
      size: 0.07,
      transparent: true,
      opacity: 0.85,
    })
  );
  scene.add(particles);

  const pointer = { x: 0, y: 0 };

  function onPointerMove(event) {
    pointer.x = (event.clientX / window.innerWidth - 0.5) * 2;
    pointer.y = (event.clientY / window.innerHeight - 0.5) * 2;
  }

  function onResize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  }

  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("resize", onResize);

  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);

    const elapsed = clock.getElapsedTime();

    mainHeart.rotation.y = elapsed * 0.55;
    mainHeart.rotation.x = Math.sin(elapsed * 0.8) * 0.12;
    mainHeart.position.y = Math.sin(elapsed * 1.4) * 0.12;

    hearts.forEach((heart, index) => {
      const data = heart.userData;
      const angle = data.angle + elapsed * data.speed;
      heart.position.x = Math.cos(angle) * data.radius;
      heart.position.z = Math.sin(angle) * 1.8;
      heart.position.y = Math.sin(elapsed * 1.5 + index) * data.lift;
      heart.rotation.y += 0.01;
      heart.rotation.x += 0.006;
    });

    particles.rotation.y = elapsed * 0.02;
    particles.rotation.x = Math.sin(elapsed * 0.12) * 0.08;

    camera.position.x += (pointer.x * 0.6 - camera.position.x) * 0.02;
    camera.position.y += (-pointer.y * 0.25 + 0.4 - camera.position.y) * 0.02;
    camera.lookAt(0, 0.15, 0);

    renderer.render(scene, camera);
  }

  animate();
})();
