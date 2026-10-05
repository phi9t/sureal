import * as THREE from "three";
import { THREE_FROM_WAYMO } from "../frames";

/** Root group holding everything in native Waymo world coordinates. */
export function makeWaymoRoot(): THREE.Group {
  const g = new THREE.Group();
  g.name = "waymoRoot";
  g.matrixAutoUpdate = false;
  g.matrix.copy(THREE_FROM_WAYMO);
  g.matrixWorldNeedsUpdate = true;
  return g;
}
