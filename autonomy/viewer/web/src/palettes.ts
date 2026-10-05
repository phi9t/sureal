import * as THREE from "three";

export function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/** Google's "turbo" colormap polynomial approximation. */
export function turbo(t: number): [number, number, number] {
  const x = Math.min(Math.max(t, 0), 1);
  const r = 0.13572138 + x * (4.6153926 + x * (-42.66032258 + x * (132.13108234 + x * (-152.94239396 + x * 59.28637943))));
  const g = 0.09140261 + x * (2.19418839 + x * (4.84296658 + x * (-14.18503333 + x * (4.27729857 + x * 2.82956604))));
  const b = 0.1066733 + x * (12.64194608 + x * (-60.58204836 + x * (110.36276771 + x * (-89.90310912 + x * 27.34824973))));
  return [Math.min(Math.max(r, 0), 1), Math.min(Math.max(g, 0), 1), Math.min(Math.max(b, 0), 1)];
}

/** A cool cyan -> warm amber ramp used for height/intensity. */
export function ember(t: number): [number, number, number] {
  const stops: [number, [number, number, number]][] = [
    [0.0, hexToRgb("#1a2a6c")],
    [0.25, hexToRgb("#2196f3")],
    [0.5, hexToRgb("#4dd0e1")],
    [0.7, hexToRgb("#ffe082")],
    [0.85, hexToRgb("#ff8a65")],
    [1.0, hexToRgb("#ff1744")],
  ];
  const x = Math.min(Math.max(t, 0), 1);
  for (let i = 1; i < stops.length; i++) {
    if (x <= stops[i][0]) {
      const [a, ca] = stops[i - 1];
      const [b, cb] = stops[i];
      const u = (x - a) / (b - a);
      return [ca[0] + (cb[0] - ca[0]) * u, ca[1] + (cb[1] - ca[1]) * u, ca[2] + (cb[2] - ca[2]) * u];
    }
  }
  return stops[stops.length - 1][1];
}

export function rampTexture(fn: (t: number) => [number, number, number], n = 256): THREE.DataTexture {
  const data = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    const [r, g, b] = fn(i / (n - 1));
    data[i * 4] = r * 255;
    data[i * 4 + 1] = g * 255;
    data[i * 4 + 2] = b * 255;
    data[i * 4 + 3] = 255;
  }
  const tex = new THREE.DataTexture(data, n, 1, THREE.RGBAFormat);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
}

export const SENSOR_COLORS: Record<number, string> = { 1: "#e0f7fa", 2: "#4fc3f7", 3: "#ffb74d", 4: "#ba68c8", 5: "#81c784" };
export const RETURN_COLORS = ["#4fc3f7", "#ff7043"];

/** Deterministic hue for an instance id. */
export function instanceColor(id: number): [number, number, number] {
  const h = (id * 0.618033988749895) % 1;
  const c = new THREE.Color().setHSL(h, 0.75, 0.6);
  return [c.r, c.g, c.b];
}
