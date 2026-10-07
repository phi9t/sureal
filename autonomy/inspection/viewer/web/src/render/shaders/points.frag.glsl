in vec3 vColor;
in float vAlpha;
in float vFogDepth;
uniform vec3 uFogColor;
uniform float uFogDensity;
uniform float uGlow;
uniform float uGlowScale;
out vec4 fragColor;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = dot(c, c);
  if (d > 0.25) discard;
  float edge = smoothstep(0.25, 0.10, d);
  float fog = 1.0 - exp(-uFogDensity * uFogDensity * vFogDepth * vFogDepth);
  vec3 col = mix(vColor, uFogColor, fog);
  float a = vAlpha * edge;
  if (uGlow > 0.5) {
    fragColor = vec4(col * a * uGlowScale, 1.0);
  } else {
    if (a < 0.02) discard;
    fragColor = vec4(col, a);
  }
}
