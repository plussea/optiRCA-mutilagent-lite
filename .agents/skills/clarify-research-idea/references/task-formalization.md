# Task Formalization

Use this reference to turn an informal direction into a Task Contract that constrains later novelty and method claims.

## Start from use-time information

Answer these questions before choosing notation:

1. What entity, event, system, or decision is studied?
2. What information is observable at training/design time and at inference/deployment time?
3. What output, action, estimate, explanation, or artifact is required?
4. What makes one output better than another?
5. Which constraints, costs, risks, or invariances must hold?
6. Against which baseline or current practice is success judged?

Expose target leakage, unavailable inputs, ambiguous supervision, train-test mismatch, and objectives that do not match the paper's claimed benefit.

## Select a suitable formalization

### Predictive or discriminative task

Given data \(\mathcal D=\{(x_i,y_i,c_i)\}_{i=1}^{N}\), learn \(f_\theta\) such that

\[
\hat y_i=f_\theta(x_i,c_i), \qquad
\theta^*=\arg\min_\theta \frac{1}{N}\sum_i \ell(\hat y_i,y_i)+\sum_k\lambda_kR_k(\theta).
\]

Define what \(x\), \(y\), and context \(c\) contain; identify which terms represent the task and which represent the proposed contribution.

### Generative, reconstruction, or representation task

Define the observed object \(x\), conditioning information \(c\), generated or reconstructed object \(\tilde x\), latent representation \(z\), and the fidelity, utility, diversity, or structural criteria. State which competing objectives trade off.

### Optimization, control, or decision task

Define state \(s_t\), observation \(o_t\), action \(a_t\), transition or system response, policy or solver \(\pi_\theta\), reward/cost \(J\), horizon, and hard constraints:

\[
\theta^*=\arg\max_\theta \mathbb E[J(\pi_\theta)]
\quad \text{subject to} \quad g_j(\pi_\theta)\le 0.
\]

### Engineering system or algorithm task

Define the input instance, required output, correctness condition, operating regime, resource budget, failure condition, and complexity or performance measure. Use a constrained mapping or specification when a learned objective is not central.

### Discovery or explanatory study

Do not force an optimization objective. Define variables, relationships, estimand or hypothesis, evidence source, identification assumptions, and observations that would support or contradict the explanation.

## Produce the Task Contract

```markdown
### Task Contract
- One-sentence task:
- Research object and unit of analysis:
- Inputs available at use time:
- Required outputs/actions:
- Data or interaction process:
- Function, model, policy, or procedure:
- Objective or estimand:
- Constraints and costs:
- Primary evaluation measures:
- Strongest baselines/current practice:
- In-scope conditions:
- Out-of-scope conditions:
- Key assumptions:
- Success criterion:
- Critical unknowns:
```

Make the success criterion discriminative: it must explain what evidence would make the proposed work preferable to the strongest relevant alternative.
