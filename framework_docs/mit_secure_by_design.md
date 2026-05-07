# MIT Secure-by-Design AI Framework

Source: MIT Sloan Management Review / MIT Initiative on the Digital Economy
"Is Your AI System Secure by Design? 10 Questions to Ask"

---

## Overview

The MIT Secure-by-Design AI Framework provides a set of diagnostic questions organizations should answer to determine whether their AI systems are built with security and reliability as foundational properties rather than afterthoughts. The framework targets leaders and practitioners responsible for deploying AI in consequential settings.

---

## The 10 Diagnostic Questions

### 1. Do you have a clear inventory of all AI systems in production?

Organizations must know what AI systems they are running, where they are deployed, and what data they access. Without a complete inventory, security and compliance gaps cannot be identified or remediated. This includes shadow AI deployments and third-party AI components embedded in vendor products.

### 2. Do you understand the failure modes of each AI system?

AI systems fail differently than traditional software. They can produce plausible but incorrect outputs, degrade silently as data distributions shift, and behave unexpectedly in edge cases. Secure-by-design requires that each system's failure modes are documented, tested, and monitored in production.

### 3. Have you identified the highest-risk decisions your AI systems influence?

Not all AI outputs carry equal risk. A recommendation engine failing is different from an AI system influencing credit, hiring, medical, or safety decisions. Secure-by-design requires mapping AI outputs to downstream decisions and calibrating oversight proportionally to impact severity.

### 4. Do you have human oversight mechanisms where AI outputs drive consequential decisions?

Where AI outputs directly influence high-stakes outcomes, there must be defined human checkpoints. These are not rubber-stamp reviews — they are meaningful opportunities to override, flag, or escalate. The framework requires that these checkpoints be designed into the workflow, not bolted on afterward.

### 5. Can you detect when an AI system is producing anomalous outputs?

Secure-by-design AI requires monitoring that can surface unexpected output patterns — not just infrastructure health metrics. This includes distribution shift detection, confidence calibration monitoring, and alerting when outputs deviate from established baselines.

### 6. Do you have a process for updating or retraining AI systems when their performance degrades?

Models drift. Secure-by-design requires defined triggers for retraining or rollback, with clear ownership and documented criteria for what constitutes unacceptable degradation. Ad-hoc responses to model failure are a governance gap.

### 7. Have you assessed the risks of adversarial inputs to your AI systems?

AI systems can be manipulated through carefully crafted inputs — prompt injection, adversarial examples, data poisoning in training pipelines. Secure-by-design requires that adversarial attack surfaces are identified for each deployed system and that mitigations are in place or explicitly accepted as residual risk.

### 8. Do you understand how your AI systems use and expose sensitive data?

AI systems often process personal, proprietary, or regulated data. Secure-by-design requires data flow mapping: what data enters the model, what data influences outputs, and whether outputs could leak sensitive information through memorization or inference attacks.

### 9. Do you have clear accountability for AI system behavior?

For every AI system in production, there must be a named owner accountable for its behavior, performance, and compliance. Diffuse accountability — shared between data teams, engineering, and business units without clarity — is a governance failure mode that secure-by-design explicitly addresses.

### 10. Do you have a documented incident response plan for AI failures?

When an AI system fails in a consequential way, the response must be faster and more structured than post-hoc investigation. Secure-by-design requires a documented playbook: who is notified, what immediate containment actions are available, how affected parties are informed, and what root cause analysis is required before redeployment.

---

## Application

These questions function as an audit instrument. A "no" or "partial" answer to any question identifies a specific design gap. The framework is intentionally question-based rather than prescriptive: different organizations will satisfy each criterion differently depending on their risk profile, sector, and AI use cases.

High-maturity organizations should be able to answer all 10 with documented evidence. Gaps in questions 3, 4, and 7 are considered highest-priority for organizations deploying AI in regulated or safety-critical contexts.
