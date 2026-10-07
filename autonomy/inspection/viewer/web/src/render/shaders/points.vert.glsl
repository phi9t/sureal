// position: int16 vehicle-frame xyz * uScale (three prepends `in vec3 position`).
in float intensity;   // normalized u8
in float elongation;  // normalized u8
in float flags;       // raw u8: bit0 nlz, bit1 return2, bits2-4 sensor, bit5 has projection
in vec3 rgb;          // normalized u8, baked camera colour
in float semantic;    // raw u8 class id (only on TOP segmentation frames)

uniform float uScale;
uniform float uPointSize;
uniform float uViewportHeight;
uniform float uOrtho;
uniform float uAge;
uniform float uHasSemantic;
uniform int uColorMode;       // 0 height 1 intensity 2 range 3 semantic 4 sensor 5 rgb 6 return
uniform vec2 uHeightRange;
uniform float uRangeMax;
uniform float uIntensityGamma;
uniform sampler2D uRamp;
uniform vec3 uSensorColors[8];
uniform vec3 uSemanticColors[32];
uniform vec3 uReturnColors[2];
uniform float uDimNlz;
uniform float uHideNlz;

out vec3 vColor;
out float vAlpha;
out float vFogDepth;

void main() {
  vec3 p = position * uScale;
  int f = int(flags + 0.5);
  bool nlz = (f & 1) != 0;
  int ret = (f >> 1) & 1;
  int sensor = (f >> 2) & 7;
  bool hasProj = (f & 32) != 0;
  float inten = pow(clamp(intensity, 0.0, 1.0), uIntensityGamma);

  if (uColorMode == 0) {
    float t = (p.z - uHeightRange.x) / (uHeightRange.y - uHeightRange.x);
    vColor = texture(uRamp, vec2(clamp(t, 0.0, 1.0), 0.5)).rgb;
  } else if (uColorMode == 1) {
    vColor = texture(uRamp, vec2(inten, 0.5)).rgb;
  } else if (uColorMode == 2) {
    vColor = texture(uRamp, vec2(clamp(length(p) / uRangeMax, 0.0, 1.0), 0.5)).rgb;
  } else if (uColorMode == 3) {
    int cls = int(semantic + 0.5);
    vColor = uHasSemantic > 0.5 ? uSemanticColors[clamp(cls, 0, 31)] : vec3(0.35 + 0.45 * inten);
  } else if (uColorMode == 4) {
    vColor = uSensorColors[sensor] * (0.45 + 0.55 * inten);
  } else if (uColorMode == 5) {
    vColor = hasProj ? pow(rgb, vec3(2.2)) * 1.15 : vec3(0.06 + 0.12 * inten);
  } else {
    vColor = uReturnColors[ret] * (0.45 + 0.55 * inten);
  }

  float alpha = 1.0;
  if (nlz) alpha *= mix(1.0, 0.18, uDimNlz);
  alpha *= mix(1.0, 0.35, uAge);
  if (nlz && uHideNlz > 0.5) alpha = 0.0;
  vAlpha = alpha;

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vFogDepth = -mv.z;
  float size = uOrtho > 0.5 ? uPointSize * 1.1 : uPointSize * (uViewportHeight / 1000.0) * 7.0 / sqrt(max(-mv.z, 1.0));
  size *= mix(1.0, 0.7, uAge);
  gl_PointSize = clamp(size, 1.0, 7.0);
  gl_Position = projectionMatrix * mv;
  if (alpha <= 0.0) gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
}
