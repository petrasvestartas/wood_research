# 9.1.2 · Keep UV coordinates beside original world samples

**Chapter 9 · CAD surfaces and topology · Section 9.1 · Surface controls and trimming** · [Contents](contents.md)

**Typing: 76–152 minutes.** [Estimate](typing-load.md).

Plan several study sessions for this subject. Save at file boundaries; its executable checkpoint remains one complete subject.

Sample the original source in f64, retain each UV address, use the current bounded grid sizes and record four original domain boundaries.

## Type

Continue from [Validate original surface control storage](55-validation.md). [Save or recover your work](recovery.md).

### 1. `src/surface.rs`

Build the current 16–96-step UV grid and open domain border segment ranges.

<details>
<summary>Locate the existing block</summary>

```rust
use session_rust::NurbsSurface;

pub fn validate(source:&NurbsSurface)->Result<[[f64;2];2],&'static str> {
    if !(2..=3).contains(&source.m_dim) {return Err("Surface dimension must be two or three");}
    let count=source.m_cv_count[0].checked_mul(source.m_cv_count[1]).ok_or("Surface control count overflows")?;
    if count>65_536||source.m_cv_count.iter().any(|n|*n<2) {return Err("Surface control count exceeds the display budget");}
    let size=source.m_dim+usize::from(source.m_is_rat);
    if source.m_cv_stride.iter().any(|stride|*stride<size) {return Err("Surface control stride is too short");}
    let row_major=source.m_cv_stride[1].checked_mul(source.m_cv_count[1]).is_some_and(|span|source.m_cv_stride[0]>=span);
    let column_major=source.m_cv_stride[0].checked_mul(source.m_cv_count[0]).is_some_and(|span|source.m_cv_stride[1]>=span);
    if !row_major&&!column_major {return Err("Surface controls overlap in storage");}
    let end=(source.m_cv_count[0]-1).checked_mul(source.m_cv_stride[0]).and_then(|n|(source.m_cv_count[1]-1).checked_mul(source.m_cv_stride[1]).and_then(|m|n.checked_add(m))).and_then(|n|n.checked_add(size)).ok_or("Surface control range overflows")?;
    if end>source.m_cv.len() {return Err("Surface controls are incomplete");}
    for i in 0..source.m_cv_count[0] {for j in 0..source.m_cv_count[1] {
        let start=i*source.m_cv_stride[0]+j*source.m_cv_stride[1];let values=&source.m_cv[start..start+size];
        if values.iter().any(|v|!v.is_finite())||source.m_is_rat&&values[source.m_dim]<=0. {return Err("Surface controls need finite coordinates and positive weights");}
    }}
    let mut domains=[[0.;2];2];
    for dir in 0..2 {
        let order=source.m_order[dir];let count=source.m_cv_count[dir];let knots=&source.m_nurbsknot[dir];
        if !(2..=32).contains(&order)||order>count||knots.len()!=count+order-2||knots.iter().any(|v|!v.is_finite())||knots.windows(2).any(|pair|pair[0]>pair[1]) {return Err("Surface order or knots are invalid");}
        let (a,b)=source.domain(dir).ok_or("Surface domain is missing")?;
        if a>=b||!(b-a).is_finite() {return Err("Surface domain must have finite positive length");}domains[dir]=[a,b];
    }
    Ok(domains)
}
```

</details>

After that block, type:

```rust
--8<-- "journey/code/55a-grid-01.rs" skip=2223
```

## Run and check

In your project:

```sh
cd workspace/journey
REGEN_PROTO=0 cargo build --lib --locked --target wasm32-unknown-unknown -j1
REGEN_PROTO=0 CARGO_BUILD_JOBS=1 trunk serve --port 8780
```

Open `http://127.0.0.1:8780/`. Keep an existing Trunk server running; saving rebuilds it.



### Recorded visual result

**Previous native render — current verification pending.**

Blue Posts, the brown source beam and black original boundaries remain visible.

![Native renderer output for keep uv coordinates beside original world samples.](../screenshots/journey/53u-layers.png)

*This recorded image predates a source or checker change. Rebuild this checkpoint before using it as current evidence; browser controls require separate acceptance.*

This reference image is shared with [8.3.1 · Navigate and fit inside the free canvas](54-camera.md). It does not demonstrate a new feature by itself.

<details>
<summary>Code explanation and diagram</summary>



parameter domain → exact UV → f64 point and normal → grid and original borders.

![Keep UV coordinates beside original world samples.](../illustrations/55a-grid.svg)

Are grid triangles new CAD faces?

No. They are derived display triangles for one original surface. UV addresses retain the connection to the source; its four domain borders keep their own identities.

Study estimate, including typing and experiments: 0.5–1 hours.

</details>

<details>
<summary>Optional experiment</summary>

Evaluate a nonunit domain and compare every cached sample with the original surface at its UV. Count boundary segments separately from interior grid edges.

</details>

<details>
<summary>Check and save your work</summary>

Restore experimental edits, then run from `session_viewer`:

```sh
npm --prefix ../session_tests run course -- check 9.1.2
npm --prefix ../session_tests run course -- save 9.1.2
```

Source comparison leaves your project untouched. [Save and recovery instructions](recovery.md).

</details>

<details>
<summary>Viewer coverage and verification</summary>



The earlier navigation acceptance exercise remains. Surface acceptance connects at the end of this subject and has not been run in Chrome.

[Full validation scope](release.md).

To reproduce the scripted acceptance of the reference checkpoint, run from `session_viewer` with the [course bundle server](release.md#reproduce) running on port 8781:

```sh
npm --prefix ../session_tests run course -- capture 9.1.2
```

This uses the verified reference bundle; it does not check or change your typed project.

</details>
