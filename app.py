import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="US Flight Delay Explorer",
    page_icon="✈️",
    layout="wide"
)

BASE = Path(__file__).resolve().parent

TIME_ORDER = [
    "Overnight", "Early Morning",
    "Morning", "Afternoon", "Evening"
]

WEEK_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday"
]

CAUSES = {
    "CarrierDelay": "Carrier",
    "WeatherDelay": "Weather",
    "NASDelay": "National Aviation System",
    "SecurityDelay": "Security",
    "LateAircraftDelay": "Late Aircraft"
}

@st.cache_data
def load_data():
    return (
        pd.read_csv(BASE / "patterns.csv"),
        pd.read_csv(BASE / "conditions.csv"),
        pd.read_csv(BASE / "causes.csv")
    )

patterns, conditions, causes = load_data()

def aggregate(df, group_cols):
    result = (
        df.groupby(group_cols, as_index=False)
        .agg(
            Flights=("Flights", "sum"),
            DelayedFlights=("DelayedFlights", "sum")
        )
    )
    result["DelayRate"] = (
        result["DelayedFlights"] / result["Flights"] * 100
    )
    return result

def month_filter(df, month):
    if month == "All Months":
        return df.copy()
    return df[df["Month"] == int(month)].copy()

def no_data():
    st.info("No data available for these filters.")

# Header
st.title("✈️ U.S. Flight Delay Explorer")
st.markdown(
    "### Patterns, Travel Conditions, and Reported Causes"
)
st.write(
    "Explore historical arrival-delay patterns across "
    "U.S. airports, airlines, routes, and departure times."
)

available_months = sorted(patterns["Month"].unique())
month_names = {
    1:"January", 2:"February", 3:"March",
    4:"April", 5:"May", 6:"June",
    7:"July", 8:"August", 9:"September",
    10:"October", 11:"November", 12:"December"
}

st.sidebar.header("Global Filters")

month_choice = st.sidebar.selectbox(
    "Month",
    ["All Months"] + list(available_months),
    format_func=lambda x: month_names.get(x, x)
)

if len(available_months) == 1:
    st.info(
        f"Pilot analysis: {month_names[available_months[0]]} "
        "2025 data only. Full-year analysis is not yet available."
    )
else:
    st.caption(
        "Coverage: 2025 | Available months: "
        + ", ".join(month_names[m] for m in available_months)
    )

st.caption(
    "Delay = arrival at least 15 minutes late. "
    "Cancelled and diverted flights are excluded "
    "from arrival-delay rates."
)

tab1, tab2, tab3 = st.tabs([
    "1. Overall Patterns",
    "2. Travel Conditions",
    "3. Reported Causes"
])

# =====================================================
# TAB 1: OVERALL PATTERNS
# =====================================================

with tab1:
    st.header("Where and When Do Delays Occur?")

    p = month_filter(patterns, month_choice)

    n = p["Flights"].sum()
    late = p["DelayedFlights"].sum()
    rate = 100 * late / n if n else 0

    a, b, c = st.columns(3)
    a.metric("Eligible Arrivals", f"{n:,}")
    b.metric("Delayed Arrivals", f"{late:,}")
    c.metric("Delay Rate", f"{rate:.1f}%")

    # Airport dot plot
    st.subheader("Airport-Level Delay Patterns")

    minimum = st.slider(
        "Minimum eligible flights per airport",
        min_value=100,
        max_value=10000,
        value=1000,
        step=100
    )

    airports = aggregate(p, ["Origin"])
    airports = airports[airports["Flights"] >= minimum]

    # Select busiest airports, not worst-ranked airports
    airports = (
        airports.nlargest(20, "Flights")
        .sort_values("DelayRate")
    )

    if airports.empty:
        no_data()
    else:
        fig = px.scatter(
            airports,
            x="DelayRate",
            y="Origin",
            hover_data=["Flights", "DelayedFlights"],
            labels={
                "DelayRate": "Arrival Delay Rate (%)",
                "Origin": "Departure Airport"
            },
            title="Delay Rates at the 20 Busiest Eligible Airports"
        )
        fig.update_traces(marker_size=12)
        fig.update_layout(
            yaxis={"categoryorder": "array",
                   "categoryarray": airports["Origin"].tolist()}
        )
        st.plotly_chart(fig, use_container_width=True)

    # Hourly line chart
    st.subheader("Delay Patterns Across the Day")

    hourly = aggregate(p, ["DepartureHour"])
    hourly = hourly.sort_values("DepartureHour")

    fig = px.line(
        hourly,
        x="DepartureHour",
        y="DelayRate",
        markers=True,
        hover_data=["Flights"],
        labels={
            "DepartureHour": "Scheduled Departure Hour",
            "DelayRate": "Arrival Delay Rate (%)"
        }
    )
    fig.update_xaxes(dtick=2)
    st.plotly_chart(fig, use_container_width=True)

    # Weekday × hour heatmap
    st.subheader("Weekday × Departure Hour")

    heat = aggregate(
        p, ["Weekday", "DepartureHour"]
    )

    matrix = heat.pivot(
        index="Weekday",
        columns="DepartureHour",
        values="DelayRate"
    ).reindex(WEEK_ORDER)

    fig = px.imshow(
        matrix,
        aspect="auto",
        color_continuous_scale="YlOrRd",
        labels={
            "x": "Scheduled Departure Hour",
            "y": "Weekday",
            "color": "Delay Rate (%)"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

    # Monthly trend only when multiple months exist
    if len(available_months) > 1:
        st.subheader("Monthly Delay Trend")
        monthly = aggregate(patterns, ["Month"])
        monthly = monthly.sort_values("Month")
        fig = px.line(
            monthly, x="Month", y="DelayRate",
            markers=True,
            labels={
                "Month": "Month",
                "DelayRate": "Arrival Delay Rate (%)"
            }
        )
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)


# =====================================================
# TAB 2: TRAVEL CONDITIONS
# =====================================================

with tab2:
    st.header("How Do Patterns Vary by Travel Conditions?")

    st.write(
        "Choose a route and compare the time-of-day "
        "delay patterns of airlines serving that route."
    )

    c = month_filter(conditions, month_choice)

    origins = sorted(c["Origin"].dropna().unique())
    origin = st.selectbox("Origin", origins)

    dests = sorted(
        c.loc[c["Origin"] == origin, "Dest"]
        .dropna().unique()
    )
    dest = st.selectbox("Destination", dests)

    chosen_route = c[
        (c["Origin"] == origin) &
        (c["Dest"] == dest)
    ].copy()

    airlines = sorted(
        chosen_route["Airline"].unique()
    )
    selected_airlines = st.multiselect(
        "Airlines",
        airlines,
        default=airlines
    )

    minimum_group = st.number_input(
        "Minimum flights per airline/time period",
        min_value=1,
        value=30,
        step=10
    )

    chosen_route = chosen_route[
        chosen_route["Airline"].isin(selected_airlines)
    ]

    if chosen_route.empty:
        no_data()
    else:
        summary = aggregate(
            chosen_route, ["Airline", "TimePeriod"]
        )

        summary = summary[
            summary["Flights"] >= minimum_group
        ].copy()

        if summary.empty:
            no_data()
        else:
            st.subheader(f"{origin} → {dest}")

            # Airline × time heatmap
            matrix = summary.pivot(
                index="Airline",
                columns="TimePeriod",
                values="DelayRate"
            ).reindex(columns=TIME_ORDER)

            matrix = matrix.dropna(
                axis=1, how="all"
            )

            fig = px.imshow(
                matrix,
                aspect="auto",
                color_continuous_scale="Blues",
                labels={
                    "x": "Departure Time Period",
                    "y": "Airline",
                    "color": "Delay Rate (%)"
                }
            )
            st.plotly_chart(fig, use_container_width=True)

            # Line chart
            st.subheader("Airline Delay Patterns by Time")

            fig = px.line(
                summary,
                x="TimePeriod",
                y="DelayRate",
                color="Airline",
                markers=True,
                category_orders={
                    "TimePeriod": TIME_ORDER
                },
                hover_data=["Flights", "DelayedFlights"],
                labels={
                    "TimePeriod": "Departure Time",
                    "DelayRate": "Arrival Delay Rate (%)"
                }
            )
            st.plotly_chart(fig, use_container_width=True)

            st.caption(
                "Missing airline/time combinations mean "
                "that the minimum flight count was not met. "
                "Lines connect categorical time periods "
                "to show descriptive patterns."
            )

            st.subheader("Detailed Data")
            st.dataframe(
                summary.sort_values(["Airline", "TimePeriod"]),
                hide_index=True,
                use_container_width=True
            )

            st.download_button(
                "Download Selected Data",
                data=summary.to_csv(index=False),
                file_name="route_delay_comparison.csv",
                mime="text/csv"
            )


# =====================================================
# TAB 3: REPORTED DELAY CAUSES
# =====================================================

with tab3:
    st.header("What Are the Reported Delay Causes?")

    st.write(
        "Compare the composition of reported delay minutes "
        "across airlines, airports and departure times."
    )

    d = month_filter(causes, month_choice)

    airport_choice = st.selectbox(
        "Airport",
        ["All Airports"] + sorted(d["Origin"].unique())
    )

    if airport_choice != "All Airports":
        d = d[d["Origin"] == airport_choice]

    airline_choice = st.selectbox(
        "Airline",
        ["All Airlines"] + sorted(d["Airline"].unique())
    )

    if airline_choice != "All Airlines":
        d = d[d["Airline"] == airline_choice]

    if d.empty:
        no_data()
    else:
        reported_flights = int(d["ReportedFlights"].sum())
        st.metric(
            "Flights with Complete Cause Reports",
            f"{reported_flights:,}"
        )

        cause_cols = list(CAUSES.keys())

        cause_summary = (
            d.groupby("TimePeriod", as_index=False)
            [cause_cols].sum()
        )

        long = cause_summary.melt(
            id_vars="TimePeriod",
            value_vars=cause_cols,
            var_name="Cause",
            value_name="Minutes"
        )

        long["Cause"] = long["Cause"].map(CAUSES)

        long["TotalMinutes"] = (
            long.groupby("TimePeriod")["Minutes"]
            .transform("sum")
        )

        long = long[long["TotalMinutes"] > 0].copy()

        if long.empty:
            no_data()
        else:
            long["Share"] = (
                long["Minutes"] / long["TotalMinutes"] * 100
            )

            # Stacked composition
            st.subheader("Cause Composition by Departure Time")

            fig = px.bar(
                long,
                x="TimePeriod",
                y="Share",
                color="Cause",
                barmode="stack",
                category_orders={
                    "TimePeriod": TIME_ORDER
                },
                hover_data=["Minutes"],
                labels={
                    "Share": "Share of Reported Delay Minutes (%)",
                    "TimePeriod": "Departure Time"
                }
            )
            fig.update_yaxes(range=[0, 100])
            st.plotly_chart(fig, use_container_width=True)

            # Overall cause-minute totals
            st.subheader("Reported Delay Minutes by Cause")

            totals = (
                long.groupby("Cause", as_index=False)
                ["Minutes"].sum()
            ).sort_values("Minutes")

            fig = px.bar(
                totals,
                x="Minutes",
                y="Cause",
                orientation="h",
                labels={
                    "Minutes": "Reported Delay Minutes",
                    "Cause": "Reported Cause"
                }
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                long[
                    ["TimePeriod", "Cause", "Minutes", "Share"]
                ],
                hide_index=True,
                use_container_width=True
            )

        st.caption(
            "Reported delay causes reflect airline-reported "
            "categories for delayed arrivals with complete "
            "cause data. They do not establish causality. "
            "Shares are calculated from reported delay minutes, "
            "not percentages of all flights."
        )

st.divider()
st.caption(
    "Data: U.S. Bureau of Transportation Statistics | "
    "Reporting Carrier On-Time Performance, 2025. "
    "Historical descriptive analysis; not a flight prediction model."
)
