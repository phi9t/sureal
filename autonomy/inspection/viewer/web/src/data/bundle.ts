/** Types mirroring scene.json / tracks.json / frames/NNNN.json written by export/export.py. */
export interface CameraCalib {
  name: string;
  width: number;
  height: number;
  intrinsics: { f_u: number; f_v: number; c_u: number; c_v: number; k1: number; k2: number; p1: number; p2: number; k3: number };
  vehicle_from_camera: number[];
  rolling_shutter_direction: number;
}
export interface LidarCalib {
  name: string;
  vehicle_from_lidar: number[];
  inclination_min: number;
  inclination_max: number;
  inclination_values: number[] | null;
  intensity_cap: number;
}
export interface FrameCamera {
  image: string;
  panoptic: string | null;
  panoptic_divisor?: number;
  world_from_vehicle: number[];
  pose_timestamp: number;
  velocity: number[];
}
export interface FrameStats {
  time_of_day: string;
  location: string;
  weather: string;
  lidar_object_counts: Record<string, number>;
  camera_object_counts: Record<string, number>;
}
export interface FrameMeta {
  index: number;
  timestamp_micros: number;
  world_from_vehicle: number[];
  points: string;
  annotations: string;
  point_counts: Record<string, number>;
  has_lidar_segmentation: boolean;
  cameras: Record<string, FrameCamera>;
  stats: FrameStats | null;
}
export interface Scene {
  bundle_format: string;
  lineage: { slice_id: string; release: string; split: string; context: string };
  frames_declaration: { world_origin_waymo: number[] };
  quantization: { xyz: { scale_m: number } };
  cameras: Record<string, CameraCalib>;
  lidars: Record<string, LidarCalib>;
  frames: FrameMeta[];
  tracks: string;
  palettes: {
    box_types: Record<string, string>;
    box_colors: Record<string, string>;
    lidar_semantic_classes: string[];
    lidar_semantic_colors: string[];
    camera_semantic_classes: string[];
    camera_semantic_colors: string[];
    keypoint_types: Record<string, string>;
    keypoint_edges: [number, number][];
  };
}
export interface Tracks {
  columns: string[];
  tracks: Record<string, { type: number; rows: (number | null)[][] }>;
}
export type Box2D = [string, number, number, number, number, number];
export interface FrameAnnotations {
  camera_boxes: Record<string, Box2D[]>;
  projected_boxes: Record<string, Box2D[]>;
  synced_boxes: [string, number, number, number, number, number, number, number, number][];
  associations: [string, string, number][];
  camera_keypoints: Record<string, Record<string, [number, number, number, number][]>>;
  lidar_keypoints: Record<string, [number, number, number, number, number][]>;
}

export interface BoxRow {
  id: string;
  type: number;
  frame: number;
  c: [number, number, number];
  size: [number, number, number];
  heading: number;
  speed: [number, number, number] | null;
  numPoints: number;
}

/** Per-frame box index built once from tracks.json. */
export class TrackIndex {
  byFrame = new Map<number, BoxRow[]>();
  byId = new Map<string, BoxRow[]>();
  constructor(public tracks: Tracks) {
    const c = Object.fromEntries(tracks.columns.map((n, i) => [n, i]));
    for (const [id, t] of Object.entries(tracks.tracks)) {
      const rows: BoxRow[] = [];
      for (const r of t.rows) {
        const row: BoxRow = {
          id,
          type: t.type,
          frame: r[c.frame] as number,
          c: [r[c.cx] as number, r[c.cy] as number, r[c.cz] as number],
          size: [r[c.length] as number, r[c.width] as number, r[c.height] as number],
          heading: r[c.heading] as number,
          speed: r[c.vx] == null ? null : [r[c.vx] as number, r[c.vy] as number, r[c.vz] as number],
          numPoints: (r[c.num_points] as number) ?? 0,
        };
        rows.push(row);
        let list = this.byFrame.get(row.frame);
        if (!list) this.byFrame.set(row.frame, (list = []));
        list.push(row);
      }
      this.byId.set(id, rows);
    }
  }
}

export async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return (await r.json()) as T;
}

export async function listScenes(): Promise<{ slice: string; context: string; url: string }[]> {
  const idx = await fetchJson<{ scenes: { slice: string; context: string; url: string }[] }>("bundles/index.json");
  return idx.scenes;
}
