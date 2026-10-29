# Spatial Interpolation Validation & LOSOCV Benchmark

## 1. Methodology

To evaluate spatial interpolation accuracy across Greater Mumbai without spatial data leakage, we execute **Leave-One-Station-Out Cross-Validation (LOSOCV)**. For each monitoring station $s_k$, the spatial model is fitted exclusively on the remaining $N-1$ stations $S_{-k}$, and predicts the AQI at the exact latitude and longitude of $s_k$. This process is repeated across all active ground stations and aggregated across multiple historical timestamps.

### Evaluated Architectures:
- **IDW ($p=1$)**: Linear Inverse Distance Weighting, decaying slowly with geographic distance.
- **IDW ($p=2$)**: Quadratic Inverse Distance Weighting (standard inverse square law of dispersion).
- **IDW ($p=3$)**: Cubic Inverse Distance Weighting, penalizing distant stations aggressively.
- **Ordinary Kriging**: Gaussian Process Regression using a stationary spatial Matern-3/2 covariance kernel with nugget regularization.
- **Spatial GBM**: Gradient Boosted Trees regressing spatial non-linearities directly on coordinates.

## 2. Multi-Hour Cross-Validation Results

Evaluated across 12 distinct hourly ground-truth snapshots across Mumbai stations:

| Model Configuration | Mean RMSE (AQI) | Std RMSE | Mean MAE (AQI) | Evaluated Snapshots |
| :--- | :---: | :---: | :---: | :---: |
| Inverse Distance Weighting (p=1) | 71.80 | 19.12 | 63.46 | 12 |
| Inverse Distance Weighting (p=2) | 79.32 | 21.00 | 69.27 | 12 |
| Inverse Distance Weighting (p=3) | 86.74 | 22.95 | 74.21 | 12 |
| Ordinary Kriging (Gaussian Process Matern) **(Default Winner)** | 66.80 | 17.89 | 59.10 | 12 |
| Spatial Gradient Boosted Regressor | 79.98 | 18.33 | 58.04 | 12 |

### Selected Production Interpolator: **Ordinary Kriging (Gaussian Process Matern)**

**Empirical Justification:** Across real ground CAAQMS observations in Mumbai, **Ordinary Kriging (Gaussian Process Matern)** achieved the lowest cross-validated RMSE of **66.80 AQI units** (with standard deviation 17.89). IDW with quadratic distance decay ($p=2$) reflects atmospheric plume dispersion physics while avoiding the boundary artifacts of tree-based methods and the computational variance of covariance inversion on small spatial graphs.
