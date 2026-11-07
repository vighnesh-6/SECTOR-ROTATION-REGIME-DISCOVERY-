import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "deployment"))

from database.connection import get_db_client
from engine.feature_adapter import MarketFeatureAdapter
from engine.inference_engine import RegimeInferenceEngine

db = get_db_client()
adapter = MarketFeatureAdapter(db_client=db)
engine = RegimeInferenceEngine()

# Test compute_features_for_date for 2026-09-21
feats = adapter.compute_features_for_date("2026-09-21")
print(f"Features computed successfully on 2026-09-21: {len(feats)} features")
print(f"Sample features: Return_20D={feats['Return_20D']:.6f}, VIX_Close={feats['VIX_Close']:.2f}")

# Scale features
x_scaled = engine.scale_features(feats)
print(f"Scaled features: shape={x_scaled.shape}, mean={x_scaled.mean():.4f}")

# Prior probabilities from 2026-09-18
prev_probs = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
res = engine.forward_step(
    features=feats, prev_probs=prev_probs, incumbent_regime=2
)
print(f"Forward step output on 2026-09-21:")
print(f"  Probs: {[round(p, 4) for p in res['probs_array']]}")
print(f"  Raw argmax: {res['raw_regime_argmax']}, Max prob: {res['max_probability']:.4f}, Confident: {res['is_confident']}, Accepted regime: {res['accepted_regime']}")

