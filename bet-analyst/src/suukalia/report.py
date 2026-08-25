"""Rendu texte des resultats (console, log, message Telegram)."""

from __future__ import annotations

import sqlite3
import statistics
from collections.abc import Sequence

from .analysis.value import closing_line_value
from .engine import AnalysisReport
from .staking.bankroll import BankrollState

LINE = "-" * 78


def render_analysis(report: AnalysisReport, state: BankrollState, verbose: bool = False) -> str:
    lines = [
        LINE,
        f"BANKROLL  {state.current:8.2f} EUR   "
        f"(depart {state.starting:.2f} | P&L {state.profit:+.2f} | "
        f"ROI {state.roi:+.1%} | drawdown {state.drawdown:.1%})",
        LINE,
    ]
    if report.blocked_reason:
        lines += ["", f"!! TRADING SUSPENDU : {report.blocked_reason}", ""]
        return "\n".join(lines)

    if not report.tickets:
        lines.append("")
        lines.append("Aucun pari retenu. C'est le resultat le plus frequent, et c'est normal :")
        lines.append("un marche efficient ne laisse pas d'edge tous les jours.")
    else:
        lines.append("")
        lines.append(
            f"{'MATCH':30s} {'PARI':6s} {'COTE':>6s} {'JUSTE':>7s} "
            f"{'EDGE':>7s} {'MISE':>7s} {'BOOK':<10s}"
        )
        lines.append(LINE)
        for t in report.tickets:
            lines.append(
                f"{t.label[:30]:30s} {t.selection:6s} {t.odds:6.2f} {t.fair_odds:7.2f} "
                f"{t.edge:+6.2%} {t.stake:6.2f}e {t.bookmaker:<10s}"
            )
        lines.append(LINE)
        expected = sum(t.expected_value for t in report.tickets)
        lines.append(
            f"{'TOTAL':30s} {'':6s} {'':6s} {'':7s} {'':7s} "
            f"{report.total_stake:6.2f}e   EV {expected:+.2f} EUR"
        )
        lines.append("")
        lines.append(
            f"Exposition : {report.total_stake / state.current:.1%} de la bankroll. "
            "L'EV est une esperance, pas une prevision de gain."
        )

    lines.append("")
    lines.append(report.summary())

    if verbose and report.rejections:
        lines.append("")
        lines.append("Matchs ecartes :")
        for rejection in report.rejections:
            lines.append(f"  - {rejection.label[:40]:40s} {rejection.reason}")
    return "\n".join(lines)


def render_telegram(report: AnalysisReport, state: BankrollState) -> str:
    """Version compacte pour notification mobile."""
    if report.blocked_reason:
        return f"[SUUKALIA] Trading suspendu : {report.blocked_reason}"
    if not report.tickets:
        return (
            f"[SUUKALIA] {report.matches_analysed} matchs analyses, aucun edge. "
            f"Bankroll {state.current:.2f} EUR."
        )
    body = "\n".join(
        f"- {t.label} : {t.selection} @ {t.odds:.2f} ({t.bookmaker}) "
        f"| edge {t.edge:+.1%} | {t.stake:.2f} EUR"
        for t in report.tickets
    )
    return (
        f"[SUUKALIA] {len(report.tickets)} pari(s) - {report.total_stake:.2f} EUR engages\n"
        f"{body}\nBankroll : {state.current:.2f} EUR ({state.roi:+.1%})"
    )


def render_performance(settled: Sequence[sqlite3.Row], state: BankrollState) -> str:
    """Bilan sur les paris soldes, avec les metriques qui comptent vraiment."""
    if not settled:
        return "Aucun pari solde pour l'instant."

    stakes = [row["stake"] for row in settled]
    profits = [(row["payout"] or 0.0) - row["stake"] for row in settled]
    wins = sum(1 for p in profits if p > 0)
    turnover = sum(stakes)
    profit = sum(profits)

    clvs = [
        closing_line_value(row["odds"], row["closing_odds"])
        for row in settled
        if row["closing_odds"]
    ]

    lines = [
        LINE,
        "BILAN DE PERFORMANCE",
        LINE,
        f"Paris soldes        : {len(settled)}",
        f"Taux de reussite    : {wins / len(settled):.1%}",
        f"Volume mise         : {turnover:.2f} EUR",
        f"Profit net          : {profit:+.2f} EUR",
        f"Yield (profit/mise) : {profit / turnover:+.2%}" if turnover else "Yield : n/a",
        f"Bankroll            : {state.current:.2f} EUR ({state.roi:+.1%})",
        f"Drawdown max        : {state.drawdown:.1%}",
    ]

    if clvs:
        mean_clv = statistics.fmean(clvs)
        beaten = sum(1 for c in clvs if c > 0) / len(clvs)
        lines += [
            "",
            f"CLV moyen           : {mean_clv:+.2%}   (sur {len(clvs)} paris)",
            f"Cloture battue      : {beaten:.1%} des paris",
            "",
            _clv_verdict(mean_clv, len(settled)),
        ]
    else:
        lines += [
            "",
            "CLV non renseigne. Saisir la cote de cloture avec `suukalia settle --closing`",
            "est le seul moyen de savoir si la selection a de la valeur avant",
            "d'avoir accumule un millier de paris.",
        ]

    if len(settled) < 200:
        lines += [
            "",
            f"Attention : {len(settled)} paris, c'est trop peu pour conclure quoi que ce",
            "soit sur le P&L. La variance domine largement l'edge en dessous de",
            "~500 paris.",
        ]
    return "\n".join(lines)


def _clv_verdict(mean_clv: float, sample: int) -> str:
    """Verdict sur le CLV, prudent tant que l'echantillon est petit.

    Le CLV converge bien plus vite que le P&L, mais pas instantanement : sous
    ~50 paris, un CLV moyen positif reste compatible avec du pur hasard. On
    refuse de valider une methode sur trois paris chanceux.
    """
    if sample < 50:
        return (
            f"CLV moyen sur {sample} pari(s) seulement : pas encore interpretable. "
            "Il en faut au moins une cinquantaine pour que le signe du CLV "
            "signifie quelque chose."
        )
    if mean_clv > 0.01:
        return (
            "CLV positif : la selection bat regulierement la cote de cloture. "
            "C'est le signal le plus fiable que la methode fonctionne."
        )
    if mean_clv > -0.005:
        return "CLV proche de zero : la selection suit le marche sans le devancer."
    return (
        "CLV negatif : les paris sont pris a des cotes que le marche corrige "
        "ensuite a la baisse. Meme avec un P&L positif, c'est de la chance et "
        "elle ne durera pas."
    )
