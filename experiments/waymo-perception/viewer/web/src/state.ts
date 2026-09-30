/** Tiny observable store: no framework, selector-based subscriptions. */
export type ColorMode = "height" | "intensity" | "range" | "semantic" | "sensor" | "rgb" | "return";
export type Rig = "orbit" | "follow" | "bev" | "pov";

export interface ViewerState {
  frame: number;
  playing: boolean;
  rate: number;
  colorMode: ColorMode;
  pointSize: number;
  accumulate: boolean;
  accumFrames: number;
  accumStride: number;
  sensors: Record<number, boolean>;
  returns: [boolean, boolean];
  dimNlz: boolean;
  showBoxes: boolean;
  showLabels: boolean;
  showTrails: boolean;
  showSpeed: boolean;
  classFilter: Record<number, boolean>;
  showFrusta: boolean;
  showPlanes: boolean;
  planeDepth: number;
  planeOpacity: number;
  showKeypoints: boolean;
  showSeg: boolean;
  segOpacity: number;
  showEgo: boolean;
  showGrid: boolean;
  rig: Rig;
  povCamera: number;
  bloom: number;
  fog: number;
  glow: boolean;
  uiHidden: boolean;
  focusCamera: number | null;
  selectedTrack: string | null;
}

export const initialState: ViewerState = {
  frame: 0,
  playing: false,
  rate: 1,
  colorMode: "height",
  pointSize: 2.2,
  accumulate: false,
  accumFrames: 12,
  accumStride: 1,
  sensors: { 1: true, 2: true, 3: true, 4: true, 5: true },
  returns: [true, true],
  dimNlz: false,
  showBoxes: true,
  showLabels: false,
  showTrails: false,
  showSpeed: true,
  classFilter: { 1: true, 2: true, 3: true, 4: true },
  showFrusta: true,
  showPlanes: true,
  planeDepth: 6,
  planeOpacity: 0.85,
  showKeypoints: true,
  showSeg: false,
  segOpacity: 0.55,
  showEgo: true,
  showGrid: true,
  rig: "orbit",
  povCamera: 1,
  bloom: 0.45,
  fog: 0.35,
  glow: false,
  uiHidden: false,
  focusCamera: null,
  selectedTrack: null,
};

type Listener<T> = (value: T, prev: T) => void;

export class Store {
  private state: ViewerState;
  private listeners: { selector: (s: ViewerState) => unknown; cb: Listener<any>; last: unknown }[] = [];
  constructor(initial: ViewerState) {
    this.state = { ...initial };
  }
  get(): ViewerState {
    return this.state;
  }
  patch(p: Partial<ViewerState>): void {
    const prev = this.state;
    this.state = { ...prev, ...p };
    for (const l of this.listeners) {
      const v = l.selector(this.state);
      if (v !== l.last) {
        const old = l.last;
        l.last = v;
        l.cb(v, old);
      }
    }
  }
  /** Subscribe to a selector; fires immediately with the current value. */
  subscribe<T>(selector: (s: ViewerState) => T, cb: Listener<T>): () => void {
    const entry = { selector, cb, last: selector(this.state) };
    this.listeners.push(entry);
    cb(entry.last as T, entry.last as T);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== entry);
    };
  }
  /** Subscribe to any change (cheap way to react to several keys). */
  watch(keys: (keyof ViewerState)[], cb: (s: ViewerState) => void): () => void {
    return this.subscribe((s) => keys.map((k) => s[k]).join("\u0000"), () => cb(this.state));
  }
}
