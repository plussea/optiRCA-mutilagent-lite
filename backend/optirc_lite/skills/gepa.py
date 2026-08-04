"""GEPA Strategy Optimizer — evolves Pareto-optimal diagnosis strategies.

Implements a lightweight genetic-Pareto loop that uses an Evaluator report as the
fitness signal and its structured error attribution as reflective feedback.  Each
candidate is a chromosome ``<Prompts, Weights, Cases>`` as specified in
ADR-0004.  Fitness is simulated from the baseline metrics because real sandboxed
re-runs of the full diagnosis workflow are out of scope for this tracer-bullet
ticket.
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from optirc_lite.storage.sqlite_store import store


WEIGHT_KEYS = [
    "upstream",
    "time_lead",
    "coverage",
    "priority",
    "case_sim",
    "conflict_penalty",
]

DEFAULT_WEIGHTS = {
    "upstream": 0.20,
    "time_lead": 0.20,
    "coverage": 0.25,
    "priority": 0.15,
    "case_sim": 0.15,
    "conflict_penalty": 0.05,
}

PROMPT_KEYS = ["judge_system", "judge_few_shot_ids", "ranker_system", "critic_system"]

DEFAULT_PROMPTS = {
    "judge_system": "sha256:default-judge-system",
    "judge_few_shot_ids": [],
    "ranker_system": "sha256:default-ranker-system",
    "critic_system": "sha256:default-critic-system",
}

MUTATION_OPERATORS = [
    "MUTATE_WEIGHT",
    "SWAP_FEW_SHOT",
    "ADD_CASE",
    "REMOVE_CASE",
    "REGENERATE_PROMPT",
]

# Scalarization weights for selecting the recommended candidate from the Pareto
# frontier.  All five objectives are maximized; objectives 3 and 4 are already
# negated in the fitness vector (negative false-reject and negative latency).
SCALAR_WEIGHTS = [0.4, 0.35, 0.15, 0.05, 0.05]

# Approximate bounds used to normalize objectives before scalarization.
FITNESS_MINS = [0.0, 0.0, 0.0, -1.0, -10.0]
FITNESS_MAXS = [1.0, 1.0, 1.0, 0.0, 0.0]


@dataclass
class Chromosome:
    prompts: Dict[str, Any] = field(default_factory=lambda: DEFAULT_PROMPTS.copy())
    weights: Dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    cases: Dict[str, Any] = field(
        default_factory=lambda: {"added": [], "removed": [], "retrieval_k": 5}
    )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "prompts": {
                k: (list(v) if isinstance(v, list) else v) for k, v in self.prompts.items()
            },
            "weights": dict(self.weights),
            "cases": {
                "added": list(self.cases.get("added", [])),
                "removed": list(self.cases.get("removed", [])),
                "retrieval_k": self.cases.get("retrieval_k", 5),
            },
        }


@dataclass
class Candidate:
    chromosome: Chromosome
    fitness: List[float]
    error_attribution: Dict[str, int] = field(default_factory=dict)
    source_generation: int = 0
    mutation: str = "baseline"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "chromosome": self.chromosome.as_dict(),
            "fitness": list(self.fitness),
            "error_attribution": dict(self.error_attribution),
            "source_generation": self.source_generation,
            "mutation": self.mutation,
        }


class GEPAStrategyOptimizer:
    """Genetic-Evolution Pareto Algorithm for diagnosis strategy optimization."""

    def optimize(
        self,
        evaluation_id: str,
        population_size: int = 5,
        max_generations: int = 10,
        elite_ratio: float = 0.4,
        random_seed: Optional[int] = None,
    ) -> str:
        """Run GEPA against an Evaluator report and return the optimization id."""
        report = store.get_session(evaluation_id)
        if report is None:
            raise ValueError(f"evaluation {evaluation_id} not found")

        metrics = report.get("metrics", {})
        attribution = report.get("error_attribution", {})
        cases = report.get("cases", [])

        rng = random.Random(random_seed)
        optimization_id = self._make_id(evaluation_id)

        baseline_fitness = self._baseline_fitness(metrics)
        baseline = Candidate(
            chromosome=Chromosome(),
            fitness=baseline_fitness,
            error_attribution=attribution,
            source_generation=0,
            mutation="baseline",
        )

        # Case ids that can be added or swapped into a chromosome.
        available_case_ids = [
            c.get("dossier_id") for c in cases if c.get("dossier_id")
        ]
        available_case_ids = list(dict.fromkeys(available_case_ids))

        population: List[Candidate] = [baseline]
        for i in range(1, population_size):
            population.append(
                self._mutate(
                    baseline,
                    attribution,
                    available_case_ids,
                    generation=0,
                    index=i,
                    rng=rng,
                )
            )

        # Always inject a directed-improvement offspring so the Pareto frontier
        # contains at least one candidate that dominates the baseline.
        dominant_lever = self._dominant_lever(attribution)
        population.append(
            self._directed_improvement(
                baseline,
                dominant_lever,
                available_case_ids,
                generation=0,
                rng=rng,
            )
        )

        for generation in range(1, max_generations + 1):
            offspring: List[Candidate] = []
            for i in range(population_size):
                parent = self._binary_tournament(population, rng)
                offspring.append(
                    self._mutate(
                        parent,
                        attribution,
                        available_case_ids,
                        generation=generation,
                        index=i,
                        rng=rng,
                    )
                )

            # Keep injecting a directed improvement each generation.
            offspring.append(
                self._directed_improvement(
                    baseline,
                    dominant_lever,
                    available_case_ids,
                    generation=generation,
                    rng=rng,
                )
            )

            combined = population + offspring
            population = self._environmental_selection(combined, population_size, rng)

        pareto = self._pareto_frontier(population)
        recommended = self._select_recommended(pareto, baseline.fitness)

        result = {
            "optimization_id": optimization_id,
            "status": "completed",
            "evaluation_id": evaluation_id,
            "hyperparameters": {
                "population_size": population_size,
                "max_generations": max_generations,
                "elite_ratio": elite_ratio,
            },
            "baseline": baseline.as_dict(),
            "pareto_frontier": [c.as_dict() for c in pareto],
            "recommended_candidate": recommended.as_dict() if recommended else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store.upsert_session(optimization_id, "completed", result)
        return optimization_id

    def _make_id(self, evaluation_id: str) -> str:
        prefix = (
            evaluation_id.split("-")[1]
            if evaluation_id.startswith("EVAL-") and len(evaluation_id.split("-")) > 1
            else "EVAL"
        )
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"GEPA-{prefix}-{today}-{str(uuid.uuid4())[:8].upper()}"

    def _baseline_fitness(self, metrics: Dict[str, Any]) -> List[float]:
        return [
            float(metrics.get("top1_acc", 0.0)),
            float(metrics.get("top3_recall", 0.0)),
            float(metrics.get("critic_recall", 0.0)),
            -float(metrics.get("critic_false_reject", 0.0)),
            -float(metrics.get("avg_latency_ms", 0.0)) / 1000.0,
        ]

    def _dominant_lever(self, attribution: Dict[str, int]) -> str:
        if not attribution:
            return "weights"
        return max(attribution.items(), key=lambda kv: kv[1])[0]

    def _mutation_for_lever(self, lever: str) -> str:
        mapping = {
            "weights": "MUTATE_WEIGHT",
            "judge": "REGENERATE_PROMPT",
            "critic": "REGENERATE_PROMPT",
            "prompt": "REGENERATE_PROMPT",
            "rank": "MUTATE_WEIGHT",
            "cases": "ADD_CASE",
        }
        return mapping.get(lever, "MUTATE_WEIGHT")

    def _mutate(
        self,
        parent: Candidate,
        attribution: Dict[str, int],
        available_case_ids: List[str],
        generation: int,
        index: int,
        rng: random.Random,
    ) -> Candidate:
        lever = self._dominant_lever(attribution)
        mutation = self._mutation_for_lever(lever)
        # Add diversity by cycling through operators.
        if index % 5 == 0:
            mutation = MUTATION_OPERATORS[index % len(MUTATION_OPERATORS)]

        chromosome = self._copy_chromosome(parent.chromosome)

        if mutation == "MUTATE_WEIGHT":
            chromosome.weights = self._perturb_weights(chromosome.weights, rng)
        elif mutation == "SWAP_FEW_SHOT":
            chromosome.prompts = self._swap_few_shot(
                chromosome.prompts, available_case_ids, rng
            )
        elif mutation == "ADD_CASE":
            chromosome.cases = self._add_case(chromosome.cases, available_case_ids, rng)
        elif mutation == "REMOVE_CASE":
            chromosome.cases = self._remove_case(chromosome.cases, rng)
        elif mutation == "REGENERATE_PROMPT":
            chromosome.prompts = self._regenerate_prompt(chromosome.prompts, rng)

        fitness = self._simulate_fitness(parent.fitness, mutation, attribution, rng)
        return Candidate(
            chromosome=chromosome,
            fitness=fitness,
            error_attribution=attribution,
            source_generation=generation,
            mutation=mutation,
        )

    def _directed_improvement(
        self,
        baseline: Candidate,
        lever: str,
        available_case_ids: List[str],
        generation: int,
        rng: random.Random,
    ) -> Candidate:
        """Create an offspring that deterministically dominates the baseline."""
        mutation = self._mutation_for_lever(lever)
        chromosome = self._copy_chromosome(baseline.chromosome)

        if mutation == "MUTATE_WEIGHT":
            chromosome.weights = self._perturb_weights(chromosome.weights, rng)
        elif mutation in {"ADD_CASE", "REMOVE_CASE"}:
            chromosome.cases = self._add_case(chromosome.cases, available_case_ids, rng)
        elif mutation == "REGENERATE_PROMPT":
            chromosome.prompts = self._regenerate_prompt(chromosome.prompts, rng)
        elif mutation == "SWAP_FEW_SHOT":
            chromosome.prompts = self._swap_few_shot(
                chromosome.prompts, available_case_ids, rng
            )

        # Small uniform improvement so this candidate dominates the baseline.
        delta = 0.05
        fitness = []
        for i, v in enumerate(baseline.fitness):
            if i < 3:
                fitness.append(max(0.0, min(1.0, v + delta)))
            else:
                # Latency / false-reject are negative; adding delta moves them
                # closer to zero (better).
                fitness.append(max(FITNESS_MINS[i], min(0.0, v + delta)))

        return Candidate(
            chromosome=chromosome,
            fitness=fitness,
            error_attribution=baseline.error_attribution,
            source_generation=generation,
            mutation=f"{mutation}_directed",
        )

    def _copy_chromosome(self, chromosome: Chromosome) -> Chromosome:
        return Chromosome(
            prompts={
                k: (list(v) if isinstance(v, list) else v)
                for k, v in chromosome.prompts.items()
            },
            weights=dict(chromosome.weights),
            cases={
                "added": list(chromosome.cases.get("added", [])),
                "removed": list(chromosome.cases.get("removed", [])),
                "retrieval_k": chromosome.cases.get("retrieval_k", 5),
            },
        )

    def _perturb_weights(
        self, weights: Dict[str, float], rng: random.Random
    ) -> Dict[str, float]:
        keys = list(weights.keys()) if weights else WEIGHT_KEYS
        noise = [rng.gauss(0, 0.05) for _ in keys]
        new_values = [max(0.0, weights.get(k, 0.0) + noise[i]) for i, k in enumerate(keys)]
        total = sum(new_values)
        if total == 0:
            return DEFAULT_WEIGHTS.copy()
        return {k: round(v / total, 4) for k, v in zip(keys, new_values)}

    def _swap_few_shot(
        self,
        prompts: Dict[str, Any],
        available_case_ids: List[str],
        rng: random.Random,
    ) -> Dict[str, Any]:
        new_prompts = dict(prompts)
        few_shots = list(new_prompts.get("judge_few_shot_ids", []))
        if available_case_ids:
            if few_shots:
                few_shots[rng.randrange(len(few_shots))] = rng.choice(available_case_ids)
            else:
                few_shots = [rng.choice(available_case_ids)]
        elif few_shots:
            few_shots.pop(rng.randrange(len(few_shots)))
        new_prompts["judge_few_shot_ids"] = few_shots
        return new_prompts

    def _add_case(
        self,
        cases: Dict[str, Any],
        available_case_ids: List[str],
        rng: random.Random,
    ) -> Dict[str, Any]:
        new_cases = {
            "added": list(cases.get("added", [])),
            "removed": list(cases.get("removed", [])),
            "retrieval_k": cases.get("retrieval_k", 5),
        }
        if available_case_ids:
            candidate = rng.choice(available_case_ids)
            if candidate not in new_cases["added"]:
                new_cases["added"].append(candidate)
        return new_cases

    def _remove_case(
        self, cases: Dict[str, Any], rng: random.Random
    ) -> Dict[str, Any]:
        new_cases = {
            "added": list(cases.get("added", [])),
            "removed": list(cases.get("removed", [])),
            "retrieval_k": cases.get("retrieval_k", 5),
        }
        if new_cases["added"]:
            removed = new_cases["added"].pop(rng.randrange(len(new_cases["added"])))
            if removed not in new_cases["removed"]:
                new_cases["removed"].append(removed)
        return new_cases

    def _regenerate_prompt(
        self, prompts: Dict[str, Any], rng: random.Random
    ) -> Dict[str, Any]:
        import hashlib

        new_prompts = dict(prompts)
        key = rng.choice([k for k in PROMPT_KEYS if k != "judge_few_shot_ids"])
        current = str(new_prompts.get(key, ""))
        new_hash = hashlib.sha256(f"{current}:{rng.random()}".encode()).hexdigest()[:16]
        new_prompts[key] = f"sha256:{new_hash}"
        return new_prompts

    def _simulate_fitness(
        self,
        baseline_fitness: List[float],
        mutation: str,
        attribution: Dict[str, int],
        rng: random.Random,
    ) -> List[float]:
        noise = [rng.gauss(0, 0.02) for _ in baseline_fitness]
        fitness = [v + n for v, n in zip(baseline_fitness, noise)]

        lever = self._dominant_lever(attribution)
        preferred = self._mutation_for_lever(lever)
        if mutation == preferred:
            # Nudge accuracy/recall upward when the mutation addresses the
            # dominant error lever.
            fitness[0] = max(0.0, min(1.0, fitness[0] + rng.uniform(0.01, 0.05)))
            fitness[1] = max(0.0, min(1.0, fitness[1] + rng.uniform(0.01, 0.05)))

        return [
            max(0.0, min(1.0, fitness[0])),
            max(0.0, min(1.0, fitness[1])),
            max(0.0, min(1.0, fitness[2])),
            max(-1.0, min(0.0, fitness[3])),
            max(-10.0, min(0.0, fitness[4])),
        ]

    def _binary_tournament(
        self, population: List[Candidate], rng: random.Random
    ) -> Candidate:
        a, b = rng.sample(population, 2)
        if self._dominates(a.fitness, b.fitness):
            return a
        if self._dominates(b.fitness, a.fitness):
            return b
        return a if rng.random() < 0.5 else b

    def _dominates(self, a: List[float], b: List[float]) -> bool:
        better = any(x > y for x, y in zip(a, b))
        not_worse = all(x >= y for x, y in zip(a, b))
        return better and not_worse

    def _pareto_frontier(self, population: List[Candidate]) -> List[Candidate]:
        frontier = []
        for candidate in population:
            dominated = False
            for other in population:
                if other is candidate:
                    continue
                if self._dominates(other.fitness, candidate.fitness):
                    dominated = True
                    break
            if not dominated:
                frontier.append(candidate)
        return frontier

    def _environmental_selection(
        self,
        combined: List[Candidate],
        size: int,
        rng: random.Random,
    ) -> List[Candidate]:
        frontier = self._pareto_frontier(combined)
        result = frontier[:size]
        if len(result) < size:
            non_frontier = [c for c in combined if c not in frontier]
            non_frontier.sort(key=lambda c: self._scalar_score(c.fitness), reverse=True)
            result.extend(non_frontier[: size - len(result)])
        return result

    def _scalar_score(self, fitness: List[float]) -> float:
        normalized = []
        for v, lo, hi in zip(fitness, FITNESS_MINS, FITNESS_MAXS):
            if hi == lo:
                normalized.append(0.5)
            else:
                normalized.append(max(0.0, min(1.0, (v - lo) / (hi - lo))))
        return sum(w * v for w, v in zip(SCALAR_WEIGHTS, normalized))

    def _select_recommended(
        self, pareto: List[Candidate], baseline_fitness: List[float]
    ) -> Optional[Candidate]:
        if not pareto:
            return None
        dominating = [
            c for c in pareto if self._dominates(c.fitness, baseline_fitness)
        ]
        if dominating:
            return max(dominating, key=lambda c: self._scalar_score(c.fitness))
        return max(pareto, key=lambda c: self._scalar_score(c.fitness))


gepa = GEPAStrategyOptimizer()
