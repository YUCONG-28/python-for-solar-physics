# Gaussian Fitting Evidence Note

This note consolidates stable Gaussian fitting, source-centroid, and apparent
source-size guidance from papers in [`../catalog/papers.json`](../catalog/papers.json).
It is an evidence synthesis, not executable code. Where the catalog marks a
detail for full-text confirmation, that uncertainty remains in force.

## Evidence base

Direct Gaussian/source-size evidence:

- *Frequency-time-resolved Imaging Spectroscopy of Fine Structures in a Solar
  Radio Noise Storm*
- *Sizes and Shapes of Sources in Solar Metric Radio Bursts*
- *LOFAR observations of radio burst source sizes and scattering in the solar
  corona*
- *Frequency-Distance Structure of Solar Radio Sources Observed by LOFAR*
- *The apparent positions of solar radio sources observed by the Low Frequency
  Array*
- *A decade of solar Type III radio bursts observed by the Nancay
  Radioheliograph 1998-2008*

Centroid, propagation, and model-limitation evidence:

- *Imaging spectroscopy reveals spike-like repeating radio burst pairs in the
  solar corona*
- *Magnetic Field Geometry and Anisotropic Scattering Effects on Solar Radio
  Burst Observations*
- *Sub-second Time Evolution of Type III Solar Radio Burst Sources at
  Fundamental and Harmonic Frequencies*
- *On the Source Position and Duration of a Solar Type III Radio Burst Observed
  by LOFAR*
- *Comprehensive study of solar type II radio bursts and the properties of the
  associated shock waves*
- *Electron Beam Propagation and Radio-Wave Scattering in the Inner Heliosphere
  using Five Spacecraft*
- *A Review of Recent Solar Type III Imaging Spectroscopy*
- *Type III Solar Radio Burst Source Region Splitting Due to a
  Quasi-Separatrix Layer*

The type II/herringbone study above supports transfer of the centroiding and
height-comparison method only. Its shock-physics conclusions do not transfer
directly to type III spike-topping events.

## Image inputs and coordinates

- Preserve the original FITS header and record the conversion chain between
  RA/Dec and helioprojective coordinates.
- Before comparing images across frequency, verify the pixel-to-world
  transform, observation time, and adopted solar-radius definition.
- When overlaying radio sources on AIA images, record any difference between
  the apparent radio and EUV solar radii and any empirical scaling applied.

## Background model

- Support pre-burst, quiet-Sun, and running- or temporal-median background
  estimates as explicit alternatives.
- Retain both a constant background and, for an ROI with a clear gradient, a
  tilted-plane background.
- Weak, extended, or off-center sources are particularly sensitive to the
  background choice; treat centroid shifts under alternative backgrounds as a
  diagnostic.

## Fitting model and initialization

The default single-source model is an elliptical Gaussian with a constant
background:

```math
\begin{aligned}
I(x,y) &= A\exp\left[-\frac{1}{2}Q(x,y)\right] + B, \\
Q(x,y) &= \left(\frac{x'}{\sigma_x}\right)^2
        + \left(\frac{y'}{\sigma_y}\right)^2.
\end{aligned}
```

For a structured background, use:

```math
I(x,y) = G(x,y) + B_0 + B_x x + B_y y.
```

Use a multi-source model only when the ROI is demonstrably multi-peaked and the
scientific interpretation supports it. Reasonable initial values are the ROI
peak minus edge background for amplitude, the peak pixel or
intensity-weighted centroid for position, the half-maximum region for widths,
the ROI-edge median for background, and either zero or a second-moment estimate
for rotation.

Enforce positive amplitude and widths, keep the centroid inside the ROI, and
reject solutions in which the background dominates the fitted source.

## Outputs and quality control

- Record fit status and reason, SNR, noise estimate, reduced chi-square,
  residual RMS, fitted parameters, and parameter covariance.
- Estimate image noise with $\sigma_{\mathrm{noise}} \approx 1.4826\,\mathrm{MAD}$
  when the selected noise region supports that estimator, and record the
  region used.
- Flag low SNR, an ROI-edge source, multi-peak structure, implausibly large
  FWHM, and structured residuals. Preserve the original ROI, model image, and
  residual image for review.
- Lower-frequency images often have poorer effective resolution. Exclude a
  frame from trajectory or speed fitting when the fitted center is unstable or
  strongly inconsistent with an independent center estimate.

## Centroid validation

Record the Gaussian fitted center and an independent contour or
intensity-weighted center in parallel. At minimum retain
`gaussian_x_arcsec`, `gaussian_y_arcsec`, `contour_x_arcsec`,
`contour_y_arcsec`, and `delta_r_arcsec`. A large separation should trigger
review of the background, ROI, contour threshold, and possible multi-source
structure.

## Beam, propagation, and source size

When a reliable beam is available, an approximate axis-by-axis deconvolution
is:

```math
\mathrm{FWHM}_{\mathrm{intrinsic}}^2
\approx \mathrm{FWHM}_{\mathrm{observed}}^2
- \mathrm{FWHM}_{\mathrm{beam}}^2.
```

Apply the correction separately to major and minor axes for an anisotropic
beam. Without reliable beam information, report the result as an **observed
apparent source size**, not an intrinsic size. Scattering, refraction, and
magnetic-field geometry can shift, broaden, elongate, or split the apparent
source even after instrumental beam treatment.

## Uncertainty and physical interpretation

- Separate fit-parameter uncertainty from imaging-system, beam, ionospheric,
  and propagation uncertainty.
- If the beam is unknown or scattering is important, describe centroid and
  source-size uncertainties conservatively rather than interpreting the fit
  covariance as the total error.
- Report the fitted center, independent center, and their separation for
  paper-level results.
- Compare spatial trajectory, frequency-height relation, height-time relation,
  and dynamic-spectrum drift rate without equating their derived speeds.
  Gaussian-center motion, density-model height motion, and drift-rate-derived
  electron-beam speed are distinct observables with different assumptions.
