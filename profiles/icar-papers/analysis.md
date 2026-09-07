# Evaluation goal

Evaluate the academic rigor, theoretical novelty, and engineering value of research papers (ArXiv, IEEE, etc.) in **Vehicle Motion Control (VMC) / Chassis Dynamics & Control Theory**.

# Scoring rules & rubric

Calculate the score (0 to 10) based on the VMC Topic Whitelist and academic rigor:

### Topic Weights & Relevance
- **P0 Core VMC Topics (+5)**: Vehicle motion control, control allocation, tire force allocation, yaw stability/DYC, torque vectoring, steer-by-wire/4WS, brake-by-wire/EMB/EHB, active suspension, sideslip angle estimation, road friction estimation, MPC chassis control, fault-tolerant vehicle control.
- **P1 Strongly Related Topics (+3)**: Distributed drive, four-motor control, brake blending, active rear steering, CDC damping, tire parameter estimation, MPC active suspension, robust vehicle control.
- **P2 Methods/Algorithms/AI (+1)**: Kalman filtering (EKF/UKF/MHE), sliding mode control, CBF, PINN/Neural ODE vehicle dynamics, reinforcement learning vehicle control, CarSim/HiL/SiL simulation.
- **Noise / Irrelevant (Score <= 2.0)**: Papers solely focused on generic NLP, pure 2D/3D perception/point clouds without motion control, battery cell chemistry, or consumer robotics unrelated to vehicles.

### Score Scale
- **9-10: Groundbreaking.** Paradigm-shifting VMC theory, novel control allocation or state estimation method with rigorous mathematical proofs and full-scale real-vehicle experimental validation.
- **7-8: High value.** Solid theoretical contribution, novel MPC/observer architecture, significant improvements on high-fidelity vehicle dynamics benchmarks (CarSim/CarMaker), or open-source code/models.
- **5-6: Useful.** Incremental improvements on existing vehicle dynamics models or control algorithms, sound baseline simulations.
- **3-4: Low priority.** Minor variations, weak baseline comparisons, or simplistic 2-DOF linear models without realistic validation.
- **0-2: Noise / Rejected.** Off-topic, lacking mathematical foundation, or completely unrelated to vehicle motion control.

# Tagging Requirement

In the `tags` field, select **2 to 4 tags strictly from the 16 standard categories**:
`#vehicle-motion-control`, `#control-allocation`, `#stability-control`, `#braking`, `#steering`, `#distributed-drive`, `#suspension`, `#state-estimation`, `#tire-road-estimation`, `#control-algorithms`, `#software-defined-chassis`, `#ai-vehicle-dynamics`, `#simulation-validation`, `#supplier-news`, `#research-paper`, `#open-source`.
