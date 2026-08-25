"""Interface en ligne de commande.

    suukalia init      --bankroll 200        initialise le grand livre
    suukalia analyse   [--live] [--record]   cherche les value bets du jour
    suukalia bets                            paris ouverts
    suukalia settle    <id> --won            solde un pari
    suukalia perf                            bilan de performance
    suukalia backtest  [--train 200]         qualite predictive hors echantillon
    suukalia simulate  [--edge 0.03]         risque de ruine et croissance
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .backtest import simulate_bankroll, walk_forward
from .config import Settings
from .engine import BettingEngine
from .models import Match
from .notify import send_telegram
from .providers.base import ProviderError
from .providers.csv_results import CsvResultsProvider
from .providers.local_odds import LocalOddsProvider
from .providers.theoddsapi import TheOddsApiProvider
from .report import render_analysis, render_performance, render_telegram
from .staking.bankroll import BankrollManager
from .storage.db import Ledger

DEFAULT_HISTORY = "data/ligue1_history.csv"
DEFAULT_ODDS = "data/sample_odds.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="suukalia",
        description="Analyse quantitative de paris sportifs : value bets, Kelly, bankroll.",
    )
    parser.add_argument("--config", help="fichier de configuration JSON")
    parser.add_argument("--db", help="chemin du grand livre SQLite")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialise le grand livre")
    p_init.add_argument("--bankroll", type=float, default=200.0)

    p_analyse = sub.add_parser("analyse", help="cherche les value bets")
    p_analyse.add_argument("--live", action="store_true", help="utiliser l'API de cotes reelle")
    p_analyse.add_argument("--odds", default=DEFAULT_ODDS, help="fichier de cotes hors-ligne")
    p_analyse.add_argument("--history", default=DEFAULT_HISTORY, help="CSV d'historique")
    p_analyse.add_argument("--record", action="store_true", help="enregistre les paris")
    p_analyse.add_argument("--notify", action="store_true", help="envoie sur Telegram")
    p_analyse.add_argument("-v", "--verbose", action="store_true", help="detail des rejets")

    sub.add_parser("bets", help="liste les paris ouverts")

    p_settle = sub.add_parser("settle", help="solde un pari")
    p_settle.add_argument("bet_id", type=int)
    group = p_settle.add_mutually_exclusive_group(required=True)
    group.add_argument("--won", action="store_true", help="pari gagne")
    group.add_argument("--lost", action="store_true", help="pari perdu")
    group.add_argument("--void", action="store_true", help="match annule, mise remboursee")
    p_settle.add_argument("--closing", type=float, help="cote de cloture (pour le CLV)")

    sub.add_parser("perf", help="bilan de performance")

    p_back = sub.add_parser("backtest", help="qualite predictive hors echantillon")
    p_back.add_argument("--history", default=DEFAULT_HISTORY)
    p_back.add_argument("--train", type=int, default=200, help="taille de la fenetre initiale")
    p_back.add_argument("--step", type=int, default=20, help="matchs predits par re-entrainement")

    p_sim = sub.add_parser("simulate", help="simulation de bankroll (risque de ruine)")
    p_sim.add_argument("--bankroll", type=float, default=200.0)
    p_sim.add_argument("--bets", type=int, default=300)
    p_sim.add_argument("--edge", type=float, default=0.03)
    p_sim.add_argument("--odds", type=float, default=2.10)
    p_sim.add_argument("--trials", type=int, default=5000)
    p_sim.add_argument(
        "--flat",
        type=float,
        metavar="FRACTION",
        help="mise a plat (ex: 0.02) au lieu de Kelly ; permet de simuler un edge negatif",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.load(args.config)
    if args.db:
        settings.db_path = args.db

    try:
        return _dispatch(args, settings)
    except ProviderError as exc:
        print(f"Erreur fournisseur : {exc}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace, settings: Settings) -> int:
    ledger = Ledger(settings.db_path)

    if args.command == "init":
        ledger.set_starting_bankroll(args.bankroll)
        print(f"Grand livre initialise dans {settings.db_path}")
        print(f"Bankroll de depart : {args.bankroll:.2f} EUR")
        print("\nProchaine etape : `suukalia analyse` (mode demo hors-ligne)")
        print("ou renseigner SUUKALIA_ODDS_API_KEY puis `suukalia analyse --live`.")
        return 0

    if args.command == "analyse":
        return _analyse(args, settings, ledger)

    if args.command == "bets":
        rows = ledger.open_bets()
        if not rows:
            print("Aucun pari ouvert.")
            return 0
        print(f"{'ID':>4} {'MATCH':30s} {'PARI':6s} {'COTE':>6s} {'MISE':>7s} {'BOOK':<10s}")
        for row in rows:
            print(
                f"{row['id']:>4} {row['label'][:30]:30s} {row['selection']:6s} "
                f"{row['odds']:6.2f} {row['stake']:6.2f}e {row['bookmaker']:<10s}"
            )
        return 0

    if args.command == "settle":
        ok = ledger.settle(
            args.bet_id, won=args.won, closing_odds=args.closing, void=args.void
        )
        if not ok:
            print(f"Pari {args.bet_id} introuvable ou deja solde.", file=sys.stderr)
            return 1
        state = ledger.state(settings.starting_bankroll)
        outcome = "annule" if args.void else ("gagne" if args.won else "perdu")
        print(f"Pari {args.bet_id} solde ({outcome}). Bankroll : {state.current:.2f} EUR")
        if args.closing is None:
            print("Astuce : ajouter --closing <cote> permet de suivre le CLV.")
        return 0

    if args.command == "perf":
        state = ledger.state(settings.starting_bankroll)
        print(render_performance(ledger.settled_bets(), state))
        return 0

    if args.command == "backtest":
        history = CsvResultsProvider(args.history).fetch_results()
        print(f"Historique : {len(history)} matchs. Backtest walk-forward en cours...\n")
        print(walk_forward(history, args.train, args.step).render())
        return 0

    if args.command == "simulate":
        print(
            simulate_bankroll(
                starting=args.bankroll,
                bets=args.bets,
                edge=args.edge,
                odds=args.odds,
                kelly=settings.kelly,
                trials=args.trials,
                flat_fraction=args.flat,
            ).render()
        )
        return 0

    return 1


def _analyse(args: argparse.Namespace, settings: Settings, ledger: Ledger) -> int:
    matches: list[Match]
    if args.live:
        provider = TheOddsApiProvider(settings.odds_api_key, settings.regions)
        matches = []
        for league in settings.leagues:
            matches.extend(provider.fetch_matches(league))
    else:
        matches = LocalOddsProvider(args.odds).fetch_matches()

    history = []
    if Path(args.history).exists():
        history = CsvResultsProvider(args.history).fetch_results()

    state = ledger.state(settings.starting_bankroll)
    manager = BankrollManager(state, settings.limits)
    engine = BettingEngine.train(settings, manager, history)
    report = engine.analyse(matches)

    print(render_analysis(report, state, args.verbose))

    if args.record and report.tickets:
        recorded = sum(1 for ticket in report.tickets if ledger.record(ticket))
        skipped = len(report.tickets) - recorded
        suffixe = f", {skipped} doublon(s) ignore(s)." if skipped else "."
        print(f"\n{recorded} pari(s) enregistre(s){suffixe}")
    elif report.tickets:
        print("\n(simulation : relancer avec --record pour enregistrer les paris)")

    if args.notify:
        sent = send_telegram(
            settings.telegram_token, settings.telegram_chat_id, render_telegram(report, state)
        )
        print("Notification Telegram envoyee." if sent else "Notification Telegram non envoyee.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
