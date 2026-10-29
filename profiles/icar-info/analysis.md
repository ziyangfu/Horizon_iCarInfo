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

### Relevance and evidence
Accept a substantive P0 or P1 chassis topic on its own. A supplier match or a
second topic is useful supporting evidence, not a mandatory condition. Accept
P2 methods and tools when the supplied item explicitly applies them to vehicle
dynamics or chassis control. Recognize Chinese/English synonyms and equivalent
engineering concepts rather than requiring exact whitelist strings.

Use the weights as relevance guidance, not a literal sum or a requirement to
know a famous supplier. Relevant incremental engineering news, validation,
standards, production applications, and supplier developments normally merit
4-6 points. Reserve 0-2 for off-topic or predominantly promotional material.
A short source excerpt limits the detail you can claim; it does not by itself
make a clearly relevant technical announcement off-topic.

### Score Scale
- **9-10: Groundbreaking.** Paradigm-shifting VMC architecture, breakthrough line-controlled chassis mass production (e.g. fully decoupled SBW/EMB, distributed drive torque vectoring), or major Tier-1 platform launch.
- **7-8: High value.** Significant chassis or actuator coordination advancements, high-credibility Tier-1/OEM platform releases, in-depth technical analysis, or major open-source chassis software.
- **5-6: Useful.** Incremental improvements in chassis control/software/hardware, moderate technical announcements, or solid test data.
- **4-5: Worth tracking.** Relevant chassis products, engineering updates, test methods, standards, or technical announcements with limited available detail.
- **3: Low priority.** Weak chassis relevance or little concrete engineering information.
- **0-2: Noise / Rejected.** Fails acceptance gate, or dominated by marketing/PR, sales numbers, price cuts, pure cockpit/infotainment, or pure perception without vehicle motion control.

# Noise Reduction Rules

- **Score <= 2.0 when the primary subject is consumer/commercial noise and no substantive chassis development is reported**:
  vehicle sales, monthly delivery numbers, price cuts, discounts, dealer/dealership, simple model facelift, interior design, cockpit infotainment, battery chemistry, charging stations/network, marketing campaigns, motorsport results, earnings/stock reports.
- Do not reject a technical chassis article merely because it also mentions a vehicle launch, price, delivery, ADAS, or AI. Judge its main technical contribution.
- **Contextual Requirement for Autonomous Driving & AI**:
  Topics like `autonomous driving`, `ADAS`, `trajectory tracking`, `path tracking`, `AI`, and `machine learning` must NOT be automatically rejected, but **MUST be combined with vehicle dynamics, vehicle motion, chassis, tire, steering, braking, suspension, stability, control allocation, or state estimation**. If they appear without chassis/motion context, classify as Noise (score <= 2.0).

# Tagging Requirement

In the `tags` field, select **2 to 4 tags strictly from the 16 standard categories**:
`#vehicle-motion-control`, `#control-allocation`, `#stability-control`, `#braking`, `#steering`, `#distributed-drive`, `#suspension`, `#state-estimation`, `#tire-road-estimation`, `#control-algorithms`, `#software-defined-chassis`, `#ai-vehicle-dynamics`, `#simulation-validation`, `#supplier-news`, `#research-paper`, `#open-source`.
