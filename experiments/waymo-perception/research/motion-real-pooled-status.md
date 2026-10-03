# Acquired native pooled Motion evaluator gate

Four oracle diagnostic controls pool the two acquired native scenarios with offsets(0,0),(0,2),(2,0),(2,2). A native parser independently reads original truth and serialized trajectories to compute per-class Euclidean sums and valid measurement counts. A separate live Python checker combines sums/counts, not scene means.

Vehicle support is9 ADE but7 FDE measurements because two targets have missing endpoints. With only the training example offset by2m, pooled vehicle ADE is2/9 and FDE2/7; with only validation offset, they are16/9 and12/7. One pedestrian retains separate1/1 support. All controls agree with the native scorer within declared1e-3m tolerance. Duplicate scenarios and wrong scenario/prediction identities refuse without output;28 damaged score/count/class/scenario-count/nonfinite copies are rejected by the independent checker.

[Live receipt](motion-real-pooled-metric-verified.json) pins both runtimes, sources, original metric handoff and outputs. This deliberately mixes official splits only as an explicit scorer diagnostic. Scientific training, tuning and held-out evaluation must keep those splits separate. No causal predictor, learned forecast quality or improvement is claimed.

The earlier comparator accepted NaN; fresh review reproduced it. Live RED→GREEN finite tests now reject observed and reference NaN/±Infinity. The finite checker receipt supersedes the earlier20-probe checker admission; native scorer/reference outputs remain unchanged.
