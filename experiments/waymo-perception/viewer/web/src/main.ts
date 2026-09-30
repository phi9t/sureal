import * as THREE from "three";
import { CSS2DRenderer } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { fetchJson, listScenes, TrackIndex, type Scene, type Tracks } from "./data/bundle";
import { FrameLoader } from "./data/loader";
import { Boxes } from "./scene/boxes";
import { Cameras } from "./scene/cameras";
import { Ego } from "./scene/ego";
import { Keypoints } from "./scene/keypoints";
import { PointClouds } from "./scene/points";
import { makeWaymoRoot } from "./scene/root";
import { PostFX } from "./render/postfx";
import { Rigs } from "./render/rigs";
import { initialState, Store, type ColorMode, type Rig } from "./state";
import { buildPanel } from "./ui/panel";
import { Hud } from "./ui/hud";
import { Timeline } from "./ui/timeline";
import { Panels } from "./ui/panels";

const $ = (id: string) => document.getElementById(id)!;

async function chooseScene(): Promise<string> {
  const params = new URLSearchParams(location.search);
  const direct = params.get("bundle");
  if (direct) return direct.endsWith("/") ? direct : direct + "/";
  const msg = $("splash-msg");
  const list = $("scene-list");
  try {
    const scenes = await listScenes();
    if (!scenes.length) {
      msg.textContent = "No bundles found. Run `run.sh export SLICE CONTEXT` first, then reload.";
      return new Promise(() => {});
    }
    msg.textContent = "Choose a scene";
    return new Promise((resolve) => {
      for (const s of scenes) {
        const b = document.createElement("button");
        b.innerHTML = `${s.context}<small>${s.slice}</small>`;
        b.addEventListener("click", () => {
          history.replaceState(null, "", `?bundle=${encodeURIComponent(s.url)}`);
          resolve(s.url);
        });
        list.append(b);
      }
    });
  } catch (e) {
    msg.textContent = `Could not list bundles (${String(e)}). Pass ?bundle=/bundles/<slice>/<context>/`;
    return new Promise(() => {});
  }
}

async function main(): Promise<void> {
  const base = await chooseScene();
  $("splash-msg").textContent = "Loading scene…";
  const scene = await fetchJson<Scene>(base + "scene.json");
  const tracks = new TrackIndex(await fetchJson<Tracks>(base + scene.tracks));
  $("splash").classList.add("hidden");

  const store = new Store(initialState);
    const canvas = $("gl") as HTMLCanvasElement;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setClearColor(new THREE.Color("#05070c"), 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  const three = new THREE.Scene();
  three.background = new THREE.Color("#05070c");
  const labels = new CSS2DRenderer({ element: $("labels") });

  const root = makeWaymoRoot();
  three.add(root);
  const resolution = new THREE.Vector2(1, 1);
  const points = new PointClouds(scene);
  const boxes = new Boxes(scene, tracks, resolution);
  const cameras = new Cameras(scene);
  const ego = new Ego(scene);
  const keypoints = new Keypoints(scene, resolution);
  root.add(points.group, boxes.group, cameras.group, ego.group, keypoints.group);

  const rigs = new Rigs(scene, canvas);
  const fx = new PostFX(renderer, three, rigs.active);
  const loader = new FrameLoader(base, scene);
  (window as unknown as { __viewer: unknown }).__viewer = { store, scene, rigs, loader, tracks, root, THREE };
  loader.onEvict = (f) => points.dispose(f);
  const hud = new Hud($("hud"), scene);
  const timeline = new Timeline($("timeline"), store, scene);
  const panels = new Panels($("strip"), $("focus"), store, scene, loader);
  buildPanel($("panel"), store, scene);

  const resize = () => {
    const w = window.innerWidth, h = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setSize(w, h, false);
    labels.setSize(w, h);
    fx.setSize(w, h, dpr);
    rigs.resize(w, h);
    resolution.set(w * dpr, h * dpr);
    boxes.setResolution(resolution);
    keypoints.setResolution(resolution);
  };
  window.addEventListener("resize", resize);
  resize();

  // Initial framing on the ego.
  rigs.snapToEgo(ego.positions[0]);
  loader.setCursor(0, 1);
  let groundSet = false;

  store.subscribe((s) => s.frame, (f, prev) => loader.setCursor(f, f >= (prev ?? 0) ? 1 : -1));
  store.subscribe((s) => s.rig + ":" + s.povCamera, () => {
    const s = store.get();
    rigs.setMode(s.rig, s.povCamera, ego.positions[s.frame], ego.yawAt(s.frame));
    fx.setCamera(rigs.active);
  });
  store.subscribe((s) => s.bloom, (v) => (fx.bloom.strength = v));
  store.subscribe((s) => s.uiHidden, (v) => document.body.classList.toggle("ui-hidden", v));
  loader.onLoaded = () => (timeline.cached = new Set(loader.cachedFrames()), timeline.draw());

  // Keyboard.
  const modes: ColorMode[] = ["height", "intensity", "range", "rgb", "semantic", "sensor", "return"];
  const rigOrder: Rig[] = ["orbit", "follow", "bev", "pov"];
  window.addEventListener("keydown", (e) => {
    if ((e.target as HTMLElement).tagName === "INPUT" || (e.target as HTMLElement).tagName === "SELECT") return;
    const s = store.get();
    const n = scene.frames.length;
    const step = e.shiftKey ? 10 : 1;
    if (e.shiftKey && /^[1-5]$/.test(e.key === "!" ? "1" : e.key === "@" ? "2" : e.key === "#" ? "3" : e.key === "$" ? "4" : e.key === "%" ? "5" : e.key)) {
      const k = { "!": 1, "@": 2, "#": 3, $: 4, "%": 5 }[e.key] ?? Number(e.key);
      if (scene.cameras[String(k)]) store.patch({ rig: "pov", povCamera: k });
      return;
    }
    switch (e.key) {
      case " ": store.patch({ playing: !s.playing }); e.preventDefault(); break;
      case "ArrowRight": store.patch({ frame: Math.min(n - 1, s.frame + step), playing: false }); break;
      case "ArrowLeft": store.patch({ frame: Math.max(0, s.frame - step), playing: false }); break;
      case "Home": store.patch({ frame: 0 }); break;
      case "End": store.patch({ frame: n - 1 }); break;
      case ",": store.patch({ rate: Math.max(0.1, +(s.rate / 2).toFixed(2)) }); break;
      case ".": store.patch({ rate: Math.min(8, s.rate * 2) }); break;
      case "a": store.patch({ accumulate: !s.accumulate }); break;
      case "[": store.patch({ accumFrames: Math.max(2, s.accumFrames - 2) }); break;
      case "]": store.patch({ accumFrames: Math.min(40, s.accumFrames + 2) }); break;
      case "b": store.patch({ showBoxes: !s.showBoxes }); break;
      case "l": store.patch({ showLabels: !s.showLabels }); break;
      case "t": store.patch({ showTrails: !s.showTrails }); break;
      case "k": store.patch({ showKeypoints: !s.showKeypoints }); break;
      case "f": store.patch({ showFrusta: !s.showFrusta }); break;
      case "i": store.patch({ showPlanes: !s.showPlanes }); break;
      case "s": store.patch({ showSeg: !s.showSeg }); break;
      case "e": store.patch({ showEgo: !s.showEgo }); break;
      case "g": store.patch({ glow: !s.glow }); break;
      case "c": store.patch({ rig: rigOrder[(rigOrder.indexOf(s.rig) + 1) % rigOrder.length] }); break;
      case "h": store.patch({ uiHidden: !s.uiHidden }); break;
      case "Escape": store.patch({ selectedTrack: null, focusCamera: null }); break;
      case "p": screenshot(); break;
      default:
        if (/^[1-7]$/.test(e.key)) store.patch({ colorMode: modes[Number(e.key) - 1] });
    }
  });

  // Click to select a track: pick the box whose centre projects nearest the cursor.
  const raycaster = new THREE.Raycaster();
  let downAt: [number, number] | null = null;
  canvas.addEventListener("pointerdown", (e) => (downAt = [e.clientX, e.clientY]));
  canvas.addEventListener("pointerup", (e) => {
    if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 4) return;
    const s = store.get();
    const rows = tracks.byFrame.get(s.frame) ?? [];
    const m = new THREE.Matrix4().copy(root.matrix).multiply(new THREE.Matrix4().fromArray(scene.frames[s.frame].world_from_vehicle).transpose());
    const ndc = new THREE.Vector2((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
    raycaster.setFromCamera(ndc, rigs.active);
    let best: { id: string; d: number } | null = null;
    for (const b of rows) {
      const c = new THREE.Vector3(...b.c).applyMatrix4(m);
      const d = raycaster.ray.distanceToPoint(c);
      const r = Math.max(b.size[0], b.size[1], b.size[2]) * 0.6;
      if (d < r && (!best || d < best.d)) best = { id: b.id, d };
    }
    store.patch({ selectedTrack: best?.id ?? null });
  });

  function screenshot(): void {
    fx.render();
    canvas.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `waymo-${scene.lineage.context}-f${String(store.get().frame).padStart(4, "0")}.png`;
      a.click();
    });
  }

  // Playback clock and render loop.
  let last = performance.now();
  let clock = 0;
  const loop = (now: number) => {
    requestAnimationFrame(loop);
    const dt = Math.min(0.1, (now - last) / 1000);
    last = now;
    hud.tick(dt);
    const s = store.get();
    const n = scene.frames.length;
    if (s.playing) {
      clock += dt * s.rate;
      const period = 0.1;
      if (clock >= period) {
        const adv = Math.floor(clock / period);
        clock -= adv * period;
        const next = (s.frame + adv) % n;
        if (loader.has(next) || !loader.isPending(next)) store.patch({ frame: next });
      }
    }
    const state = store.get();
    const frame = state.frame;
    const data = loader.get(frame);
    if (data) {
      loader.touch(frame);
      if (!points.has(frame)) points.build(frame, data);
      if (!groundSet) {
        ego.setGroundZ(points.groundZ(data), frame);
        groundSet = true;
      }
    }
    if (state.accumulate) {
      for (let i = 1; i < state.accumFrames; i++) {
        const f = frame - i * state.accumStride;
        if (f < 0) break;
        const d = loader.get(f);
        if (d && !points.has(f)) points.build(f, d);
        else if (!d && !loader.isPending(f)) void loader.request(f);
      }
    }
    points.update(state, frame, renderer.domElement.height, rigs.isOrtho);
    boxes.update(state, frame);
    cameras.update(state, frame, data);
    ego.update(state, frame);
    keypoints.update(state, frame, data?.ann);
    panels.update(state, frame, data);
    rigs.update(dt, frame, state.povCamera, ego.positions[frame], ego.yawAt(frame));
    if (rigs.active !== fx.renderPass.camera) fx.setCamera(rigs.active);
    fx.render();
    labels.render(three, rigs.active);
    hud.render(state, { points: points.visibleCount, draws: points.drawCalls, boxes: boxes.boxCount, cached: loader.cachedFrames().length, bytes: loader.bytesUsed, loading: loader.isPending(frame), keypoints: keypoints.count });
  };
  requestAnimationFrame(loop);
}

main().catch((e) => {
  console.error(e);
  const msg = document.getElementById("splash-msg");
  if (msg) msg.textContent = `Failed: ${String(e)}`;
});
