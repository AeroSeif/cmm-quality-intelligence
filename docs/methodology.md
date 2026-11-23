# Methodology and interpretation

## Study types

### Dynamic repeatability

The repeatability study represents repeated readings of one simulated physical component. The current dimensional calculation uses the sample standard deviation and calculates study variation as `6 × s`. Repeatability percentage is `6 × s / (USL − LSL) × 100`.

The prototype compares that result with the configured Critical/Major/Minor reference limits in `core/repeatability.py`. Confirm the applicable customer-approved standard revision, characteristic classification, measurement conditions and local procedures before any engineering use.

The colour bar in the dashboard expresses **limit utilisation**: `repeatability_pct / acceptance_limit_pct × 100`. Its warning bands are visual aids, not additional acceptance criteria.

### Part variation

The part-variation study represents different simulated component serial numbers. It presents descriptive distributions, observed spread and counts outside the supplied dimensional specification limits. It does not apply repeatability acceptance criteria.

Cp/Cpk, control-chart interpretations and process-release decisions are intentionally not calculated by this prototype.

## Geometric characteristics

Geometric records are extracted and displayed separately. They are not evaluated using the dimensional repeatability calculation. A suitable geometric methodology must be defined and validated separately.

## Data provenance

All included workbooks are synthetic and generated for software demonstration and testing. Synthetic classification labels are test metadata, not approved drawing classifications or customer decisions.
