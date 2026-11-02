from __future__ import annotations

from collections import defaultdict

from rdflib import Graph, RDF, Variable
from rdflib.collection import Collection

from .config import ONTOLOGY_DIR, SWRL


def load_rule_graph() -> Graph:
    graph = Graph()
    graph.parse(ONTOLOGY_DIR / "cinetrope-swrl.n3", format="n3")
    return graph


def _atom_kind(graph: Graph, atom) -> str | None:
    if (atom, RDF.type, SWRL.ClassAtom) in graph:
        return "class"
    if (atom, RDF.type, SWRL.IndividualPropertyAtom) in graph:
        return "property"
    return None


def _parse_atom(graph: Graph, atom) -> dict:
    kind = _atom_kind(graph, atom)
    if kind == "class":
        return {
            "kind": "class",
            "predicate": graph.value(atom, SWRL.classPredicate),
            "arg1": graph.value(atom, SWRL.argument1),
        }
    if kind == "property":
        return {
            "kind": "property",
            "predicate": graph.value(atom, SWRL.propertyPredicate),
            "arg1": graph.value(atom, SWRL.argument1),
            "arg2": graph.value(atom, SWRL.argument2),
        }
    return {"kind": "unsupported"}


def _unify(binding: dict, term, value) -> dict | None:
    if isinstance(term, Variable):
        if term in binding:
            return binding if binding[term] == value else None
        candidate = dict(binding)
        candidate[term] = value
        return candidate
    return binding if term == value else None


def _match_atom(graph: Graph, atom: dict, binding: dict) -> list[dict]:
    if atom["kind"] == "class":
        predicate = atom["predicate"]
        arg1 = atom["arg1"]
        if arg1 is None:
            return []
        if isinstance(arg1, Variable) and arg1 in binding:
            subject = binding[arg1]
            return [binding] if (subject, RDF.type, predicate) in graph else []
        results = []
        for subject in graph.subjects(RDF.type, predicate):
            unified = _unify(binding, arg1, subject)
            if unified is not None:
                results.append(unified)
        return results

    if atom["kind"] == "property":
        predicate = atom["predicate"]
        arg1, arg2 = atom["arg1"], atom["arg2"]
        results = []
        bound1 = binding.get(arg1) if isinstance(arg1, Variable) else arg1
        bound2 = binding.get(arg2) if isinstance(arg2, Variable) else arg2

        if bound1 is not None and bound2 is not None:
            if (bound1, predicate, bound2) in graph:
                first = _unify(binding, arg1, bound1)
                if first is None:
                    return []
                second = _unify(first, arg2, bound2)
                return [second] if second is not None else []

        if bound1 is not None and isinstance(arg2, Variable):
            pairs = ((bound1, obj) for obj in graph.objects(bound1, predicate))
        elif bound2 is not None and isinstance(arg1, Variable):
            pairs = ((subj, bound2) for subj in graph.subjects(predicate, bound2))
        else:
            pairs = ((subj, obj) for subj, obj in graph.subject_objects(predicate))

        for subject, obj in pairs:
            first = _unify(binding, arg1, subject)
            if first is None:
                continue
            second = _unify(first, arg2, obj)
            if second is not None:
                results.append(second)
        return results

    return []


def _instantiate(term, binding: dict):
    if isinstance(term, Variable):
        return binding.get(term)
    return term


def apply_swrl(graph: Graph, rules: Graph, max_iterations: int = 20) -> dict[str, int]:
    """Applica le regole SWRL con forward chaining fino al punto fisso."""
    stats: dict[str, int] = defaultdict(int)
    rules_list = list(rules.subjects(RDF.type, SWRL.Imp))

    for iteration in range(max_iterations):
        added_in_round = 0
        for rule in rules_list:
            body_node = rules.value(rule, SWRL.body)
            head_node = rules.value(rule, SWRL.head)
            if body_node is None or head_node is None:
                continue
            body = [_parse_atom(rules, atom) for atom in Collection(rules, body_node)]
            head = [_parse_atom(rules, atom) for atom in Collection(rules, head_node)]
            if any(atom["kind"] == "unsupported" for atom in body + head):
                continue

            bindings: list[dict] = [{}]
            for atom in body:
                next_bindings: list[dict] = []
                for binding in bindings:
                    next_bindings.extend(_match_atom(graph, atom, binding))
                bindings = next_bindings
                if not bindings:
                    break

            for binding in bindings:
                for atom in head:
                    if atom["kind"] == "class":
                        subject = _instantiate(atom["arg1"], binding)
                        predicate = RDF.type
                        obj = atom["predicate"]
                    else:
                        subject = _instantiate(atom["arg1"], binding)
                        predicate = atom["predicate"]
                        obj = _instantiate(atom["arg2"], binding)
                    if subject is None or predicate is None or obj is None:
                        continue
                    triple = (subject, predicate, obj)
                    if triple not in graph:
                        graph.add(triple)
                        stats[str(rule).split("#")[-1]] += 1
                        added_in_round += 1
        if added_in_round == 0:
            break

    return dict(stats)
