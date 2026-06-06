"""Portfolio parsing and rule-based analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from typing import Any, Dict, List, Union

import pandas as pd

REQUIRED_COLUMNS = {"ticker", "shares", "current_price"}


@dataclass
class PortfolioAnalysis:
    holdings: pd.DataFrame
    total_value: float
    allocation_by_ticker: Dict[str, float]
    allocation_by_class: Dict[str, float]
    flags: List[str] = field(default_factory=list)
    summary: str = ""


def load_portfolio(source: Union[str, bytes]) -> pd.DataFrame:
    if isinstance(source, bytes):
        source = source.decode("utf-8")
    df = pd.read_csv(StringIO(source))
    df.columns = [c.strip().lower() for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0)
    df["current_price"] = pd.to_numeric(df["current_price"], errors="coerce").fillna(0)

    if "cost_basis" not in df.columns:
        df["cost_basis"] = df["current_price"]
    else:
        df["cost_basis"] = pd.to_numeric(df["cost_basis"], errors="coerce").fillna(
            df["current_price"]
        )

    if "asset_class" not in df.columns:
        df["asset_class"] = "unknown"
    else:
        df["asset_class"] = df["asset_class"].astype(str).str.strip().str.lower()

    df["market_value"] = df["shares"] * df["current_price"]
    return df


def analyze_portfolio(df: pd.DataFrame, cash_balance: float = 0.0) -> PortfolioAnalysis:
    holdings = df.copy()
    total_value = float(holdings["market_value"].sum()) + cash_balance

    if total_value <= 0:
        raise ValueError("Portfolio total value must be greater than zero.")

    allocation_by_ticker = {
        row.ticker: round(row.market_value / total_value * 100, 2)
        for row in holdings.itertuples()
        if row.market_value > 0
    }

    if cash_balance > 0:
        allocation_by_ticker["CASH"] = round(cash_balance / total_value * 100, 2)

    class_values = holdings.groupby("asset_class", dropna=False)["market_value"].sum()
    class_dict = {str(k): float(v) for k, v in class_values.items()}
    if cash_balance > 0:
        class_dict["cash"] = class_dict.get("cash", 0.0) + cash_balance

    allocation_by_class = {
        k: round(v / total_value * 100, 2) for k, v in class_dict.items() if v > 0
    }

    flags: List[str] = []
    sorted_alloc = sorted(allocation_by_ticker.items(), key=lambda x: x[1], reverse=True)

    if sorted_alloc and sorted_alloc[0][1] >= 40:
        flags.append(
            f"High concentration: {sorted_alloc[0][0]} is {sorted_alloc[0][1]:.1f}% of portfolio."
        )

    top_two = sum(v for _, v in sorted_alloc[:2])
    if top_two >= 60:
        flags.append(f"Top 2 holdings represent {top_two:.1f}% of portfolio.")

    stock_pct = allocation_by_class.get("stock", 0)
    bond_pct = allocation_by_class.get("bond", 0)
    cash_pct = allocation_by_class.get("cash", allocation_by_ticker.get("CASH", 0))

    if stock_pct >= 80:
        flags.append(f"Equity-heavy portfolio: {stock_pct:.1f}% in stocks.")
    if bond_pct + cash_pct < 10 and stock_pct >= 70:
        flags.append("Limited defensive allocation (bonds/cash under 10%).")

    unrealized = holdings.copy()
    unrealized["gain_loss"] = (
        unrealized["current_price"] - unrealized["cost_basis"]
    ) * unrealized["shares"]
    big_winners = unrealized[unrealized["gain_loss"] > 0].sort_values(
        "gain_loss", ascending=False
    )
    if not big_winners.empty and big_winners.iloc[0]["gain_loss"] / total_value > 0.15:
        top = big_winners.iloc[0]
        flags.append(
            f"Large unrealized gain in {top['ticker']} (${top['gain_loss']:,.0f}) "
            "— consider tax impact before selling."
        )

    summary = (
        f"Portfolio value ${total_value:,.0f} across {len(allocation_by_ticker)} positions. "
        f"Largest holding: {sorted_alloc[0][0]} ({sorted_alloc[0][1]:.1f}%)."
    )

    return PortfolioAnalysis(
        holdings=holdings,
        total_value=total_value,
        allocation_by_ticker=allocation_by_ticker,
        allocation_by_class=allocation_by_class,
        flags=flags,
        summary=summary,
    )


def project_allocation_after_trades(
    holdings: List[Dict[str, Any]],
    cash_balance: float,
    trades: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Estimate asset-class allocation after proposed trades (for plan comparison)."""
    positions: Dict[str, Dict[str, Any]] = {}
    for h in holdings:
        ticker = str(h.get("ticker", "")).upper()
        if not ticker or ticker == "CASH":
            continue
        positions[ticker] = {
            "shares": float(h.get("shares", 0)),
            "price": float(h.get("current_price", 0)),
            "asset_class": str(h.get("asset_class", "unknown")).lower(),
        }

    cash = float(cash_balance)

    for trade in trades:
        action = str(trade.get("action", "hold")).lower()
        ticker = str(trade.get("ticker", "")).upper()
        shares = float(trade.get("shares", 0))
        if action == "hold" or not ticker or shares <= 0:
            continue

        if ticker in positions:
            price = positions[ticker]["price"]
            asset_class = positions[ticker]["asset_class"]
        else:
            # New position — infer class from ticker hints used in the demo.
            price = float(trade.get("current_price", 0))
            if price <= 0 and ticker in {"BND", "AGG", "TLT"}:
                price = 72.0
            asset_class = str(trade.get("asset_class", "unknown")).lower()
            if asset_class == "unknown":
                if ticker in {"BND", "AGG", "TLT"}:
                    asset_class = "bond"
                elif ticker in {"VOO", "SPY", "QQQ", "VTI"}:
                    asset_class = "etf"
                else:
                    asset_class = "stock"
            positions[ticker] = {"shares": 0.0, "price": price, "asset_class": asset_class}

        if action == "sell":
            sold = min(shares, positions[ticker]["shares"])
            positions[ticker]["shares"] -= sold
            cash += sold * positions[ticker]["price"]
        elif action == "buy":
            cost = shares * positions[ticker]["price"]
            positions[ticker]["shares"] += shares
            cash = max(0.0, cash - cost)

    class_values: Dict[str, float] = {}
    for pos in positions.values():
        if pos["shares"] <= 0 or pos["price"] <= 0:
            continue
        value = pos["shares"] * pos["price"]
        cls = pos["asset_class"]
        class_values[cls] = class_values.get(cls, 0.0) + value

    if cash > 0:
        class_values["cash"] = class_values.get("cash", 0.0) + cash

    total = sum(class_values.values())
    if total <= 0:
        return {}

    return {k: round(v / total * 100, 2) for k, v in class_values.items() if v > 0}


def analysis_to_context(
    analysis: PortfolioAnalysis, cash_balance: float = 0.0
) -> Dict[str, Any]:
    holdings = analysis.holdings.copy()
    holdings["weight_pct"] = (
        holdings["ticker"].map(analysis.allocation_by_ticker).fillna(0)
    )

    return {
        "total_value": analysis.total_value,
        "cash_balance": cash_balance,
        "summary": analysis.summary,
        "flags": analysis.flags,
        "allocation_by_ticker": analysis.allocation_by_ticker,
        "allocation_by_class": analysis.allocation_by_class,
        "holdings": holdings[
            [
                "ticker",
                "shares",
                "cost_basis",
                "current_price",
                "market_value",
                "weight_pct",
                "asset_class",
            ]
        ].to_dict(orient="records"),
    }
