# Firecracker vs OpenSandbox

## 1. Overview

This document provides a technical comparison between Firecracker and OpenSandbox as sandbox technologies for running isolated AI agent sub-tasks (e.g., Python execution, shell tools, web search, file operations) in a server-side multi-tenant environment.

The comparison is framed around high-isolation AI agent platforms such as Noesium, where:

* Agents may execute arbitrary user-influenced code
* Strong tenant isolation is required
* Tool execution must be sandboxed
* Execution may need auditing and replay

---

## 2. Architectural Model

### Firecracker

* Type: MicroVM (KVM-based)
* Isolation level: Virtual machine
* Guest kernel: Independent Linux kernel per VM
* Designed for: Secure multi-tenant serverless workloads

Each workload runs inside a lightweight VM with its own kernel, virtualized CPU, memory, and block devices.

### OpenSandbox

* Type: Enhanced container sandbox
* Isolation level: Container (shared host kernel)
* Guest kernel: Shared with host
* Designed for: High-density cloud-native execution

Workloads run in hardened containers with security policies layered on top of standard container isolation.

---

## 3. Isolation & Security

| Dimension           | Firecracker                     | OpenSandbox                      |
| ------------------- | ------------------------------- | -------------------------------- |
| Kernel isolation    | Full (independent guest kernel) | Shared host kernel               |
| VM boundary         | Yes                             | No                               |
| Escape resistance   | Very high                       | Depends on host kernel hardening |
| Multi-tenant safety | Strong                          | Moderate to strong               |
| Attack surface      | Minimal device model            | Container runtime + kernel       |

Firecracker provides hardware-virtualized isolation via KVM, reducing cross-tenant attack risk.

OpenSandbox relies on container-level isolation with seccomp, namespaces, cgroups, and runtime policies.

For adversarial or untrusted code execution (e.g., arbitrary Python), VM-level isolation is significantly stronger.

---

## 4. Startup Performance

| Metric           | Firecracker | OpenSandbox          |
| ---------------- | ----------- | -------------------- |
| Cold start       | ~100–300ms  | Typically <50ms      |
| Snapshot restore | Supported   | Container-level only |
| Memory footprint | Higher      | Lower                |

OpenSandbox generally offers faster startup and higher density.

Firecracker supports snapshotting, which can reduce startup latency when pre-warmed images are used.

---

## 5. Resource Density & Scalability

### Firecracker

* Each workload consumes VM memory overhead
* Lower per-node density
* More predictable isolation

### OpenSandbox

* High container density
* Better CPU/memory packing efficiency
* Native Kubernetes compatibility

If thousands of lightweight tool invocations are expected per second, container-based isolation may scale more efficiently.

---

## 6. Operational Complexity

| Dimension              | Firecracker                | OpenSandbox                |
| ---------------------- | -------------------------- | -------------------------- |
| Deployment complexity  | Higher                     | Lower                      |
| Kubernetes integration | Requires integration layer | Native container model     |
| Observability          | VM-level tooling required  | Standard container tooling |
| Debugging              | VM-level                   | Container-level            |

Firecracker introduces VM lifecycle management complexity (image building, snapshot management, network setup).

OpenSandbox fits directly into container orchestration systems.

---

## 7. Suitability for AI Agent Tool Execution

### Firecracker Strengths

* Safe execution of arbitrary user-provided Python
* Strong isolation for shell access
* Better protection against kernel exploits
* Suitable for high-trust multi-tenant SaaS
* Enables effect replay via snapshotting

### OpenSandbox Strengths

* Lightweight execution for low-risk tools (grep, read-only file access)
* Fast scaling of high-frequency subagent tasks
* Lower operational overhead

---

## 8. Deterministic Execution & Replay Potential

Firecracker enables:

* VM snapshotting
* Reproducible execution environments
* Effect recording at VM boundary

OpenSandbox relies on container reproducibility and external logging.

If the architecture emphasizes deterministic projection models and effect graph replay, VM-level isolation aligns more naturally with that design philosophy.

---

## 9. Risk-Based Runtime Strategy

A hybrid approach may be optimal:

* Low-risk tools → Container sandbox
* High-risk tools (Python, shell, networked execution) → MicroVM sandbox

This allows balancing cost, performance, and security.

---

## 10. Decision Matrix

| Scenario                                        | Recommended Technology |
| ----------------------------------------------- | ---------------------- |
| Multi-tenant SaaS with arbitrary code execution | Firecracker            |
| Internal enterprise deployment                  | OpenSandbox            |
| High-frequency lightweight tasks                | OpenSandbox            |
| Strong isolation with auditability              | Firecracker            |
| AI-native effect graph replay system            | Firecracker            |

---

## 11. Strategic Consideration

If the platform vision prioritizes:

* Security as a first-class primitive
* Deterministic external effect modeling
* Multi-tenant adversarial robustness

MicroVM-based isolation is architecturally aligned.

If the platform prioritizes:

* Throughput
* Cost efficiency
* Cloud-native operational simplicity

Container-based sandboxing may be more pragmatic.

---

## 12. Summary

Firecracker provides stronger isolation guarantees at the cost of complexity and density.

OpenSandbox provides higher efficiency and simpler integration but shares the host kernel, which reduces the theoretical isolation boundary.

The correct choice depends on the threat model, scale target, and architectural philosophy of the AI agent platform.
