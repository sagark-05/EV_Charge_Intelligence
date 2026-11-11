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
    from .demand_analysis import parse_boolean_flags, WEEKDAYS, LOCATION_TYPES, CHARGER_TYPES, EXTRA_TABLE_NAMES, sensitivity_has_variation
except ImportError:
    from data_preparation import file_hash
    from demand_analysis import parse_boolean_flags, WEEKDAYS, LOCATION_TYPES, CHARGER_TYPES, EXTRA_TABLE_NAMES, sensitivity_has_variation

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
    for name in EXTRA_TABLE_NAMES:
        table = pd.read_csv(input_dir / (name + ".csv"))
        if len(table) != summary["output_row_counts"][name] or table.session_count.sum() != summary["input_session_count"]:
            raise ValueError(f"{name}: dimensions/counts disagree with the verified summary.")
        tables[name] = table
    if not all(summary.get("additional_reconciliation", {}).values()) or not summary.get("additional_reconciliation"):
        raise ValueError("Additional analyses must reconcile before plotting.")
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
    ax.set_xlabel("Session-start hour (Asia/Kolkata)")
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
    ax.set_xlabel("Session-start hour (Asia/Kolkata)")
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
    axes[0].set_xlabel("Session-start hour (Asia/Kolkata)")
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
    scenario_note = ("No exclusions: curves coincide; baseline demand and sample composition are unchanged."
                     if table.excluded_session_count.sum() == 0 else
                     "Sample composition differs; sensitivity is not corrected/ground-truth data. Demand counts are unchanged.")
    note = (f"Retained {retained:,}/{baseline_count:,} valid-energy sessions ({fraction:.2%}); monthly retention {fraction_range.min():.1%}–{fraction_range.max():.1%}. "
            f"Retained-energy dates: {table.retained_energy_observed_dates.sum():,}/{table.calendar_days.sum():,}.\n"
            + scenario_note + "\n"
            + ENERGY_NOTE + " * Partial boundary month; missing observations are not zero-filled.")
    return finish_figure(fig, note)



def plot_location_profiles(table):
    """Compare within-location percentages on identical axes, with category sample sizes."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    colors = [BLUE, ORANGE, GREEN, "#CC79A7"]
    ceiling = max(1, table.session_percentage.max() * 1.2)
    for ax, location, color in zip(axes.flat, LOCATION_TYPES, colors):
        subset = table.loc[table.Location_Type.eq(location)]
        count = int(subset.location_session_count.iloc[0])
        ax.plot(subset.Charging_Hour, subset.session_percentage, color=color, marker="o", markersize=3)
        ax.set_title(f"{location} (n={count:,})")
        ax.set_xticks(range(0, 24, 3))
        ax.set_xlabel("Session-start hour (Asia/Kolkata)")
        style_axis(ax, "Sessions within location type (%)")
        ax.set_ylim(0, ceiling)
    return finish_figure(fig, "Each represented location type sums to 100% across 24 hours; all panels share the same scale.\nSynthetic site categories; hour-weight generation rules were not supplied, so these are descriptive patterns.")


def plot_weekday_variability(observations):
    """Show daily distributions, including zero-session dates, in Monday–Sunday order."""
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.boxplot(data=observations, x="Weekday_Name", y="session_count", order=WEEKDAYS,
                color=BLUE, ax=ax, fliersize=3)
    ax.set_title("Weekday variability in daily session starts")
    ax.set_xlabel("Local calendar weekday")
    style_axis(ax, "Session starts / represented calendar date")
    return finish_figure(fig, "Daily observations include zero-session dates. Boxes: 25th/50th/75th percentiles; whiskers: 1.5 IQR.\nComplete calendar coverage is assumed; variation is descriptive, not a significance test.")


def plot_time_period_energy(table):
    """Use valid-energy per-session means, not totals divided by unequal period lengths."""
    fig, ax = plt.subplots(figsize=(11, 5))
    labels = [f"{row.Time_Period}\n{row.start_hour_inclusive:02d}–{row.end_hour_exclusive:02d}\nn={row.valid_energy_session_count:,}"
              for row in table.itertuples()]
    bars = ax.bar(labels, table.mean_energy_kwh, color=GREEN)
    ax.bar_label(bars, fmt="%.2f", padding=3)
    ax.set_ylim(0, max(1, table.mean_energy_kwh.max()) * 1.2)
    ax.set_title("Recorded energy per valid-energy session by start period")
    ax.set_xlabel("Non-overlapping start periods (Asia/Kolkata); n = valid-energy sessions")
    style_axis(ax, "Mean delivered energy / session (kWh)")
    return finish_figure(fig, "Whole-session energy is assigned to its session-start period, not measured hourly grid load.\nUnequal period lengths are acceptable for per-session means; invalid energy does not remove demand sessions.")


def plot_charger_comparison(table):
    """Keep energy, active charging and connected occupancy in separate unit-labelled panels."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    x = pd.Series(range(len(table)))
    labels = [f"{row.Charger_Type}\nn={row.session_count:,}" for row in table.itertuples()]
    for ax, mean, median, title, units in [
        (axes[0], "mean_energy_kwh", "median_energy_kwh", "Delivered energy", "Energy / valid-energy session (kWh)"),
        (axes[1], "mean_active_charging_duration_min", "median_active_charging_duration_min", "Active charging", "Active charging duration (minutes)"),
        (axes[2], "mean_connected_duration_min", "median_connected_duration_min", "Connected occupancy", "Connected duration (minutes)"),
    ]:
        ax.bar(x - 0.2, table[mean], width=0.4, color=BLUE, label="Mean")
        ax.bar(x + 0.2, table[median], width=0.4, color=ORANGE, label="Median")
        ax.set_xticks(x, labels, fontsize=9)
        ax.set_title(title)
        style_axis(ax, units)
        ax.set_ylim(0, max(1, table[[mean, median]].max().max()) * 1.25)
        ax.legend(frameon=False)
    return finish_figure(fig, "Active = Charging_End − Session_Start; connected = Session_End − Session_Start. Supplied minutes are checked.\nSynthetic categories and energy limits do not establish causal equipment effects; energy excludes invalid measurements.")


# Only these generated artifact names are owned by the exporter; preserve all other user files.
FIGURE_STEMS = ["01_hourly_demand", "02_daily_demand", "03_weekday_demand", "04_day_hour_heatmap",
                "05_monthly_demand", "06_recorded_energy", "07_monthly_energy_sensitivity",
                "08_location_type_hourly", "09_weekday_variability", "10_time_period_energy", "11_charger_type_comparison"]


def figure_jobs(tables):
    """Keep all distinct charts; include sensitivity only with retained/excluded variation."""
    jobs = [
        ("01_hourly_demand", plot_hourly, [tables["hourly_demand"]]),
        ("02_daily_demand", plot_daily, [tables["daily_demand"]]),
        ("03_weekday_demand", plot_weekdays, [tables["weekday_demand"], tables["weekday_weekend_demand"]]),
        ("04_day_hour_heatmap", plot_day_hour, [tables["day_hour_demand"]]),
        ("05_monthly_demand", plot_monthly, [tables["monthly_demand"]]),
        ("06_recorded_energy", plot_energy, [tables["hourly_demand"], tables["monthly_demand"]]),
    ]
    if sensitivity_has_variation(tables["monthly_energy_sensitivity"]):
        jobs.append(("07_monthly_energy_sensitivity", plot_sensitivity, [tables["monthly_energy_sensitivity"]]))
    jobs.extend([
        ("08_location_type_hourly", plot_location_profiles, [tables["location_type_hourly"]]),
        ("09_weekday_variability", plot_weekday_variability, [tables["daily_weekday_counts"]]),
        ("10_time_period_energy", plot_time_period_energy, [tables["time_period_energy"]]),
        ("11_charger_type_comparison", plot_charger_comparison, [tables["charger_type_comparison"]]),
    ])
    return jobs


def generate_figures(tables, output_dir):
    """Export one 300-dpi PNG per intended chart; remove only owned obsolete artifacts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = figure_jobs(tables)
    intended = {name for name, _, _ in jobs}
    for stem in FIGURE_STEMS:
        svg = output_dir / (stem + ".svg")
        if svg.is_file():
            svg.unlink()
        stale_png = output_dir / (stem + ".png")
        if stem not in intended and stale_png.is_file():
            stale_png.unlink()
    paths = []
    settings = {"font.size": 11, "axes.titlesize": 13, "font.family": "DejaVu Sans"}
    with plt.rc_context(settings), sns.axes_style("white"):
        for name, plot, args in jobs:
            fig = plot(*args)
            try:
                path = output_dir / f"{name}.png"
                fig.savefig(path, dpi=300, bbox_inches="tight", metadata={"Software": "EVCharge Intelligence"})
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
        sources = [args.input_dir / (name + ".csv") for name in [*TABLE_NAMES, *EXTRA_TABLE_NAMES]] + [args.input_dir / "analysis_summary.json"]
        before = {p: file_hash(p) for p in sources}
        tables, _ = load_analysis(args.input_dir)
        paths = generate_figures(tables, args.output_dir or args.input_dir / "figures")
        if before != {p: file_hash(p) for p in sources}:
            raise ValueError("A Phase 2 summary changed during plotting.")
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as error:
        parser.exit(1, f"Demand visualization failed: {error}\n")
    print(f"Generated {len(paths)} charts: one PNG per chart at 300 dpi. No stale owned chart artifacts remain.")


if __name__ == "__main__":
    main()
