# 5.4.2 · Sample a validated curve without replacing its source

**Chapter 5 · Lines, points and curves · Section 5.4 · NURBS curves** · [Contents](contents.md)

**Typing: 130–260 minutes.** [Estimate](typing-load.md).

Plan several study sessions for this subject. Save at file boundaries; its executable checkpoint remains one complete subject.

Use the control polygon’s turning to choose display chords, matching the current viewer’s three-degree policy and 512 uniform-chord cap.

## Type

Continue from [Validate an original NURBS curve before sampling](38-layout.md). [Save or recover your work](recovery.md).

### 1. `src/curve.rs`

Sample the original evaluator with bounded uniform chords and exact interior knot breaks.

<details>
<summary>Locate the existing block</summary>

```rust
use session_rust::NurbsCurve;

pub fn validate(source: &NurbsCurve) -> Result<(f64, f64), &'static str> {
    if !(2..=3).contains(&source.m_dim) || !(2..=10_000).contains(&source.m_cv_count)
        || !(2..=32).contains(&source.m_order) || source.m_order > source.m_cv_count {
        return Err("Curve dimension, count or order is invalid");
    }
    let size = source.m_dim + usize::from(source.m_is_rat);
    if source.m_cv_stride < size { return Err("Curve control stride is too short"); }
    let end = (source.m_cv_count - 1).checked_mul(source.m_cv_stride)
        .and_then(|offset| offset.checked_add(size)).ok_or("Curve control range overflows")?;
    if source.m_cv.len() < end { return Err("Curve control values are incomplete"); }
    for index in 0..source.m_cv_count {
        let start = index * source.m_cv_stride;
        let values = &source.m_cv[start..start + size];
        if values.iter().any(|v| !v.is_finite()) { return Err("Curve controls must be finite"); }
        if source.m_is_rat && values[source.m_dim] <= 0.0 { return Err("Curve display requires positive rational weights"); }
    }
    let count = source.m_cv_count + source.m_order - 2;
    if source.m_nurbsknot.len() != count || source.m_nurbsknot.iter().any(|v| !v.is_finite())
        || source.m_nurbsknot.windows(2).any(|pair| pair[0] > pair[1]) {
        return Err("Curve knot vector is incomplete or unordered");
    }
    let domain = source.domain();
    if domain.0 >= domain.1 || !(domain.1 - domain.0).is_finite() { return Err("Curve domain must have positive length"); }
    Ok(domain)
}
```

</details>

After that block, type:

```rust
--8<-- "journey/code/38a-samples-01.rs" skip=1593
```

### 2. `src/lib.rs`

Register actual sampled geometry checks.

Edit these blocks from bottom to top. Keep the surrounding lines unchanged.

<details>
<summary>Locate this block</summary>

```rust
mod browser_upload;
#[cfg(target_arch = "wasm32")]
mod browser_phase;
```

</details>

Replace it with:

```rust
mod browser_upload;
#[cfg(target_arch = "wasm32")]
mod browser_phase;

pub mod math_quality;
```

<details>
<summary>Locate this block</summary>

```rust
mod curve_layout_tests;
#[cfg(test)]
mod control_tests;
```

</details>

Replace it with:

```rust
mod curve_sample_tests;
#[cfg(test)]
mod curve_layout_tests;
#[cfg(test)]
mod control_tests;
```

<details>
<summary>Complete updated block reference</summary>

```rust
--8<-- "journey/code/38a-samples-02.rs"
```

</details>

<details>
<summary>Supplied validation fixture</summary>

Copy this supplied authoring fixture once. Continue with the browser build below; the course does not require running native tests.

### 3. `src/curve_sample_tests.rs`

Copy original preservation, dense measured error, periodic closure and knot-break checks.

Copy this supplied file:

```text
--8<-- "journey/code/38a-samples-03.rs"
```

</details>

### 4. `src/math_quality.rs`

Bound mathematical display refinement while retaining original source identity.

Create the file and type:

```rust
--8<-- "journey/code/38a-samples-math-display-3.rs"
```

## Run and check

In your project:

```sh
cd workspace/journey
REGEN_PROTO=0 cargo build --lib --locked --target wasm32-unknown-unknown -j1
REGEN_PROTO=0 CARGO_BUILD_JOBS=1 trunk serve --port 8780
```

Open `http://127.0.0.1:8780/`. Keep an existing Trunk server running; saving rebuilds it.

Run straight, curved, periodic and malformed curve sampling checks. Original control arrays remain unchanged.

### Recorded visual result

**Previous native render — current verification pending.**

This checkpoint was rendered independently and has the same native comparison frame as [Validate an original NURBS curve before sampling](38-layout.md). Use its state checks and browser exercise to assess the changed behavior.

![Native renderer output for sample a validated curve without replacing its source.](../screenshots/journey/37d-render.png)

*This recorded image predates a source or checker change. Rebuild this checkpoint before using it as current evidence; browser controls require separate acceptance.*

<details>
<summary>Code explanation and diagram</summary>

Include original interior knot breaks as well. Bound the control count before allocating, keep sample positions in double precision, and refuse nonfinite or unrepresentable display coordinates. A sampled polyline remains an approximation rather than a replacement kernel curve.

validated original curve → control-polygon turning → bounded parameter samples and knot breaks → finite double-precision chords.

![Original kernel evaluations create a bounded display approximation.](../illustrations/journey-38a.svg)

What does the sampled polyline know that the original curve does not lose?

It provides drawing chords at chosen parameters. The original knots, degree, rational weights and exact controls remain the editing source; the chords are explicitly an approximation.

Study estimate, including typing and experiments: 0.75–1.25 hours.

</details>

<details>
<summary>Optional experiment</summary>

Compare dense kernel evaluations with the sampled quadratic arch. Check measured chord error, rather than mistaking its control polygon for the curve.

</details>

<details>
<summary>Check and save your work</summary>

Restore experimental edits, then run from `session_viewer`:

```sh
npm --prefix ../session_tests run course -- check 5.4.2
npm --prefix ../session_tests run course -- save 5.4.2
```

Source comparison leaves your project untouched. [Save and recovery instructions](recovery.md).

</details>

<details>
<summary>Viewer coverage and verification</summary>

Curve display sampling is complete. Original curve rows, control markers and real input follow in the remaining curve checkpoints.

Native checks prove exact original preservation, straight minimal samples, real quadratic arch shape and measured dense chord error, periodic endpoints, knot-break inclusion and bounded malformed-input refusal.

Chrome retains point and connected rendering while native checks guard original curve evaluation.

[Full validation scope](release.md).

To reproduce the scripted acceptance of the reference checkpoint, run from `session_viewer` with the [course bundle server](release.md#reproduce) running on port 8781:

```sh
npm --prefix ../session_tests run course -- capture 5.4.2
```

This uses the verified reference bundle; it does not check or change your typed project.

</details>
