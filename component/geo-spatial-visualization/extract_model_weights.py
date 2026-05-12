"""
Extract model weights from pkl files without importing sklearn.
Saves coef/intercept as .npy files so predict.py can run without sklearn.
Run once: python extract_model_weights.py
"""
import numpy as np
import os
import joblib
import joblib.numpy_pickle as jnp

class _Container:
    """Generic container that accepts any __setstate__ call."""
    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        else:
            self._state = state

class _SklearnFreeUnpickler(jnp.NumpyUnpickler):
    def find_class(self, module, name):
        if 'sklearn' in module or 'scipy' in module:
            return _Container
        return super().find_class(module, name)

def load_without_sklearn(path):
    import io
    with open(path, 'rb') as f:
        # joblib reads a header first; use its internal _unpickle path
        unpickler = _SklearnFreeUnpickler(
            path, f,
            ensure_native_byte_order=True,
        )
        return unpickler.load()

print("Extracting model weights from pkl files...")
print("(no sklearn import needed)")

os.makedirs('models/weights', exist_ok=True)

# ── Scaler ──────────────────────────────────────────
scaler = load_without_sklearn('models/scaler.pkl')
print(f"\nscaler type : {type(scaler)}")
print(f"scaler attrs: {[k for k in scaler.__dict__ if not k.startswith('_')]}")

# MinMaxScaler internal fields
scale_ = np.array(scaler.scale_)
min_   = np.array(scaler.min_)
n_feat = int(scaler.n_features_in_)

np.save('models/weights/scaler_scale.npy', scale_)
np.save('models/weights/scaler_min.npy',   min_)
np.save('models/weights/n_features.npy',   np.array([n_feat]))

print(f"  scale_ shape: {scale_.shape} → {scale_}")
print(f"  min_   shape: {min_.shape}   → {min_}")
print(f"  n_features  : {n_feat}")

# ── Latitude model ───────────────────────────────────
m_lat = load_without_sklearn('models/model_lat.pkl')
print(f"\nmodel_lat attrs: {[k for k in m_lat.__dict__ if not k.startswith('_')]}")

coef_lat      = np.array(m_lat.coef_).flatten()
intercept_lat = float(m_lat.intercept_)

np.save('models/weights/lat_coef.npy',      coef_lat)
np.save('models/weights/lat_intercept.npy', np.array([intercept_lat]))

print(f"  coef_      : {coef_lat}")
print(f"  intercept_ : {intercept_lat}")

# ── Longitude model ──────────────────────────────────
m_lon = load_without_sklearn('models/model_lon.pkl')
print(f"\nmodel_lon attrs: {[k for k in m_lon.__dict__ if not k.startswith('_')]}")

coef_lon      = np.array(m_lon.coef_).flatten()
intercept_lon = float(m_lon.intercept_)

np.save('models/weights/lon_coef.npy',      coef_lon)
np.save('models/weights/lon_intercept.npy', np.array([intercept_lon]))

print(f"  coef_      : {coef_lon}")
print(f"  intercept_ : {intercept_lon}")

print("\n[DONE] Weights saved to models/weights/")
print("Now predict.py can run without sklearn.")
