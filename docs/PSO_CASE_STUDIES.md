| Case | Algorithm | Weighted | Makespan (min) | Cost (EGP) | Queue (min) | Charging (min) | Energy (kWh) | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Single Fork – Baseline | SA | 757.23 | 304.18 | 453.05 | 0.00 | 44.13 | 34.85 | 13.55 |
| Single Fork – Baseline | GA | 291.55 | 271.55 | 20.00 | 0.00 | 0.63 | 1.00 | 33.71 |
| Single Fork – Baseline | PSO | 260.76 | 260.76 | 0.00 | 0.00 | 0.00 | 0.00 | 29.68 |
| Double Fork – Congested Grid | SA | 3495.08 | 551.53 | 2943.55 | 100.31 | 152.28 | 179.95 | 44.95 |
| Double Fork – Congested Grid | GA | 2405.67 | 481.43 | 1924.24 | 44.92 | 88.58 | 107.48 | 107.18 |
| Double Fork – Congested Grid | PSO | 3270.63 | 629.18 | 2641.46 | 190.10 | 182.47 | 172.62 | 97.30 |
| Double Fork – High Demand & Pricing | SA | 4657.31 | 505.50 | 4151.81 | 59.01 | 212.55 | 228.17 | 43.29 |
| Double Fork – High Demand & Pricing | GA | 2719.98 | 495.68 | 2224.30 | 74.71 | 89.27 | 108.19 | 125.64 |
| Double Fork – High Demand & Pricing | PSO | 3208.36 | 546.64 | 2661.71 | 148.98 | 76.67 | 115.80 | 112.50 |


### PSO-focused analysis and trends
- **Single Fork - Baseline**: PSO achieves the best weighted objective (260.76) and removes cost, queue, charging, and energy penalties entirely. Runtime (29.68 s) is lower than GA (33.71 s) but higher than SA (13.55 s), reflecting greater search effort that pays off in quality.
- **Double Fork - Congested Grid**: PSO trails GA on weighted score (+864.96) and incurs heavy queue time (190.10 min) and cost (2641.46 EGP), signaling premature convergence to congested routes. It still beats GA on runtime (97.30 s vs. 107.18 s) and secures the lowest charging (182.47 min) and energy (172.62 kWh) among the three, but queue penalties dominate the objective.
- **Double Fork - High Demand & Pricing**: PSO again lags GA on weighted score (+488.38) with higher queue time (148.98 min) yet attains the lowest charging (76.67 min) and energy (115.80 kWh). Runtime (112.50 s) edges GA, indicating stable but conservative exploration.
- **Performance pattern**: PSO excels in sparse or simple settings but weakens when congestion and price signals shrink the feasible space; queue penalties suggest insufficient global exploration and weak constraint pressure in dense networks.
