import pandas as pd
import numpy as np

# Test the mathematical identities on synthetic data
w_prev = np.array([0.5, 0.5, 0.0]) # Sector 1, Sector 2, Cash
r = np.array([0.02, -0.01, 0.0])   # returns
c = 0.0015 # 15 bps
nav_prev = 1.05

# 1. Gross return
r_gross = np.sum(w_prev * r)
print(f"r_gross: {r_gross:.6f}")

# 2. Pre-trade NAV
nav_pre = nav_prev * (1 + r_gross)
print(f"nav_pre: {nav_pre:.6f}")

# 3. Drifted weights
w_drift = (w_prev * (1 + r)) / (1 + r_gross)
print(f"w_drift: {w_drift}, sum: {w_drift.sum():.6f}")

# 4. Target weights at rebalance
w_target = np.array([0.0, 0.6, 0.4]) # new allocation
to_actual = 0.5 * np.sum(np.abs(w_target - w_drift))
print(f"to_actual: {to_actual:.6f}")

# 5. Cost and Post-trade NAV
tc = nav_pre * to_actual * c
nav_post = nav_pre - tc
print(f"tc: {tc:.6f}, nav_post: {nav_post:.6f}")

# 6. Net return
r_net = nav_post / nav_prev - 1
print(f"r_net: {r_net:.6f}")

# 7. Exact attribution check
c_assets = w_prev * r
c_cost = r_net - r_gross
reconciled_r_net = np.sum(c_assets) + c_cost
print(f"c_cost: {c_cost:.6f}")
print(f"Attribution diff: {abs(r_net - reconciled_r_net):.2e}")
assert np.isclose(r_net, reconciled_r_net)

# Check direct formula for c_cost: -(1 + r_gross) * to_actual * c
c_cost_formula = -(1 + r_gross) * to_actual * c
print(f"c_cost formula diff: {abs(c_cost - c_cost_formula):.2e}")
assert np.isclose(c_cost, c_cost_formula)
print("All mathematical identities verified!")

