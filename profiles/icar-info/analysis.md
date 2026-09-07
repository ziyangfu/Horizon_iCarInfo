# Evaluation goal

Evaluate the importance, technical depth, and engineering value of news, announcements, and developments in **Vehicle Motion Control (VMC) / Chassis Motion Control (CMC)** and intelligent chassis engineering for automotive researchers, chassis control engineers, and industry analysts.

# Scoring rules & rubric

Calculate the score (0 to 10) based on the VMC Topic & Supplier Whitelist and acceptance logic:

### Additive Scoring Weights
- **P0 Topic hit**: +5
- **P1 Topic hit**: +3
- **P2 Topic hit**: +1
- **P3 Topic hit**: 0 (only adds value when combined with P0/P1)
- **P0 Supplier hit**: +4
- **P1 Supplier hit**: +2
- **P2 Supplier hit**: +1
- **P3 OEM hit**: 0 (only adds value when combined with P0/P1 Topic)

### Strict Acceptance Gate
An item MUST satisfy at least one of the following criteria to be considered acceptable (score >= 4.0):
1. Hit a **P0 Topic**
2. Hit a **P1 Topic** AND hit a **P0/P1 Supplier**
3. Hit a **P1 Topic** AND another **P1 Topic**
4. Hit a **P2 Topic** AND hit a **P0 Supplier**
5. Hit a **P3 OEM** AND hit a **P0 Topic**
6. Hit a **P3 OEM** AND hit **2+ P1 Topics**

**If an item fails all 6 acceptance conditions above, assign score <= 2.0 (Noise / Off-topic).**

### Score Scale
- **9-10: Groundbreaking.** Paradigm-shifting VMC architecture, breakthrough line-controlled chassis mass production (e.g. fully decoupled SBW/EMB, distributed drive torque vectoring), or major Tier-1 platform launch.
- **7-8: High value.** Significant chassis or actuator coordination advancements, high-credibility Tier-1/OEM platform releases, in-depth technical analysis, or major open-source chassis software.
- **5-6: Useful.** Incremental improvements in chassis control/software/hardware, moderate technical announcements, or solid test data.
- **3-4: Low priority.** Minor variations, routine announcements, shallow reports, or weak technical depth.
- **0-2: Noise / Rejected.** Fails acceptance gate, or dominated by marketing/PR, sales numbers, price cuts, pure cockpit/infotainment, or pure perception without vehicle motion control.

# Noise Reduction Rules

- **Force score <= 2.0** for consumer/commercial noise:
  vehicle sales, monthly delivery numbers, price cuts, discounts, dealer/dealership, simple model facelift, interior design, cockpit infotainment, battery chemistry, charging stations/network, marketing campaigns, motorsport results, earnings/stock reports.
- **Contextual Requirement for Autonomous Driving & AI**:
  Topics like `autonomous driving`, `ADAS`, `trajectory tracking`, `path tracking`, `AI`, and `machine learning` must NOT be automatically rejected, but **MUST be combined with vehicle dynamics, vehicle motion, chassis, tire, steering, braking, suspension, stability, control allocation, or state estimation**. If they appear without chassis/motion context, classify as Noise (score <= 2.0).

# Tagging Requirement

In the `tags` field, select **2 to 4 tags strictly from the 16 standard categories**:
`#vehicle-motion-control`, `#control-allocation`, `#stability-control`, `#braking`, `#steering`, `#distributed-drive`, `#suspension`, `#state-estimation`, `#tire-road-estimation`, `#control-algorithms`, `#software-defined-chassis`, `#ai-vehicle-dynamics`, `#simulation-validation`, `#supplier-news`, `#research-paper`, `#open-source`.
