# Interactive Heuristics

Use this reference to make `guided` mode genuinely interactive. The goal is to help the researcher discover the shape of the idea through constrained questions, not to collect answers passively.

## Triage the idea maturity

Classify the user state and start with the question type that removes the largest uncertainty.

| User state | Symptom | First question target | Useful output |
|---|---|---|---|
| Broad interest | Topic area but no task | Research object and consequential setting | Candidate task family |
| Question without task | Motivation exists but input/output are vague | Use-time information and required output | Task Contract draft |
| Method without positioning | User has modules or model idea | Failure mode the method is meant to fix | Gap and design principle |
| Papers without idea | User has references but no contribution | Shared limitation or boundary condition | Defensible gap |
| Nearly complete idea | Task, method, and papers exist | Falsifier and closest competitor | Audit plan |

If the state is mixed, start with task definition unless the user has already supplied a reliable Task Contract.

## Ask high-information questions

A high-information question should change at least one of these fields: task, gap, hypothesis, contribution, evidence path, or scope boundary.

Prefer one question per turn. Good questions have this form:

```markdown
Current bottleneck: [what is preventing the idea from becoming precise]
Question: [one decision the user can answer]
Why this matters: [which part of the idea architecture it constrains]
If unsure, choose one:
- Option A: [plausible direction and implication]
- Option B: [plausible direction and implication]
- Option C: [plausible direction and implication]
```

Do not ask for generic preferences such as "tell me more." Ask for a discriminating choice, example, failure case, baseline, output, or evidence standard.

## Maintain a Working Idea Canvas

After each meaningful answer, update this compact canvas. Keep fields short and attach provenance labels.

```markdown
### Working Idea Canvas
- Task: [PROVIDED/INFERRED/UNKNOWN]
- Use-time input and output: [...]
- Consequential friction: [...]
- Underlying cause: [...]
- Required capability: [...]
- Anchor papers or anchor roles: [...]
- Core hypothesis: [...]
- Candidate contributions: [...]
- Strongest baseline or counter-position: [...]
- Evidence needed: [...]
- Critical risk or unknown: [...]
- Next question: [...]
```

Use the canvas to show progress and prevent circular brainstorming. Do not let a polished sentence hide an `UNKNOWN`.

## Heuristic loops

### Mathematical compression

Turn a topic into:

`object -> available input -> required output -> success criterion -> constraint`

Ask: "At deployment or use time, what information is actually available?" This catches target leakage, impossible assumptions, and unclear metrics early.

### Causal framing

Turn motivation into:

`background -> friction -> unresolved cause -> required capability -> research move`

Ask: "What property of the setting makes generic methods fail?" This prevents motivations that only say the topic is important.

### Literature coordinate

Turn papers into roles:

`problem anchor / method anchor / closest competitor / experiment anchor / architecture anchor`

Ask: "Which paper would a reviewer most likely say already solved this?" This reveals the real novelty threat.

### Contribution compression

Turn components into contributions:

`observed gap -> cause -> design principle -> component -> observable claim -> decisive evidence`

Ask: "If this component is removed, which claim becomes impossible to support?" Remove components that do not answer this question.

### Reviewer simulation

Before accepting a contribution, ask the idea to survive these attacks:

1. Closest competitor: same task, same information, same metric?
2. Simplest baseline: tuning, scaling, preprocessing, or data can explain the gain?
3. Alternative explanation: a confound can produce the same observation?
4. Negative case: where should the method fail or stop helping?
5. Falsifier: what result would weaken the core hypothesis?

If the answer is weak, mark the contribution `PROVISIONAL` and convert the weakness into a required experiment, limitation, or narrower claim.

### Figure preflight

Before drawing the core figure, require each visual module to pass:

`challenge -> design principle -> module/procedure -> output behavior -> validation hook`

Ask: "Can the figure show why this module exists without reading the methods section?" Remove decorative modules and unsupported arrows.

## Rescue moves for common weak ideas

- If the idea is only "add module A+B+C," ask for the diagnosed failure each module fixes.
- If novelty is "few studies exist," ask why the missing study changes a decision, capability, or boundary.
- If the task is too broad, freeze one unit of analysis and one primary output.
- If the method is impressive but unmotivated, derive the setting property that makes it necessary.
- If the expected result is only a metric gain, require a diagnostic, ablation, or stress test that supports a mechanism.
- If the user cannot name anchor papers, search or ask for one known closest method, one benchmark, or one target venue to seed the coordinate system.

## Interaction discipline

Keep the user's agency explicit. Say when a choice is a scientific decision rather than a writing preference. When making an assumption, label it `PROVISIONAL` and explain what would confirm or revise it. Stop at checkpoints when the next phase would freeze the task, hypothesis, or method architecture.
