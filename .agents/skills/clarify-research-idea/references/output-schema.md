# Research Idea Brief Output Schema

Use this reference to compile the final artifact. Preserve provisional content and unresolved decisions instead of smoothing them away.

## Required structure

```markdown
# Research Idea Brief — [working title]

> Status: CONFIRMED / PROVISIONAL / BLOCKED
> Mode: guided / synthesize
> Scope: [domain and intended paper type]
> Evidence cutoff: [date or supplied corpus]

## 1. Working Idea Canvas
## 2. One-sentence research proposition
## 3. Task Contract
## 4. Background and consequential motivation
## 5. Framing Intent and counter-position
## 6. Problem properties and technical challenges
## 7. Anchor-paper positioning matrix
## 8. Defensible knowledge gap
## 9. Core hypothesis and falsifier
## 10. Alternatives considered and rejected
## 11. Proposed method or study architecture
## 12. Contributions (2-3 cards)
## 13. Challenge-solution-claim map
## 14. Claim-evidence matrix
## 15. Core-figure Mermaid draft
## 16. Risks, confounds, limitations, and negative cases
## 17. Unresolved decisions and next actions
## 18. Checkpoint record and readiness audit
```

Include stable links for verified anchor papers. Cite sources next to supported claims when the output environment supports citations.

## Build the claim-evidence matrix

| Claim | Contribution | Required comparison | Ablation/diagnostic | Stress/boundary test | Metric or observation | Falsifying outcome | Status |
|---|---|---|---|---|---|---|---|

Require at least one decisive row per contribution. Use `TBD` when experimental choices are intentionally deferred; do not invent expected numbers.

## Record checkpoints

| Checkpoint | Decision | User-confirmed? | Remaining change risk |
|---|---|---|---|
| 1. Task Contract | ... | YES / NO | ... |
| 2. Positioning and Hypothesis | ... | YES / NO | ... |
| 3. Final Idea Architecture | ... | YES / NO | ... |

In `synthesize` mode, an unconfirmed checkpoint keeps the overall status `PROVISIONAL` even when the brief is complete.

## Preserve the interaction path

In `guided` mode, summarize the reasoning path without transcript bloat:

```markdown
### Working Idea Canvas
- Starting state:
- Key decisions made:
- Decisions still provisional:
- Highest-impact user choice:
- Current next question or next action:
```

This section should help later experiment-design or manuscript-writing workflows understand why the idea took its current shape.

## Audit readiness

Score each dimension from 1-5 and justify the score with one diagnostic sentence:

- **Clarity:** task, scope, and success criterion are unambiguous.
- **Positioning:** closest work and assumptions are verified and fairly compared.
- **Novelty:** the difference is concrete and survives the closest-alternative attack.
- **Feasibility:** data, tools, resources, and evaluation access are realistic.
- **Falsifiability:** the core hypothesis has an observable disconfirming outcome.
- **Consistency:** challenges, principles, components, claims, and evidence align.

Set status:

- `CONFIRMED`: all checkpoints confirmed; no critical `UNKNOWN`; each contribution has a credible evidence path.
- `PROVISIONAL`: useful architecture exists, but confirmation or important verification remains.
- `BLOCKED`: a critical contradiction, unavailable dependency, or unresolvable task ambiguity prevents a defensible idea.

Do not average away a critical failure. List the highest-leverage next action first.

## Prepare the handoff

End with a compact handoff contract:

```markdown
### Handoff Contract
- Frozen task definition:
- Frozen core hypothesis:
- Contributions to test:
- Required anchor papers:
- Minimum decisive experiments:
- Assumptions that experiments must check:
- Claims that manuscript writing must not exceed:
- Figure elements approved for production:
```

Use this block as the input to later experiment-design, implementation, paper-writing, and presentation workflows.
