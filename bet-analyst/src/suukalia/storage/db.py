"""Grand livre des paris en SQLite (stdlib, zero dependance, zero serveur).

Le fichier est la source de verite : la bankroll est toujours reconstruite
depuis les lignes du grand livre, jamais stockee comme un nombre modifiable.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from ..models import BetTicket
from ..staking.bankroll import BankrollState

SCHEMA = """
CREATE TABLE IF NOT EXISTS bets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id       TEXT NOT NULL,
    label          TEXT NOT NULL,
    league         TEXT NOT NULL,
    kickoff        TEXT NOT NULL,
    market         TEXT NOT NULL,
    selection      TEXT NOT NULL,
    bookmaker      TEXT NOT NULL,
    odds           REAL NOT NULL,
    fair_odds      REAL NOT NULL,
    probability    REAL NOT NULL,
    edge           REAL NOT NULL,
    stake          REAL NOT NULL,
    placed_at      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'OPEN',
    payout         REAL,
    closing_odds   REAL,
    settled_at     TEXT,
    UNIQUE (match_id, market, selection, bookmaker)
);
CREATE INDEX IF NOT EXISTS idx_bets_status ON bets (status);
CREATE INDEX IF NOT EXISTS idx_bets_placed ON bets (placed_at);

CREATE TABLE IF NOT EXISTS bankroll_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Ledger:
    """Acces au grand livre. Toutes les ecritures sont transactionnelles."""

    def __init__(self, path: str | Path = "data/bankroll.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------- bankroll
    def set_starting_bankroll(self, amount: float) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bankroll_config (key, value) VALUES ('starting', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(amount),),
            )

    def starting_bankroll(self, default: float = 200.0) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM bankroll_config WHERE key = 'starting'"
            ).fetchone()
        return float(row["value"]) if row else default

    def state(self, default_starting: float = 200.0) -> BankrollState:
        """Reconstruit l'etat de la bankroll a partir de tous les paris.

        Le pic est calcule en rejouant les paris soldes dans l'ordre : c'est ce
        qui donne un drawdown honnete, et non la difference avec le maximum
        instantane.
        """
        starting = self.starting_bankroll(default_starting)
        today = datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            settled = conn.execute(
                "SELECT stake, payout FROM bets WHERE status = 'SETTLED' "
                "ORDER BY COALESCE(settled_at, placed_at), id"
            ).fetchall()
            open_rows = conn.execute(
                "SELECT COALESCE(SUM(stake), 0) AS s, COUNT(*) AS n "
                "FROM bets WHERE status = 'OPEN'"
            ).fetchone()
            today_row = conn.execute(
                "SELECT COUNT(*) AS n FROM bets WHERE substr(placed_at, 1, 10) = ?",
                (today,),
            ).fetchone()

        current = peak = starting
        for row in settled:
            current += (row["payout"] or 0.0) - row["stake"]
            peak = max(peak, current)
        return BankrollState(
            starting=starting,
            current=current,
            peak=peak,
            open_exposure=float(open_rows["s"]),
            bets_today=int(today_row["n"]),
            settled_bets=len(settled),
        )

    # ----------------------------------------------------------------- paris
    def record(self, ticket: BetTicket) -> bool:
        """Enregistre un ticket. Retourne False si le pari existe deja.

        La contrainte d'unicite (match, marche, issue, book) est volontaire :
        relancer le moteur deux fois dans la journee ne doit jamais doubler une
        position.
        """
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO bets (match_id, label, league, kickoff, market, selection,"
                    " bookmaker, odds, fair_odds, probability, edge, stake, placed_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ticket.match_id, ticket.label, ticket.league,
                        ticket.kickoff.isoformat(), ticket.market.value, ticket.selection,
                        ticket.bookmaker, ticket.odds, ticket.fair_odds, ticket.probability,
                        ticket.edge, ticket.stake,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def settle(
        self,
        bet_id: int,
        won: bool,
        closing_odds: float | None = None,
        void: bool = False,
    ) -> bool:
        """Solde un pari. `void` rembourse la mise (match annule)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT stake, odds FROM bets WHERE id = ? AND status = 'OPEN'", (bet_id,)
            ).fetchone()
            if row is None:
                return False
            payout = row["stake"] if void else (row["stake"] * row["odds"] if won else 0.0)
            conn.execute(
                "UPDATE bets SET status='SETTLED', payout=?, closing_odds=?, settled_at=?"
                " WHERE id = ?",
                (payout, closing_odds, datetime.now(timezone.utc).isoformat(), bet_id),
            )
        return True

    def open_bets(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM bets WHERE status = 'OPEN' ORDER BY kickoff"
            ).fetchall()

    def settled_bets(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM bets WHERE status = 'SETTLED' "
                "ORDER BY COALESCE(settled_at, placed_at), id"
            ).fetchall()

    def bets_on(self, day: date) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM bets WHERE substr(placed_at, 1, 10) = ?", (day.isoformat(),)
            ).fetchall()
