/** Left settings panel built from plain DOM. */
import type { Scene } from "../data/bundle";
import { SENSOR_COLORS } from "../palettes";
import type { ColorMode, Rig, Store, ViewerState } from "../state";

const COLOR_MODES: [ColorMode, string][] = [
  ["height", "Height"], ["intensity", "Intensity"], ["range", "Range"], ["rgb", "Camera RGB"],
  ["semantic", "Semantic"], ["sensor", "Sensor"], ["return", "Return"],
];
const RIGS: [Rig, string][] = [["orbit", "Orbit"], ["follow", "Follow ego"], ["bev", "Bird's eye"], ["pov", "Camera POV"]];

export function buildPanel(root: HTMLElement, store: Store, scene: Scene): void {
  root.innerHTML = "";
  const h1 = document.createElement("h1");
  h1.textContent = "Waymo Perception";
  const sub = document.createElement("div");
  sub.className = "sub";
  sub.textContent = `${scene.lineage.release} · ${scene.lineage.split} · ${scene.lineage.context}`;
  root.append(h1, sub);

  const section = (title: string) => {
    const s = document.createElement("section");
    const h = document.createElement("h2");
    h.textContent = title;
    s.append(h);
    root.append(s);
    return s;
  };
  const check = (parent: HTMLElement, label: string, key: keyof ViewerState) => {
    const row = document.createElement("div");
    row.className = "row";
    const lab = document.createElement("label");
    lab.textContent = label;
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = "chk-" + key;
    lab.htmlFor = input.id;
    input.addEventListener("change", () => store.patch({ [key]: input.checked } as Partial<ViewerState>));
    store.subscribe((s) => s[key] as boolean, (v) => (input.checked = v));
    row.append(lab, input);
    parent.append(row);
  };
  const slider = (parent: HTMLElement, label: string, key: keyof ViewerState, min: number, max: number, step: number, fmt = (v: number) => v.toFixed(2)) => {
    const row = document.createElement("div");
    row.className = "row";
    const lab = document.createElement("label");
    lab.textContent = label;
    const input = document.createElement("input");
    input.type = "range";
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    const val = document.createElement("span");
    val.className = "val";
    input.addEventListener("input", () => store.patch({ [key]: Number(input.value) } as Partial<ViewerState>));
    store.subscribe((s) => s[key] as number, (v) => {
      input.value = String(v);
      val.textContent = fmt(v);
    });
    row.append(lab, input, val);
    parent.append(row);
  };
  const chips = <T extends string | number>(parent: HTMLElement, items: [T, string, string?][], isOn: (s: ViewerState, v: T) => boolean, toggle: (v: T) => void) => {
    const wrap = document.createElement("div");
    wrap.className = "chips";
    for (const [v, label, color] of items) {
      const b = document.createElement("button");
      b.className = "chip";
      b.textContent = label;
      if (color) b.style.setProperty("--chip", color);
      b.addEventListener("click", () => toggle(v));
      store.subscribe((s) => isOn(s, v), (on) => b.classList.toggle("on", on));
      wrap.append(b);
    }
    parent.append(wrap);
  };

  const pts = section("Points");
  chips(pts, COLOR_MODES.map(([m, l]) => [m, l]), (s, v) => s.colorMode === v, (v) => store.patch({ colorMode: v }));
  slider(pts, "Point size", "pointSize", 0.6, 6, 0.1, (v) => v.toFixed(1));
  const sensorItems: [number, string, string][] = Object.entries(scene.lidars).map(([k, l]) => [Number(k), l.name, SENSOR_COLORS[Number(k)]]);
  const sensorWrap = document.createElement("div");
  sensorWrap.style.marginTop = "6px";
  pts.append(sensorWrap);
  chips(sensorWrap, sensorItems, (s, v) => !!s.sensors[v], (v) => store.patch({ sensors: { ...store.get().sensors, [v]: !store.get().sensors[v] } }));
  const retWrap = document.createElement("div");
  retWrap.style.marginTop = "6px";
  pts.append(retWrap);
  chips(retWrap, [[0, "return 1", "#4fc3f7"], [1, "return 2", "#ff7043"]], (s, v) => s.returns[v], (v) => {
    const r: [boolean, boolean] = [...store.get().returns] as [boolean, boolean];
    r[v] = !r[v];
    store.patch({ returns: r });
  });
  check(pts, "Dim no-label zones", "dimNlz");
  check(pts, "Additive glow", "glow");

  const acc = section("Temporal accumulation");
  check(acc, "Accumulate frames", "accumulate");
  slider(acc, "Window", "accumFrames", 2, 40, 1, (v) => `${v}f`);
  slider(acc, "Stride", "accumStride", 1, 5, 1, (v) => `${v}`);

  const lab = section("Labels");
  check(lab, "3D boxes", "showBoxes");
  check(lab, "Track labels", "showLabels");
  check(lab, "Trails", "showTrails");
  check(lab, "Speed vectors", "showSpeed");
  const classItems: [number, string, string][] = Object.entries(scene.palettes.box_types).filter(([k]) => k !== "0").map(([k, n]) => [Number(k), n.toLowerCase(), scene.palettes.box_colors[k]]);
  chips(lab, classItems, (s, v) => s.classFilter[v] !== false, (v) => store.patch({ classFilter: { ...store.get().classFilter, [v]: store.get().classFilter[v] === false } }));
  check(lab, "Human keypoints", "showKeypoints");

  const cams = section("Cameras");
  check(cams, "Frusta", "showFrusta");
  check(cams, "Image planes", "showPlanes");
  slider(cams, "Plane depth", "planeDepth", 1, 30, 0.5, (v) => `${v.toFixed(1)}m`);
  slider(cams, "Plane opacity", "planeOpacity", 0, 1, 0.05);
  check(cams, "Panoptic overlay", "showSeg");
  slider(cams, "Overlay opacity", "segOpacity", 0, 1, 0.05);

  const view = section("View");
  chips(view, RIGS.map(([r, l]) => [r, l]), (s, v) => s.rig === v, (v) => store.patch({ rig: v }));
  const povWrap = document.createElement("div");
  povWrap.style.marginTop = "6px";
  view.append(povWrap);
  chips(povWrap, Object.entries(scene.cameras).map(([k, c]) => [Number(k), c.name.toLowerCase().replace("_", " ")] as [number, string]), (s, v) => s.rig === "pov" && s.povCamera === v, (v) => store.patch({ rig: "pov", povCamera: v }));
  check(view, "Ego trajectory", "showEgo");
  check(view, "Ground grid", "showGrid");
  slider(view, "Bloom", "bloom", 0, 1.5, 0.05);
  slider(view, "Fog", "fog", 0, 1, 0.05);

  const keys = section("Keys");
  keys.insertAdjacentHTML("beforeend", `<div class="keys"><b>space</b> play · <b>← →</b> step (<b>shift</b> ×10) · <b>, .</b> rate<br><b>1-7</b> colour modes · <b>a</b> accumulate · <b>[ ]</b> window<br><b>b</b> boxes · <b>l</b> labels · <b>t</b> trails · <b>k</b> keypoints<br><b>f</b> frusta · <b>i</b> planes · <b>s</b> panoptic · <b>e</b> ego<br><b>c</b> cycle view · <b>shift+1-5</b> camera POV · <b>g</b> glow<br><b>h</b> hide UI · <b>p</b> screenshot · <b>esc</b> deselect</div>`);
}
