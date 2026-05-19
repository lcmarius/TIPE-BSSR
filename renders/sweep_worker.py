"""Worker pour le sweep parallèle (Modal + multiprocessing local).

Définit `run_one(args)` qui exécute les 10 configs sur une instance synthétique
et renvoie `(n, {config_name: ratio | None})`. Les closures (paramètres
`max_iterations`) sont construites DANS le worker pour éviter le pickling
cross-process.
"""

from renders.render_sweep import (
    SyntheticMap,
    _run_all_configs_on_instance,
    generate_instance,
)
from src.solver.algorithm.builder.method1 import method1
from src.solver.algorithm.builder.method2 import method2
from src.solver.algorithm.incrementer.ils import ils
from src.solver.algorithm.incrementer.opt2 import opt2
from src.solver.algorithm.incrementer.or_opt import or_opt


def _build_configs(ils_max_iter: int):
    def imp_opt2 (g, c): opt2  (g, c, max_iterations=500)
    def imp_oropt(g, c): or_opt(g, c, max_iterations=500)
    def imp_ils  (g, c): ils   (g, c, max_iterations=ils_max_iter)
    return [
        ("method1 seul",             method1, []),
        ("method1 + OPT_2",          method1, [imp_opt2]),
        ("method1 + OR_OPT",         method1, [imp_oropt]),
        ("method1 + OPT_2 + OR_OPT", method1, [imp_opt2, imp_oropt]),
        ("method1 + ILS",            method1, [imp_ils]),
        ("method2 seul",             method2, []),
        ("method2 + OPT_2",          method2, [imp_opt2]),
        ("method2 + OR_OPT",         method2, [imp_oropt]),
        ("method2 + OPT_2 + OR_OPT", method2, [imp_opt2, imp_oropt]),
        ("method2 + ILS",            method2, [imp_ils]),
    ]


def run_one(args):
    """args = (n, capacity, truck, seed, ils_max_iter). Renvoie (n, {name: ratio|None})."""
    n, capacity, truck, seed, ils_max_iter = args
    configs = _build_configs(ils_max_iter)
    targeted, depot, depot_targeted = generate_instance(n, capacity, seed)
    ratios = _run_all_configs_on_instance(targeted, depot, depot_targeted, truck, configs)
    return n, ratios
