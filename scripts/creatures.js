// The two fighters of the contributions panel, rendered once by scripts/bake.mjs.
// The model is RobotExpressive by Tomás Laulhé (CC0; from the three.js examples), restyled:
// dark gunmetal armour, polished brass on the left fighter and crimson steel on the right,
// lit like the metal V on vanniworks.com. Its own animations drive the fight: a breathing
// idle, a punch that launches the cube from the actual fist, and a stagger when it's hit.
// Each fighter becomes one strip of frames (idle loop, punch, hit) that the SVG steps through.
//   strip({ side: 'L' | 'R' }) returns the strip as a webp data URL, the frame box (panel
//   units: px, y down, the figure box is 160 x 330), the frame counts, the punch frame where
//   the fist is furthest out, and where the fist and the chest are.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const BOX = { x: -40, y: -6, w: 240, h: 346 }; // one frame, panel units
const S = 1.25; // pixels per unit
const IDLE = 6;
const PUNCH = 8;
const HIT = 8;
const ACCENT = { L: '#b8913e', R: '#a3301d' };
const RIM = { L: '#ffc861', R: '#ff5a2a' };

export async function strip({ side }) {
  const facing = side === 'L' ? 1 : -1;
  const W = Math.round(BOX.w * S);
  const H = Math.round(BOX.h * S);
  const canvas = document.createElement('canvas');
  document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H);
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  const scene = new THREE.Scene();
  const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;

  const gltf = await new GLTFLoader().loadAsync('/assets/src/models/RobotExpressive.glb');
  const robot = gltf.scene;

  // the restyle: armour plates, accent metal, black joints, and a hit flash on demand
  const flashable = [];
  robot.traverse((o) => {
    if (!o.isMesh) return;
    const name = o.material.name;
    const mat =
      name === 'Main'
        ? new THREE.MeshStandardMaterial({ color: '#2c2825', metalness: 0.88, roughness: 0.3 })
        : name === 'Grey'
          ? new THREE.MeshStandardMaterial({ color: ACCENT[side], metalness: 0.95, roughness: 0.24 })
          : new THREE.MeshStandardMaterial({ color: '#0b0a09', metalness: 0.5, roughness: 0.35 });
    mat.envMap = env;
    mat.envMapIntensity = 1.1;
    mat.emissive = new THREE.Color('#fff1c2');
    mat.emissiveIntensity = 0;
    mat.morphTargets = true;
    o.material = mat;
    flashable.push(mat);
  });

  // size it to stand in the figure box: feet on the box's floor (330), about 300 tall
  const pose = new THREE.AnimationMixer(robot);
  const clip = (n) => gltf.animations.find((a) => a.name === n);
  const at = (name, t) => {
    pose.stopAllAction();
    const a = pose.clipAction(clip(name));
    a.reset().play();
    pose.setTime(t);
    robot.updateMatrixWorld(true);
  };
  at('Idle', 0);
  const bb = new THREE.Box3().setFromObject(robot);
  const k = 300 / (bb.max.y - bb.min.y);
  const rig = new THREE.Group();
  rig.add(robot);
  rig.scale.setScalar(k);
  // panel y runs down: the rig stands on y = -330 in three's space, in the box's middle
  rig.position.set(80, -330 - bb.min.y * k, 0);
  // turned toward the opponent, three-quarters to the camera
  rig.rotation.y = facing * (Math.PI / 2 - 0.62);
  scene.add(rig);

  // light: a warm key, a rim in the fighter's colour from the opponent's side, a cool back
  scene.add(new THREE.HemisphereLight('#5a4030', '#050302', 0.7));
  const key = new THREE.DirectionalLight('#ffe8cc', 2.4);
  key.position.set(40 * facing, 160, 240);
  const rim = new THREE.DirectionalLight(RIM[side], 4.5);
  rim.position.set(260 * facing, 80, -140);
  const back = new THREE.DirectionalLight('#ff8a1f', 1.6);
  back.position.set(-220 * facing, 120, -200);
  scene.add(key, rim, back);

  const cam = new THREE.OrthographicCamera(BOX.x, BOX.x + BOX.w, -BOX.y, -(BOX.y + BOX.h), -3000, 3000);
  cam.position.z = 1500;

  const bone = (n) => robot.getObjectByName(n);
  const where = (n) => {
    const p = new THREE.Vector3();
    bone(n).getWorldPosition(p);
    return [Math.round(p.x * 10) / 10, Math.round(-p.y * 10) / 10];
  };

  // the frames: idle loop, punch, hit (staggering back and recovering, flashing at first)
  const frames = [];
  for (let i = 0; i < IDLE; i++) frames.push({ clip: 'Idle', t: (i / IDLE) * 3.33 });
  for (let i = 0; i < PUNCH; i++) frames.push({ clip: 'Punch', t: (i / (PUNCH - 1)) * 0.8 });
  // the hit: rocked back on its heels and recovering (degrees of lean), flashing at first
  const lean = [10, 17, 20, 17, 12, 7, 3, 1];
  for (let i = 0; i < HIT; i++) frames.push({ clip: 'Idle', t: 0.3 + i * 0.05, lean: lean[i], flash: i < 2 ? 0.9 - i * 0.45 : 0 });

  const sheet = document.createElement('canvas');
  sheet.width = W * frames.length;
  sheet.height = H;
  const ctx = sheet.getContext('2d');
  let reach = -Infinity;
  let punchAt = 0;
  let hand = [0, 0];
  let chest = [0, 0];
  frames.forEach((f, i) => {
    at(f.clip, f.t);
    flashable.forEach((m) => (m.emissiveIntensity = f.flash || 0));
    // leaning away from the opponent, pivoting on the heels, pushed back a little
    const lean = THREE.MathUtils.degToRad(f.lean || 0);
    rig.rotation.z = lean * facing;
    rig.position.x = 80 - (f.lean || 0) * 0.9 * facing;
    renderer.render(scene, cam);
    ctx.drawImage(canvas, i * W, 0);
    if (f.clip === 'Idle' && i === 0) chest = where('Torso');
    if (f.clip === 'Punch') {
      // the fist that goes furthest toward the opponent, at the frame it's furthest
      for (const h of ['Palm2R', 'Palm2L']) {
        const p = where(h);
        if (p[0] * facing > reach) {
          reach = p[0] * facing;
          punchAt = i - IDLE;
          hand = p;
        }
      }
    }
  });
  return {
    href: sheet.toDataURL('image/webp', 0.82),
    box: BOX,
    frames: { idle: IDLE, punch: PUNCH, hit: HIT },
    punchAt,
    points: { hand, chest },
  };
}
