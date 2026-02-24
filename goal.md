# Project Goal

Come up with a prohject proposal for runtime CPS (cyber-physical system) safety policy verification. PWM actuation path verification can be used as a demonstration use case.

In CPS, we always have both an intended value and a post-compute realized value for certain critical parameters. The state-of-the-art CPS verification approach defines CPS safety properties in STL (Signal Temporal Logic) expressions (or similar other Temporal languages), which gives us a way to verify critical actuation paths. And the low-latency requirement enforces the need for memory consistency of heterogeneous architectures.  (Why heterogeneous? Cause the verifier should be computationally less demanding.) [Present and explain these with proper, accurate, and credible recent publications/literature].

In this project, we will explore how a safety island should be implemented, where we have run-time low-latency safety verification.

## Instructions

* Write the project proposal in the ./proposal/ directory in latex
* Use USENIX template for the proposal.
* The proposal should focus on the problem, the solution and soundness argument of the solution. The proposal should not be a detailed design or implementation plan. Also it should not focus on milestones or timeline. The proposal should be more like a research paper, but with a focus on the problem and solution rather than evaluation for now.
* The techical content of the proposal should be based on recent publications and literature. You should do a thorough literature review to find the most relevant and recent publications to support your proposal. You should also explain how your proposal is different from or better than the existing work.
* Use proper citations and references for the publications you use. You can use bibtex for managing your references.
* The proposal language should be natural and clear. It should not be too robotic or too abstract. It should be technically sound and accurate. I also should avoid unnecessary jargon or buzzwords. No cliche or cringe. It should be professional and academic.
* If possible, add flawless and accurate figures to illustrate your proposal. But only do so if you can do it well. A bad figure is worse than no figure.
