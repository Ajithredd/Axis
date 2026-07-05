---
name: ai-agents-architecture
description: Guidelines and design patterns for building stateful, resilient multi-agent systems using graphs and tools.
---

# AI Agents & Multi-Agent Architecture

Standards for building state-driven, resilient, and autonomous agentic workflows.

## 1. Graph & Agentic Design Patterns

- **Router Pattern:** Dispatch user queries to specialized node processors dynamically using intent classification.
- **Orchestrator-Worker (Supervisor):** Designate a coordinator agent to split tasks, assign them to worker agents, and review the final outputs.
- **Evaluator-Optimizer:** Build double-loop workflows where one agent generates outputs and another agent critiques and refines them.

---

## 2. State & Memory Management

- **Typed Graph State:** Define state schemas explicitly using Pydantic or TypedDict. Never use unstructured dictionaries.
- **Node Purity:** Nodes must act as pure state transformers, taking in current state and returning delta updates.
- **Context Compression:** Summarize or slice chat history dynamically to keep LLM context sizes low and cost-efficient.
- **Checkpointing & Persistence:** Persist state snapshots at every node transition to allow workflows to pause, resume, and replay after failures.

---

## 3. Best Practices Checklist

- [ ] Ensure conditional transitions are guided by deterministic code paths where possible, fallback to LLMs only for semantic routing.
- [ ] Use Human-in-the-loop triggers for high-risk actions (e.g., executing code, triggering database writes, external deployments).
- [ ] Trace all graph runs using monitoring tools (e.g., LangSmith) to identify node latency and token costs.
