# Anchor-Paper Positioning

Use this reference to select and compare 3-5 papers that constrain the task, novelty claim, experimental contract, and paper architecture.

## Search on multiple axes

Search combinations of:

- task and output;
- data regime or application context;
- closest mechanism or model family;
- known failure mode or ignored condition;
- benchmark, metric, deployment constraint, or theoretical assumption.

Use current academic-search or web tools when the user has not supplied adequate papers. Prefer publisher pages, DOI records, recognized repositories, and the papers themselves. Use reviews for field mapping, then verify central claims against primary papers.

## Assign anchor roles

Select the smallest set that covers these roles:

1. **Problem anchor** — closest task definition and motivation.
2. **Method anchor** — closest design principle or technical mechanism.
3. **Closest competitor** — strongest threat to the proposed novelty.
4. **Experiment anchor** — credible benchmark, protocol, metric, or evidence order.
5. **Architecture anchor** — useful high-level argument and section structure; optional.

A paper may occupy several roles. Do not pad the list to reach five.

## Verify before using

Record the exact title, authors, year, venue/repository, DOI or stable URL, paper type, and verification source. Mark inaccessible or metadata-only records `UNVERIFIED`. Never complete missing bibliographic fields by guesswork.

## Extract a stable comparison frame

For each paper, extract:

- `WHY`: problem, stakes, and operating assumptions;
- `HOW`: central mechanism and design principle;
- `WHAT`: demonstrated result or capability;
- `LIMIT`: explicit limitation plus limitations inferred from evidence boundaries;
- `TRANSFER`: reusable task definition, evaluation logic, or structural pattern.

Build this matrix:

| Role | Paper | Task/assumptions | WHY | HOW | WHAT/evidence | LIMIT | Relation to our idea | Verified link |
|---|---|---|---|---|---|---|---|---|

Compare under aligned data, information access, supervision, metrics, and resource assumptions. Similar module names do not imply identical problems; different names do not imply novelty.

## Derive a defensible gap

Classify the gap:

- **Capability gap:** an important output or behavior remains unsupported.
- **Condition gap:** performance or validity breaks under a neglected regime.
- **Mechanism gap:** evidence shows a failure, but its cause is not handled.
- **Evidence gap:** a claim lacks fair comparison, diagnosis, or boundary testing.
- **Integration gap:** components exist separately, but their principled interaction is unresolved.

State what is known, what is not established, why that absence matters, and what evidence could close it. Do not equate “not found in this search” with “never studied.”

## Learn architecture without imitation

Extract only high-level traits from an architecture anchor: context width, claim order, evidence ladder, section balance, hedging level, and transition logic. Do not copy distinctive phrases, sentences, or a paper-specific rhetorical fingerprint.
