# Sureal mission

Sureal studies the transition from reconstructing observed surfaces to sampling
one persistent, coherent scene hypothesis from incomplete visual evidence. It is
a fork of [Surflo](https://github.com/Anttwo/Surflo): Surflo remains the
inherited reconstruction model and `surflo` remains the compatible Python
package. Sureal contributes reproduction infrastructure, controlled failure
experiments, and a research program; it does not yet claim a learned generative
scene model.

The central distinction is between resampling points on a fixed surface and
sampling which hidden scene exists. For observations \(O\), the proposed model
first samples one scene state and then reuses it for every point, camera, and
time:

\[
z \sim p_\psi(z\mid O),
\qquad
x_i \sim p_\theta(x_i\mid z,O).
\]

The next defining result is a matched-data learned comparison showing evidence
preservation, within-sample validity, across-sample coverage, and cross-query
persistence on held-out configurations. The current evidence, architectural
analysis, limitations, and staged research directions are documented in
[Coherent scene hypotheses](docs/coherent-scene-hypotheses.md).

The broader historical and executable context is the
[3D reconstruction pathway](docs/3d-reconstruction-pathway.md), which traces
the measurement, representation, rendering, and generative traditions that
motivate the persistent-scene objective.
