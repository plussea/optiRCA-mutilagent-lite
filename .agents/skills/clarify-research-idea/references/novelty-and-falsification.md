# Novelty and Falsification

Use this reference to derive candidate ideas, reduce them to testable contributions, and expose weak novelty before experiments begin.

## Choose an idea route

### New problem or regime

Show that the setting has a property that changes the task rather than merely changing the dataset. Derive the technical challenge and the capability unavailable under existing assumptions.

### Old problem with an ignored condition

Identify the prior assumption, explain where it fails, and show why a new variable, constraint, objective, or mechanism is needed. Do not claim novelty for mentioning a limitation without solving or measuring it.

### New evidence or understanding

Use new data, diagnosis, theory, or causal evidence to change an accepted boundary or explanation. A method need not be wholly new if the scientific conclusion and evidence are genuinely new.

## Force the causal idea chain

For each candidate, complete:

```text
Observed gap
  -> underlying cause
  -> design principle
  -> method component or study move
  -> observable claim
  -> decisive evidence
```

Reject a component that cannot be traced backward to a diagnosed cause or forward to observable evidence.

## Compare candidates without false precision

Rate each candidate from 1-5 on differentiation, causal coherence, feasibility, evidence accessibility, falsifiability, and likely significance. Explain the weakest dimension. Use scores to reveal tradeoffs, not to manufacture certainty.

## Write contribution cards

Limit the final set to 2-3 contributions:

```markdown
### Contribution C1 — [concrete capability or finding]
- Claim:
- Difference from closest anchor:
- Why the difference is necessary:
- Mechanism/design principle:
- Expected evidence:
- Strongest falsifier:
- Boundary:
- Status: VERIFIED / INFERRED / PROVISIONAL
```

Do not split one mechanism into several inflated contributions. Treat datasets, metrics, frameworks, and findings as separate contributions only when each has independent value and evidence.

## Run the Devil's Advocate pass

Attack the selected idea with these questions:

1. Does a close paper already solve the same task under the same information and evaluation assumptions?
2. Could a simpler baseline, data scaling, tuning, or preprocessing explain the expected gain?
3. Is the proposed “new problem” merely a renamed dataset or application?
4. Is the method a module combination without a new principle or interaction?
5. Does each component answer a stated challenge, or was it added after the fact?
6. Which confound or alternative explanation could produce the same observations?
7. What result would falsify the core hypothesis rather than merely lower a metric?
8. Is the required data, compute, hardware, expertise, or evaluation access realistic?

Record rejected alternatives and why they were rejected. Preserve any unresolved attack as a risk, experiment requirement, or scope boundary.

## Define the core hypothesis

Use one sentence:

> Because [diagnosed cause], introducing [design principle] into [task/regime] should produce [observable effect] relative to [strongest alternative], especially under [critical condition].

Pair it with a falsifier:

> The hypothesis is weakened or rejected if [observable outcome under a fair test].
