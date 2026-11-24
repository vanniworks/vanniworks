// The two creatures of the contributions panel, in 3D (three.js), rendered once by
// scripts/bake.mjs into pictures. Faceted dark metal, burning eyes and chest core, curved
// horns, an orange wire glow along their edges: built to sit with the metal V on vanniworks.com.
// Everything is in the panel's own units (px, y down, the figure box is 160 x 330), drawn
// with an orthographic camera, so what's rendered lands exactly where contrib.py places it.
//   render({ side: 'L' | 'R', part: 'body' | 'arm' | 'flash' }) draws one piece and returns
//   its box and the points the panel needs (eyes, chest, shoulder, hand), in panel units.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const FW = 160;
const PAL = {
  L: { glow: '#ffd23a', core: '#ff8a1f', metal: '#2a1d14', rim: '#ffb347' },
  R: { glow: '#f0402a', core: '#ff8a1f', metal: '#241311', rim: '#ff5a2a' },
};
// the panel's y runs down; three's runs up
const P = (x, y, z = 0) => new THREE.Vector3(x, -y, z);

function materials(pal, env, flash) {
  if (flash) {
    const m = new THREE.MeshBasicMaterial({ color: '#fff1c2' });
    return { metal: m, dark: m, glow: m, core: m, edge: new THREE.LineBasicMaterial({ color: '#fff1c2' }) };
  }
  return {
    metal: new THREE.MeshStandardMaterial({ color: pal.metal, metalness: 0.75, roughness: 0.38, flatShading: true, envMap: env, envMapIntensity: 0.9 }),
    dark: new THREE.MeshStandardMaterial({ color: '#120b08', metalness: 0.6, roughness: 0.55, flatShading: true, envMap: env, envMapIntensity: 0.6 }),
    glow: new THREE.MeshBasicMaterial({ color: new THREE.Color(pal.glow).multiplyScalar(1.1) }),
    core: new THREE.MeshBasicMaterial({ color: new THREE.Color(pal.core).multiplyScalar(1.15) }),
    edge: new THREE.LineBasicMaterial({ color: pal.glow, transparent: true, opacity: 0.55 }),
  };
}

// a faceted solid with its edges traced in light
function solid(geo, mat, M, at, scale = [1, 1, 1], rot = [0, 0, 0]) {
  const g = new THREE.Group();
  const mesh = new THREE.Mesh(geo, mat);
  g.add(mesh);
  if (mat !== M.glow && mat !== M.core) g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), M.edge));
  g.position.copy(at);
  g.scale.set(...scale);
  g.rotation.set(...rot);
  return g;
}

// a horn: cones along a curve, thinner toward the tip
function horn(M, p0, p1, p2, r0) {
  const curve = new THREE.QuadraticBezierCurve3(P(...p0), P(...p1), P(...p2));
  const g = new THREE.Group();
  const N = 7;
  for (let i = 0; i < N; i++) {
    const a = curve.getPoint(i / N);
    const b = curve.getPoint((i + 1) / N);
    const len = a.distanceTo(b);
    const r = r0 * (1 - i / N) + 1.2;
    const geo = new THREE.CylinderGeometry(r * 0.78, r, len * 1.15, 6);
    const seg = solid(geo, i > N - 3 ? M.glow : M.metal, M, a.clone().lerp(b, 0.5));
    seg.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    g.add(seg);
  }
  return g;
}

function limb(M, from, to, r0, r1, mat) {
  const a = P(...from);
  const b = P(...to);
  const geo = new THREE.CylinderGeometry(r1, r0, a.distanceTo(b), 7);
  const s = solid(geo, mat || M.metal, M, a.clone().lerp(b, 0.5));
  s.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
  return s;
}

// the creature, facing right (+x), in panel units
function body(M) {
  const g = new THREE.Group();
  // legs: thighs, shins, clawed feet
  for (const [hx, kx, fx, z] of [[64, 58, 46, -10], [100, 108, 118, 10]]) {
    g.add(limb(M, [hx, 214], [kx, 262], 15, 11, M.metal));
    g.add(limb(M, [kx, 262], [fx, 312], 11, 8, M.dark));
    g.add(solid(new THREE.OctahedronGeometry(11, 0), M.metal, M, P(fx + 6, 318, z), [1.6, 0.55, 1]));
    g.add(solid(new THREE.SphereGeometry(8, 6, 4), M.dark, M, P(kx, 262, z)));
  }
  // hips and a heavy, hunched torso
  g.add(solid(new THREE.IcosahedronGeometry(30, 0), M.dark, M, P(82, 206), [1.25, 0.6, 0.9]));
  g.add(solid(new THREE.IcosahedronGeometry(44, 0), M.metal, M, P(86, 156), [1.0, 1.15, 0.8], [0.2, 0.3, -0.15]));
  // the burning core in the chest
  g.add(solid(new THREE.OctahedronGeometry(12, 0), M.core, M, P(98, 158, 30), [1, 1.3, 1]));
  // shoulder plates with spikes
  for (const [x, y, s] of [[124, 122, 1], [48, 126, 0.85]]) {
    g.add(solid(new THREE.DodecahedronGeometry(17 * s, 0), M.metal, M, P(x, y)));
    g.add(solid(new THREE.ConeGeometry(6 * s, 22 * s, 5), M.dark, M, P(x - 2, y - 18 * s), [1, 1, 1], [0, 0, 0.3]));
  }
  // the hanging arm, the one that doesn't throw: shoulder, elbow, claws
  g.add(limb(M, [48, 130], [34, 182], 10, 8));
  g.add(limb(M, [34, 182], [30, 226], 8, 6, M.dark));
  for (const dx of [-5, 0, 5]) g.add(limb(M, [30, 226], [26 + dx, 244], 3, 0.8, M.glow));
  // neck and head: a faceted skull, a jaw, burning eyes
  g.add(limb(M, [84, 120], [88, 102], 14, 12, M.dark));
  g.add(solid(new THREE.DodecahedronGeometry(27, 0), M.metal, M, P(88, 82), [1.05, 1.0, 0.95], [0.1, 0.4, 0]));
  g.add(solid(new THREE.TetrahedronGeometry(20, 0), M.dark, M, P(96, 104, 6), [1.2, 0.5, 0.9], [0.3, 0.8, 0]));
  for (const ex of [80, 97]) g.add(solid(new THREE.BoxGeometry(11, 3.5, 4), M.glow, M, P(ex, 84, 25)));
  // horns, on the old horns' curves
  g.add(horn(M, [70, 64], [34, 46], [26, 4], 9));
  g.add(horn(M, [98, 62], [132, 40], [128, 0], 9));
  // a spined tail curling behind
  const tail = new THREE.QuadraticBezierCurve3(P(60, 214, -12), P(10, 250, -20), P(14, 300, -10));
  for (let i = 0; i < 6; i++) {
    const a = tail.getPoint(i / 6);
    g.add(solid(new THREE.OctahedronGeometry(8 - i, 0), i > 3 ? M.glow : M.dark, M, a));
  }
  return g;
}

// the throwing arm, from its shoulder pivot (0, 0): up and forward, three glowing claws
function arm(M) {
  const g = new THREE.Group();
  g.add(limb(M, [0, 0], [22, -26], 11, 9));
  g.add(solid(new THREE.SphereGeometry(8, 6, 4), M.dark, M, P(22, -26)));
  g.add(limb(M, [22, -26], [42, -46], 9, 7, M.dark));
  for (const [dx, dy] of [[14, -8], [16, 0], [6, -16]]) g.add(limb(M, [42, -46], [42 + dx, -46 + dy], 3.2, 0.8, M.glow));
  return g;
}

export async function render({ side, part }) {
  const pal = PAL[side];
  const facing = side === 'L' ? 1 : -1;
  const isArm = part === 'arm';
  // the box to draw, in panel units (with room for the horns and a swinging arm)
  const box = isArm ? (facing === 1 ? { x: -24, y: -78, w: 96, h: 100 } : { x: -72, y: -78, w: 96, h: 100 }) : { x: -26, y: -16, w: 212, h: 356 };
  const S = 2;
  const canvas = document.createElement('canvas');
  document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(S);
  renderer.setSize(box.w, box.h);
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  const pm = new THREE.PMREMGenerator(renderer);
  const env = pm.fromScene(new RoomEnvironment(), 0.04).texture;

  const M = materials(pal, env, part === 'flash');
  const model = isArm ? arm(M) : body(M);
  // turned a little toward you, so it reads in depth; the left one faces right, the right one left
  const rig = new THREE.Group();
  const pivot = isArm ? new THREE.Vector3(0, 0, 0) : P(FW / 2, 0);
  model.position.sub(pivot);
  rig.add(model);
  rig.position.copy(pivot);
  rig.rotation.y = isArm ? -0.35 : -0.45;
  if (facing === -1) {
    // mirrored about the figure box's middle (the arm about its pivot)
    rig.scale.x = -1;
    rig.rotation.y *= -1;
    if (!isArm) rig.position.x = FW - pivot.x;
  }
  scene.add(rig);

  // light: a warm key from the front, a rim from the side facing the opponent, a dim fill
  scene.add(new THREE.HemisphereLight('#4a3020', '#000000', 0.6));
  const key = new THREE.DirectionalLight('#ffe2c0', 2.2);
  key.position.set(60 * facing, 120, 200);
  const rim = new THREE.DirectionalLight(pal.rim, 3.2);
  rim.position.set(220 * facing, 40, -120);
  const back = new THREE.DirectionalLight(pal.glow, 1.4);
  back.position.set(-180 * facing, 60, -160);
  scene.add(key, rim, back);

  const cam = new THREE.OrthographicCamera(box.x, box.x + box.w, -box.y, -(box.y + box.h), -2000, 2000);
  cam.position.z = 1000;
  renderer.render(scene, cam);

  // where the panel needs to know things are, projected
  const at = (v) => {
    const p = v.clone();
    rig.updateMatrixWorld(true);
    model.localToWorld(p);
    return [Math.round(p.x * 10) / 10, Math.round(-p.y * 10) / 10];
  };
  const points = isArm
    ? { hand: at(P(54, -54)) }
    : { eyes: [at(P(80, 84, 25)), at(P(97, 84, 25))], chest: at(P(98, 158, 30)), shoulder: at(P(124, 122)) };
  return { box, points };
}
