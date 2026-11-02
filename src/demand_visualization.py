"""Plot verified temporal summaries without recalculating session aggregations."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd
import seaborn as sns

try:
    from .data_preparation import file_hash
    from .demand_analysis import parse_boolean_flags, WEEKDAYS
except ImportError:
    from data_preparation import file_hash
    from demand_analysis import parse_boolean_flags, WEEKDAYS

TABLE_NAMES = ["hourly_demand", "daily_demand", "weekday_demand", "weekday_weekend_demand",
               "day_hour_demand", "monthly_demand", "monthly_energy_sensitivity"]
BLUE, ORANGE, GREEN = "#0072B2", "#D55E00", "#009E73"  # Okabe–Ito colors
ENERGY_NOTE = "Recorded energy associated with session-start periods; not measured hourly grid load."


def load_analysis(input_dir):
    """Read verified exports and check counts/schema without duplicating aggregation."""
    input_dir = Path(input_dir)
    summary = json.loads((input_dir / "analysis_summary.json").read_text(encoding="utf-8"))
    if not summary.get("reconciliation", {}).get("all_passed"):
        raise ValueError("Phase 2 reconciliation must pass before plotting.")
    tables = {}
    for name in TABLE_NAMES:
        table = pd.read_csv(input_dir / (name + ".csv"))
        required = ["session_count", "calendar_days", "valid_energy_session_count", "total_recorded_energy_kwh"]
        if name != "monthly_energy_sensitivity":
            required += ["avg_sessions_per_day", "avg_recorded_energy_per_day_kwh"]
        else:
            required += ["retained_valid_energy_session_count", "retained_valid_energy_fraction",
                         "retained_energy_observed_dates", "retained_avg_recorded_energy_per_calendar_day_kwh"]
        missing = sorted(set(required) - set(table.columns))
        if missing:
            raise ValueError(f"{name}: missing columns: {', '.join(missing)}")
        if len(table) != summary["output_row_counts"][name] or table.session_count.sum() != summary["input_session_count"]:
            raise ValueError(f"{name}: dimensions/counts disagree with the verified summary.")
        if name.startswith("monthly"):
            table["is_partial_boundary_month"] = parse_boolean_flags(table.is_partial_boundary_month, name)
            if table.is_partial_boundary_month.isna().any():
                raise ValueError(f"{name}: partial-month indicators must be present.")
        tables[name] = table
    if tables["hourly_demand"].Charging_Hour.tolist() != list(range(24)):
        raise ValueError("Hourly summaries must contain ordered hours 0–23.")
    if tables["weekday_demand"].Weekday_Name.tolist() != WEEKDAYS:
        raise ValueError("Weekday summaries must be ordered Monday–Sunday.")
    return tables, summary


def finish_figure(fig, note):
    """Reserve room for a short interpretation note beneath the plot."""
    fig.text(0.08, 0.02, note, fontsize=9, va="bottom", linespacing=1.5)
    fig.tight_layout(rect=(0, 0.12, 1, 0.97))
    return fig


def style_axis(ax, ylabel):
    """Keep quantitative axes grounded at zero with simple horizontal guides."""
    ax.set_ylabel(ylabel)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    sns.despine(ax=ax)


def month_ticks(ax, table):
    """Identify represented partial months separately from missing measurements."""
    labels = table.Year_Month + table.is_partial_boundary_month.map({True: "*", False: ""})
    ax.set_xticks(range(len(table)), labels, rotation=55, ha="right", fontsize=9)
    ax.set_xlabel("Session-start year-month (* partial calendar coverage)")


def plot_hourly(table):
    """Show hourly demand, mean, and all extreme ties without dramatic scaling."""
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(table.Charging_Hour, table.avg_sessions_per_day, color=BLUE)
    mean = table.avg_sessions_per_day.mean()
    ax.axhline(mean, color="black", linestyle="--", linewidth=1, label=f"Mean hour: {mean:.2f}")
    for label, value, x, y in [("Maximum", table.avg_sessions_per_day.max(), 0.02, 0.96),
                                ("Minimum", table.avg_sessions_per_day.min(), 0.59, 0.96)]:
        hours = table.loc[table.avg_sessions_per_day.eq(value), "Charging_Hour"].tolist()
        text = ", ".join(f"{h:02d}" for h in hours)
        if len(hours) > 6:
            text = f"{len(hours)} tied hours"
        ax.text(x, y, f"{label}: {value:.2f} at {text}", transform=ax.transAxes, va="top", fontsize=10)
    ax.set_ylim(0, table.avg_sessions_per_day.max() * 1.35)
    ax.set_xticks(range(24))
    ax.set_xlabel("Session-start hour (timezone unverified)")
    ax.set_title("Hourly session starts: average per calendar day")
    style_axis(ax, "Session starts / calendar day")
    ax.legend(loc="upper right", bbox_to_anchor=(1, 0.84), frameon=False)
    return finish_figure(fig, "All 24 hours use the same inclusive calendar denominator. Highest starts do not establish congestion.")


def plot_daily(table):
    """Plot daily counts and a trailing window requiring seven daily observations."""
    dates = pd.to_datetime(table.Charging_Date, format="%Y-%m-%d")
    moving = table.session_count.rolling(window=7, min_periods=7).mean()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dates, table.session_count, color=BLUE, linewidth=0.7, alpha=0.55, label="Daily starts")
    ax.plot(dates, moving, color=ORANGE, linewidth=1.6, label="Trailing 7-day mean")
    ax.set_title("Daily session starts and trailing 7-day mean")
    ax.set_xlabel("Session-start date")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=9))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    style_axis(ax, "Session starts / day")
    ax.legend(frameon=False, loc="lower left")
    return finish_figure(fig, "First six moving-average values are missing: seven daily observations are required.\nZero-session dates are retained; complete collection is assumed, not verified.")


def plot_weekdays(weekday, weekend):
    """Compare normalized weekdays and weekday/weekend rates on equal scales."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [2.5, 1]})
    for ax, table, labels in [(axes[0], weekday, weekday.Weekday_Name.str[:3]),
                              (axes[1], weekend, weekend.Day_Type)]:
        bars = ax.bar(labels, table.avg_sessions_per_day, color=BLUE)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
        style_axis(ax, "Session starts / represented day")
    ceiling = max(weekday.avg_sessions_per_day.max(), weekend.avg_sessions_per_day.max()) * 1.2
    for ax in axes:
        ax.set_ylim(0, ceiling)
    axes[0].set_title("Weekday comparison (Monday–Sunday)")
    axes[1].set_title("Weekday / weekend")
    return finish_figure(fig, "Each denominator counts its own calendar dates; weekday/weekend totals are not compared directly.")


def plot_day_hour(table):
    """Reshape the verified 168-cell table; no session aggregation is performed."""
    values = table.pivot(index="Weekday_Index", columns="Charging_Hour", values="avg_sessions_per_day").reindex(index=range(7), columns=range(24))
    fig, ax = plt.subplots(figsize=(12, 5))
    maximum = values.max().max()
    sns.heatmap(values, cmap="viridis", vmin=0, vmax=max(1, maximum), ax=ax,
                cbar_kws={"label": "Session starts / represented weekday"}, linewidths=0.3)
    ax.set_yticklabels(WEEKDAYS, rotation=0)
    ax.set_xlabel("Session-start hour (timezone unverified)")
    ax.set_ylabel("")
    ax.set_title("Weekday–hour demand: average session starts")
    return finish_figure(fig, "Each cell uses the count of that weekday's calendar dates. Color scale starts at zero.\nBlank cells indicate undefined rates, not measured zero demand.")


def plot_monthly(table):
    """Display year-month averages with hatched partial coverage bars."""
    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(range(len(table)), table.avg_sessions_per_day, color=BLUE)
    for bar, partial in zip(bars, table.is_partial_boundary_month):
        if partial:
            bar.set_hatch("///")
            bar.set_edgecolor("black")
    month_ticks(ax, table)
    ax.set_title("Monthly session starts: average per represented calendar day")
    style_axis(ax, "Session starts / represented day")
    ax.set_ylim(0, max(1, table.avg_sessions_per_day.max()) * 1.2)
    ax.legend(handles=[Patch(facecolor=BLUE, edgecolor="black", hatch="///", label="Partial boundary month")], frameon=False, loc="upper left")
    return finish_figure(fig, "Hatching/* means a shorter represented calendar range, not missing energy data.\nEven full calendar months do not verify collection uptime; boundary days may be partly observed.")


def plot_energy(hourly, monthly):
    """Plot energy/day profiles attributed to session-start hour and month."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    axes[0].bar(hourly.Charging_Hour, hourly.avg_recorded_energy_per_day_kwh, color=GREEN)
    axes[0].set_xticks(range(24))
    axes[0].set_xlabel("Session-start hour (timezone unverified)")
    axes[0].set_title("Hourly recorded energy associated with session starts")
    axes[1].bar(range(len(monthly)), monthly.avg_recorded_energy_per_day_kwh, color=GREEN)
    month_ticks(axes[1], monthly)
    axes[1].set_title("Monthly recorded energy associated with session starts")
    for ax in axes:
        style_axis(ax, "Recorded energy\n(kWh / calendar day)")
    return finish_figure(fig, ENERGY_NOTE + "\n* Partial boundary month. Missing energy stays missing; numeric zero is allowed.")


def plot_sensitivity(table):
    """Compare energy scenarios and show the retained sample on a separate panel."""
    x = range(len(table))
    baseline = table.total_recorded_energy_kwh / table.calendar_days
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw={"height_ratios": [1.5, 1]})
    axes[0].plot(x, baseline, marker="o", markersize=3, color=BLUE, label="Baseline valid recorded energy")
    axes[0].plot(x, table.retained_avg_recorded_energy_per_calendar_day_kwh,
                 marker="s", markersize=3, color=ORANGE, label="Sensitivity: union-of-flags exclusion")
    axes[0].set_title("Monthly recorded energy: baseline and sensitivity scenario")
    axes[0].legend(frameon=False, loc="lower left")
    style_axis(axes[0], "Recorded energy\n(kWh / calendar day)")
    bars = axes[1].bar(x, table.retained_valid_energy_session_count, color=ORANGE)
    axes[1].bar_label(bars, fmt="%.0f", fontsize=8, padding=2, rotation=90)
    axes[1].set_ylim(0, max(1, table.retained_valid_energy_session_count.max()) * 1.35)
    axes[1].set_title("Retained valid-energy sample count by month")
    style_axis(axes[1], "Retained valid-energy sessions")
    for ax in axes:
        month_ticks(ax, table)
    retained = table.retained_valid_energy_session_count.sum()
    baseline_count = table.valid_energy_session_count.sum()
    fraction = retained / baseline_count if baseline_count else float("nan")
    fraction_range = table.retained_valid_energy_fraction
    note = (f"Retained {retained:,}/{baseline_count:,} valid-energy sessions ({fraction:.2%}); monthly retention {fraction_range.min():.1%}–{fraction_range.max():.1%}. "
            f"Retained-energy dates: {table.retained_energy_observed_dates.sum():,}/{table.calendar_days.sum():,}.\n"
            "Sample composition differs; sensitivity is not corrected/ground-truth data. Demand counts are unchanged.\n"
            + ENERGY_NOTE + " * Partial boundary month; missing observations are not zero-filled.")
    return finish_figure(fig, note)


def generate_figures(tables, output_dir):
    """Save seven figures as 300-dpi PNG and editable SVG with stable metadata."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("01_hourly_demand", plot_hourly, [tables["hourly_demand"]]),
        ("02_daily_demand", plot_daily, [tables["daily_demand"]]),
        ("03_weekday_demand", plot_weekdays, [tables["weekday_demand"], tables["weekday_weekend_demand"]]),
        ("04_day_hour_heatmap", plot_day_hour, [tables["day_hour_demand"]]),
        ("05_monthly_demand", plot_monthly, [tables["monthly_demand"]]),
        ("06_recorded_energy", plot_energy, [tables["hourly_demand"], tables["monthly_demand"]]),
        ("07_monthly_energy_sensitivity", plot_sensitivity, [tables["monthly_energy_sensitivity"]]),
    ]
    paths = []
    settings = {"font.size": 11, "axes.titlesize": 13, "font.family": "DejaVu Sans",
                "svg.fonttype": "none", "svg.hashsalt": "evcharge-phase3"}
    with plt.rc_context(settings), sns.axes_style("white"):
        for name, plot, args in jobs:
            fig = plot(*args)
            try:
                for extension in ["png", "svg"]:
                    path = output_dir / f"{name}.{extension}"
                    metadata = {"Date": None} if extension == "svg" else {"Software": "EVCharge Intelligence"}
                    fig.savefig(path, dpi=300, bbox_inches="tight", metadata=metadata)
                    paths.append(path)
            finally:
                plt.close(fig)
    return paths


def main():
    """CLI reading existing Phase 2 summaries and preserving their fingerprints."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=root / "outputs/demand")
    parser.add_argument("--output-dir", type=Path, help="Defaults to INPUT_DIR/figures")
    args = parser.parse_args()
    try:
        sources = [args.input_dir / (name + ".csv") for name in TABLE_NAMES] + [args.input_dir / "analysis_summary.json"]
        before = {p: file_hash(p) for p in sources}
        tables, _ = load_analysis(args.input_dir)
        paths = generate_figures(tables, args.output_dir or args.input_dir / "figures")
        if before != {p: file_hash(p) for p in sources}:
            raise ValueError("A Phase 2 summary changed during plotting.")
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as error:
        parser.exit(1, f"Demand visualization failed: {error}\n")
    print(f"Generated {len(paths)} artifacts (7 figures, PNG at 300 dpi and SVG).")


if __name__ == "__main__":
    main()
