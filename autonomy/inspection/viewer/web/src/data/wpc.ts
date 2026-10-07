/** Parser for the WPC1 planar point container (see export/wpc.py). */
export const KIND = { xyz: 1, intensity: 2, elongation: 3, flags: 4, rgb: 5, projCam: 6, projU: 7, projV: 8, semantic: 9, instance: 10 } as const;

export interface WpcSection {
  sensor: number;
  ret: number;
  kind: number;
  count: number;
  data: Int16Array | Uint8Array | Uint16Array | Int32Array | Float32Array;
  components: number;
}
export interface ParsedWpc {
  frameIndex: number;
  timestamp: number;
  scale: number;
  sections: Map<string, WpcSection>;
  bytes: number;
}

export const sectionKey = (sensor: number, ret: number, kind: number) => `${sensor}/${ret}/${kind}`;

export function parseWpc(buf: ArrayBuffer): ParsedWpc {
  const dv = new DataView(buf);
  const magic = String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3));
  if (magic !== "WPC1" || dv.getUint16(4, true) !== 1) throw new Error("not a WPC1 file");
  const headerBytes = dv.getUint16(6, true);
  const frameIndex = dv.getUint32(8, true);
  const count = dv.getUint32(12, true);
  const scale = dv.getFloat32(16, true);
  const timestamp = Number(dv.getBigUint64(24, true));
  const sections = new Map<string, WpcSection>();
  for (let i = 0; i < count; i++) {
    const o = headerBytes + 32 * i;
    const sensor = dv.getUint8(o);
    const ret = dv.getUint8(o + 1);
    const kind = dv.getUint8(o + 2);
    const dtype = dv.getUint8(o + 3);
    const components = dv.getUint8(o + 4);
    const n = dv.getUint32(o + 8, true);
    const offset = Number(dv.getBigUint64(o + 16, true));
    const len = n * components;
    let data: WpcSection["data"];
    switch (dtype) {
      case 1: data = new Uint8Array(buf, offset, len); break;
      case 2: data = new Int16Array(buf, offset, len); break;
      case 3: data = new Uint16Array(buf, offset, len); break;
      case 4: data = new Int32Array(buf, offset, len); break;
      case 5: data = new Float32Array(buf, offset, len); break;
      default: throw new Error(`unknown dtype ${dtype}`);
    }
    sections.set(sectionKey(sensor, ret, kind), { sensor, ret, kind, count: n, data, components });
  }
  return { frameIndex, timestamp, scale, sections, bytes: buf.byteLength };
}
