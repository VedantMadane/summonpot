# Agent execution and context management research

**Research cutoff: 2026-09-07. Planned design, not shipped functionality.**

## Decision

Keep Summonpot's endpoint as the complete executable contract: request model, fixed goal,
declared operations and bindings, response model, and an ellipsis body. Improve the private
execution loop and the context it receives; do not introduce a public agent, graph, planner,
workspace, or memory-manager configuration surface.

The roadmap already covered producer-constrained agent choices, authenticated application
context, and optional larger execution harnesses. It did not give working-context construction,
compaction, persistent-memory isolation, or their evaluation gates a concrete delivery track.
The new [agent execution and context track](../ROADMAP.md#agent-execution-and-context-track)
fills that gap without moving the hardening prerequisites behind agent features.

There is no defensible universal "best memory stack" in this evidence. Current SDKs expose
useful mechanisms, while recent benchmarks distinguish factual recall from subsequent correct
action and show that memory utility must be evaluated together with poisoning risk.[25][24]
Our recommendation is therefore **bounded working context first, opt-in continuity second,
measured delegation later**. This is an architectural judgment, not a benchmark result.

## Research method and limits

- Check current primary documentation against dated releases and tagged source. The upstream
  snapshot includes Pydantic AI **v2.40.0, September 5, 2026**, and Pydantic AI Harness
  **v0.29.0, September 4, 2026**.[1][2]
- Treat undated official documentation as **accessed 2026-09-07**, not as proof of a feature's
  launch date. A protocol suffix containing 2025 is not automatically obsolete: Anthropic's
  current reference explicitly explains simultaneously supported versions and variants.[27]
- Inspect 2026 research, including September context-compaction work; distinguish published
  mechanisms, current provider protocols, and experimental techniques. Paper findings below
  are author-reported, not independently reproduced performance claims.[18][19]
- Do not infer support in Summonpot from a feature's existence upstream. No dependency or
  runtime implementation is changed by this roadmap update. An isolated Python 3.13 probe
  imported the exact Pydantic AI/Harness releases above and constructed
  `TieredCompaction(tiers=[ClearToolResults(max_tokens=1000)], target_tokens=1000)`.
  That verifies construction only—not model behavior, security, or Summonpot compatibility.
- No authenticated provider conformance tests, benchmark reproduction, or comparative latency
  measurements were performed. Mutable docs, model support, SDK versions and retention terms
  must be checked again when implementing an adapter.

## What is available now, and what it does not guarantee

### 1. Layered compaction is an available building block

Pydantic AI's tagged compaction documentation describes capabilities for reducing message
history. Harness v0.29.0 provides tiered compaction, combining cheaper clearing/truncation
with more expensive summarization strategies.[11][8]

Google ADK's current guide distinguishes token-triggered compaction from turn-based sliding
windows, gives token-based compaction priority when both apply, and allows retaining recent
raw events.[23] These are useful mechanisms, not proof that the same thresholds or summary
policy work for every endpoint.

**Adopt:** construct a bounded view for each legal decision. Count instructions, tool schemas,
evidence and response/reasoning headroom, not just conversational turns. Prefer selecting
relevant results and removing redundant payloads before summarizing. Record policy versions
and measure cumulative loss across repeated compactions.

**Do not adopt:** one global summary as canonical state. Exact identifiers, validated operation
results, pending effects, approvals and call reservations belong outside generated prose.
If protected contract context cannot fit, fail within the declared budget rather than evict it.

### 2. Provider compaction is not a portable transcript format

OpenAI documents both in-stream server compaction through `context_management` and explicit
`/responses/compact`. Its compaction item is opaque; continuation rules differ between an
explicit input array and `previous_response_id` chaining.[17]

Anthropic's Python v1 migration guide removes the old tool-runner `compaction_control`
argument in favor of server-side compaction.[15] Consequently, older SDK examples using
that argument must not become an implementation plan without an explicit version check.

**Adopt:** provider-specific continuation and replay adapters behind the existing abstraction,
with a portable context-selection path. Keep an authoritative server-owned execution record
and permitted evidence independent of opaque provider state. Unsupported model/provider
combinations must reject or choose an eligible path before effects begin.

**Do not adopt:** translating encrypted/native compaction objects into generic summary text,
assuming they can migrate between providers, or replaying an effect to reconstruct context.

### 3. Progressive tool discovery reduces disclosure cost, not authority

Anthropic currently lists its regex and BM25 tool-search variants as GA and documents deferred
definitions being expanded in the conversation rather than the cached tools prefix.[27]
OpenAI supports hosted and client-executed tool search; individually deferred functions still
expose their names/descriptions while deferring parameter schemas. Newly discovered definitions
are appended at the end of context to preserve prior cache content.[30]

**Adopt:** eager schemas for small endpoint capability sets. For larger sets, evaluate
just-in-time discovery over only declared, currently legal operations. Recheck bindings,
readiness, producer membership and reservations at invocation, even if the model saw a schema
before a compaction or state transition.

**Do not adopt:** a global tool search that expands the endpoint's capabilities, or treating
schema visibility as authorization. Prompt caching is an optimization, not user memory or an
access-control mechanism. Provider retention and cache scope require separate review.

### 4. Runtime context, sessions and memory are different resources

OpenAI Agents SDK explicitly separates local context/dependencies from information supplied
to the model; passing local context is not automatic prompt injection.[14]
Pydantic Harness provides persistent memory and namespacing, but those interfaces do not by
themselves establish the provenance or authorization policy an API framework needs.[10]
LangSmith's store-auth guide states that namespaces are shared by default and requires custom
authentication plus namespace validation/rewriting for user isolation; thread isolation and
store isolation are separate controls.[22]

**Adopt four distinct lifetimes and trust levels:**

| Resource | Owner and role | What must not happen |
|---|---|---|
| Working context | Derived model-visible request/evidence projection | Its summaries redefine the endpoint contract |
| Authenticated application context | Server-resolved principal, scoped resources and policy | A model-provided ID or memory note establishes authority |
| Execution state | Canonical values, reservations, results and effect receipts | Conversation replay silently repeats a completed write |
| Optional persistent memory | Typed, scoped facts/notes with provenance and lifecycle | Remembered text becomes credentials, policy or proof of success |

Large evidence can live behind request-scoped handles, but those handles need access checks,
expiry, version/provenance and bounded reads. The model receives neither a raw filesystem nor
an unrestricted object store.

Memory stays off by default and is referenced through exact declared operations. Separate read
permission from permission to commit a model-authored note. Apply scope and freshness filters
before ranking; semantic similarity is not authority. Require correction, supersession,
concurrency control, retention and deletion across derived summaries/indexes/caches. Queued
consolidation must not resurrect deleted records. A backend lacking required lifecycle
operations is not an eligible adapter.

### 5. Delegation needs more than isolated histories

Pydantic Harness documents isolated subagent histories and configurable usage forwarding.
Giving a delegate explicit usage limits changes the default forwarding behavior, so a child
budget must not be mistaken for aggregate parent accounting.[9]

OpenAI's native Multi-agent feature is beta. Its documented concurrency limit is not a bound
on total spawned agents or tree depth, and all agents share the request's available tools.[16]
That does not satisfy a contract requiring individually narrowed child authority.

**Adopt later:** typed bounded sub-operations with minimal evidence, a subset of parent
capabilities, shared effect reservations and aggregate accounting. Cap total spawned tasks,
depth, concurrency, turns, tokens, cost and wall time. Reserve before dispatch; account for
in-flight work and cancellation uncertainty. Children return claims plus verifiable evidence,
not assumed successful outcomes.

**Do not adopt:** a public subagent roster/configuration bag, ambient credentials, general
workspaces, or an automatically enabled swarm. A single bounded loop remains the baseline.
Parallelism should earn inclusion on independently decomposable endpoint workloads.

### 6. Asynchronous tools and steering add lifecycle obligations

Current OpenAI documentation allows the model to continue while an application-executed async
tool runs. The application still owns that job; the provider does not manage it.[28]
Mid-turn steering is model/transport-specific, does not undo earlier effects or cancel started
tools, and applies token/tool limits separately to each continuation response.[29]

**Adopt only when needed:** explicit pending-call accounting, late-result rules and a final-output
barrier for required effects. The aggregate endpoint budget survives provider continuations.
Input updates never mutate the endpoint's fixed goal or expand its authority. Returning a valid
response model cannot stand in for resolving the declared completion conditions.

## Recent research: useful experiments, not default architecture

| Work inspected | Evidence and interpretation | Summonpot experiment |
|---|---|---|
| Compact-Memory LLM Agents via Online Max-Member Clustering and Atom-Aware Packing, September 2026 | Combines online max-member memory merging with atom-aware grouped context packing; its reported quality/token advantages concern the tested compact-memory regimes.[18] | Compare merging and packing policies under matched budgets, retaining source references; do not assume a universal retrieval advantage. |
| KVMem: Virtualizing Million-Token Agent Workspaces on a Consumer GPU, September 2026 | Virtualizes historical KV state across GPU, host memory and NVMe, selectively retrieving blocks into a bounded active view.[19] | Treat this as inference-infrastructure research requiring access to model KV state, not a portable hosted-API context adapter or a new benchmark. |
| The Compaction Cliff in Long-Running AI Agent Memory, August 2026 | Studies safety-rule loss across repeated compaction and proposes type-specific retention, decomposition and retrieval policies.[20] | Test exact constraint retention across repeated compactions; enforce authority outside model summaries regardless of retention quality. |
| Addressable Recall Compaction for Long Context-Window Control in AI Agents, July 2026 | Keeps tool observations in an append-only, ID-addressable archive and recalls stored observations without re-executing tools; efficiency claims include a hardware-cost model rather than only measured serving times.[21] | Evaluate scoped evidence handles and bounded exact recall; add authentication and effect-state safeguards rather than treating archive access as authorization. |
| MemoryArena, 2026 | Couples memory with interdependent actions across sessions; strong recall performance does not establish successful subsequent action.[25] | Test facts learned earlier being applied to later valid operations, not just recalled in answers. |
| MemGauge, August 2026 | Separately varies memory writing, management and retrieval under clean/poisoned conditions; finds stage-dependent utility/risk trade-offs in its tested systems.[24] | Measure benign utility and poisoning success for each lifecycle stage, not a single memory accuracy score. |
| Recursive Language Models, v3 revision in 2026 | Externalizes prompts into a programmatic environment and recursively processes snippets; performance claims apply to the studied tasks.[26] | Explore bounded evidence decomposition behind an experimental adapter, not unrestricted Python orchestration. |

Recursive context processing and learned memory are not prerequisites for Summonpot. Their
useful structural idea is selective access to external evidence with compact intermediate
results. Generated code, adaptive memory controllers or recursive subcalls do not get to bypass
bindings, output validation, effect reservations or budgets. A promising paper is a reason to
run an experiment, not to expand the public API or claim a measured improvement here.

## Delivery order and acceptance gates

1. **After boundary hardening:** request-local context assembly, bounded result projections,
   evidence handles, loop non-progress detection and full-request budgets. Establish a baseline
   before introducing compaction. Keep the direct path model-free.
2. **After validated chains and choices:** readiness-aware tool discovery, selective evidence
   retrieval and compaction that preserves exact result/choice authority. Provider adapters are
   optional and version-tested; none weakens the local invocation kernel.
3. **After authenticated application context:** opt-in scoped continuity and persistent memory,
   including lifecycle and adversarial isolation tests. Persistence does not imply durable
   execution or permission to replay side effects.
4. **After shared accounting and isolation:** benchmark bounded delegation and advanced context
   experiments. Do not wait for a large harness to deliver the useful request-local slices.

Every slice needs a fixed dataset of representative endpoint tasks and deterministic assertions
for permitted operations, exact bindings, successful effects and output provenance. Include:

- Repeated compaction with long-lived constraints, exact IDs and stale-versus-current facts.
- Oversized results, failed evidence retrieval and attempts to recover an evicted write result.
- Instructions embedded in retrieved documents, tool outputs and model-authored memories.
- Cross-tenant guessed handles, private-data exposure in streams/traces, and deletion resurrection.
- Concurrent children, exhausted reservations, late completion and timeout uncertainty.
- Provider continuation/replay differences, unsupported features and changed contract versions.

Measure task/effect correctness first, then exact-fact retention, retrieval success, repeated
calls, context occupancy, summarizer/child/parent usage, cache reads/writes, latency and cost.
Use model judges only for supplementary semantic quality, never authority or effect completion.
Report distributions and failed cases, not only average token savings. Keep telemetry redacted.

## Conclusion

The useful direction is not "more agents" or "remember everything." It is a small internal
execution loop receiving the right permitted evidence, with exact state and authority retained
outside its context. This can be added incrementally while the endpoint declaration remains
unchanged. All proposed guarantees above are acceptance criteria for future work.

## Sources

[1] https://github.com/pydantic/pydantic-ai/releases/tag/v2.40.0
[2] https://github.com/pydantic/pydantic-ai-harness/releases/tag/v0.29.0
[8] https://raw.githubusercontent.com/pydantic/pydantic-ai-harness/v0.29.0/docs/compaction.md
[9] https://raw.githubusercontent.com/pydantic/pydantic-ai-harness/v0.29.0/docs/subagents.md
[10] https://raw.githubusercontent.com/pydantic/pydantic-ai-harness/v0.29.0/docs/memory.md
[11] https://raw.githubusercontent.com/pydantic/pydantic-ai/v2.40.0/docs/capabilities/compaction.md
[14] https://openai.github.io/openai-agents-python/context
[15] https://github.com/anthropics/anthropic-sdk-python/blob/main/MIGRATION.md
[16] https://developers.openai.com/api/docs/guides/tools-multi-agent
[17] https://developers.openai.com/api/docs/guides/compaction
[18] https://arxiv.org/html/2609.04915v1
[19] https://arxiv.org/html/2609.04852v1
[20] https://arxiv.org/html/2608.22752v1
[21] https://arxiv.org/html/2607.25066v1
[22] https://docs.langchain.com/langsmith/store-auth
[23] https://adk.dev/context/compaction
[24] https://arxiv.org/html/2608.30177v1
[25] https://arxiv.org/html/2602.16313v1
[26] https://arxiv.org/html/2512.24601v3
[27] https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference
[28] https://developers.openai.com/api/docs/guides/async-tool-calling
[29] https://developers.openai.com/api/docs/guides/steering
[30] https://developers.openai.com/api/docs/guides/tools-tool-search
