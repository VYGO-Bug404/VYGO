"""Punto de entrada multiplataforma del agente de RL VYGO.

El equipo trabaja en Windows 10, donde `make` no está disponible (ai/CLAUDE.md §10). Este
módulo es la referencia; `Makefile` es sólo una envoltura delgada de estos mismos
subcomandos, para quien sí tenga `make`.

Subcomandos: test, bench, baselines, train [--seed], eval, report.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_AI_ROOT = Path(__file__).resolve().parent
_TESTS_DIR = _AI_ROOT / "tests"


def _run(args: list[str]) -> int:
    return subprocess.run(args, cwd=_AI_ROOT).returncode


def cmd_test(_args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "pytest", str(_TESTS_DIR), "-q"])


def cmd_bench(_args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "vygo.env", "--bench"])


def cmd_baselines(_args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "vygo.baselines"])


def cmd_train(args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "vygo.train_ppo", "--seed", str(args.seed)])


def cmd_eval(_args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "vygo.evaluate"])


def cmd_report(_args: argparse.Namespace) -> int:
    return _run([sys.executable, "-m", "vygo.report"])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run.py", description=__doc__)
    subparsers = parser.add_subparsers(dest="comando", required=True)

    subparsers.add_parser("test", help="pytest tests/ -q").set_defaults(func=cmd_test)
    subparsers.add_parser("bench", help="mide steps/s del entorno").set_defaults(func=cmd_bench)
    subparsers.add_parser(
        "baselines", help="corre B0..B2 sobre los 50 escenarios congelados",
    ).set_defaults(func=cmd_baselines)

    train = subparsers.add_parser("train", help="entrenamiento")
    train.add_argument("--seed", type=int, default=0)
    train.set_defaults(func=cmd_train)

    subparsers.add_parser("eval", help="evaluación pareada final").set_defaults(func=cmd_eval)
    subparsers.add_parser("report", help="regenera reports/").set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
