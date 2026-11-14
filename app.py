import streamlit as st
from fpdf import FPDF
from datetime import datetime
from calculator_engine import ConcreteSection, calculate_project_order, OrderSummary
from shape_visualizer import render_shape_preview

st.set_page_config(
    page_title="Concrete Ordering & Planning Calculator",
    page_icon="🏗️",
    layout="wide",
)

SHAPE_OPTIONS = [
    "Rectangular Slab / Footing",
    "Hole, Column & Round Footing",
    "Circular Slab",
    "Tube / Hollow Column",
    "Curb & Gutter Barrier",
    "Stairs",
]

MIX_PRICES = {"3,000 PSI": 160.0, "3,500 PSI": 168.0, "4,000 PSI": 176.0}


def _sync_price_to_mix() -> None:
    """Reset the editable price when the selected mix strength changes."""
    st.session_state.price_per_yard = MIX_PRICES[st.session_state.selected_mix]


if "selected_mix" not in st.session_state:
    st.session_state.selected_mix = "3,500 PSI"
if "price_per_yard" not in st.session_state:
    st.session_state.price_per_yard = MIX_PRICES[st.session_state.selected_mix]

if "sections" not in st.session_state:
    st.session_state.sections = [
        ConcreteSection(
            name="Main Driveway Slab",
            shape="Rectangular Slab / Footing",
            quantity=1,
            length_ft=20.0,
            width_ft=12.0,
            thickness_in=4.0,
        )
    ]


def _latin1_safe(text: str) -> str:
    """Sanitizes text so built-in FPDF2 Latin-1 fonts never crash on Unicode characters."""
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "—": "-",
        "–": "-",
        "×": "x",
        "→": "->",
    }
    for src, target in replacements.items():
        text = text.replace(src, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_pdf_quote(
    project_name: str,
    mix_psi: str,
    sections: list[ConcreteSection],
    summary: OrderSummary,
    admixtures: dict[str, float],
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Concrete Order & Dispatch Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_project = _latin1_safe(project_name.strip() or "Untitled Pour")
    pdf.cell(
        0,
        6,
        f"Project: {safe_project} | Mix: {mix_psi} | Date: {date_str}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Pour Sections", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for sec in sections:
        vol_yd = sec.exact_cubic_yards()
        vol_m3 = sec.exact_cubic_meters()
        line = _latin1_safe(
            f"- {sec.name} [{sec.shape}]: {sec.summary_text()} -> {vol_yd:.2f} yd3 ({vol_m3:.2f} m3)"
        )
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Volume & Cost Totals", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        6,
        f"Net Exact Volume: {summary.exact_yards:.2f} yd3 / {summary.exact_meters:.2f} m3",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        f"Recommended Order (+{summary.waste_percent:.0f}% waste): {summary.recommended_order_yards:.1f} yd3 / {summary.recommended_order_meters:.2f} m3",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        6,
        f"Estimated Mixer Trucks: {summary.trucks_required} | 80-lb Bags Equiv: ~{summary.equivalent_80lb_bags}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    admix_list = ", ".join(admixtures.keys()) if admixtures else "None"
    pdf.cell(0, 6, f"Admixtures: {admix_list}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Estimated Total Cost: ${summary.estimated_total:,.2f}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())


# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Supplier & Mix Settings")
    project_name = st.text_input("Project Name", value="Residential Pour")
    selected_mix = st.selectbox(
        "Concrete Mix Strength",
        list(MIX_PRICES.keys()),
        key="selected_mix",
        on_change=_sync_price_to_mix,
    )
    price_per_yard = st.number_input(
        "Price per Cubic Yard ($)",
        min_value=50.0,
        step=5.0,
        key="price_per_yard",
    )

    admix_selected = {}
    if st.checkbox("Fiber Mesh (+$12/yd³)"):
        admix_selected["Fiber Mesh"] = 12.0
    if st.checkbox("Air Entrainment (+$8/yd³)"):
        admix_selected["Air Entrainment"] = 8.0
    if st.checkbox("Hot-Weather Retarder (+$10/yd³)"):
        admix_selected["Retarder"] = 10.0

    truck_capacity = st.number_input("Truck Capacity (yd³)", min_value=5.0, value=9.5, step=0.5)
    short_load_threshold = st.number_input("Short-Load Threshold (yd³)", min_value=1.0, value=4.0, step=0.5)
    short_load_fee = st.number_input("Short-Load Fee ($)", min_value=0.0, value=150.0, step=25.0)


# --- MAIN WORKSPACE ---
st.title("🏗️ Concrete Ordering & Planning Calculator")
col_left, col_right = st.columns([1.15, 1], gap="large")

with col_left:
    st.subheader("1. Configure Pour Shape")
    with st.container(border=True):
        shape_choice = st.selectbox("Select Concrete Shape", options=SHAPE_OPTIONS)
        default_label = shape_choice.partition("/")[0].strip()
        c_name, c_qty = st.columns([2.5, 1])
        sec_name = c_name.text_input("Section Label", value=default_label)
        qty = c_qty.number_input("Qty", min_value=1, value=1, step=1)

        draft_section = ConcreteSection(
            name=sec_name.strip() or default_label,
            shape=shape_choice,
            quantity=int(qty),
        )
        has_validation_error = False

        if shape_choice == "Rectangular Slab / Footing":
            c1, c2, c3 = st.columns(3)
            draft_section.length_ft = c1.number_input("Length (ft)", min_value=0.5, value=10.0, step=1.0)
            draft_section.width_ft = c2.number_input("Width (ft)", min_value=0.5, value=10.0, step=1.0)
            draft_section.thickness_in = c3.number_input("Thickness (in)", min_value=1.0, value=4.0, step=0.5)
            if draft_section.thickness_in > 12.0:
                st.warning(
                    f"⚠️ Thickness is **{draft_section.thickness_in} in** ({draft_section.thickness_in / 12:.1f} ft). Verify inches vs. feet!"
                )

        elif shape_choice == "Hole, Column & Round Footing":
            c1, c2 = st.columns(2)
            draft_section.diameter_in = c1.number_input("Diameter (in)", min_value=4.0, value=12.0, step=2.0)
            draft_section.depth_ft = c2.number_input("Depth / Height (ft)", min_value=0.5, value=4.0, step=0.5)

        elif shape_choice == "Circular Slab":
            c1, c2 = st.columns(2)
            draft_section.diameter_in = c1.number_input("Diameter (in)", min_value=12.0, value=120.0, step=6.0)
            draft_section.thickness_in = c2.number_input("Thickness (in)", min_value=1.0, value=4.0, step=0.5)

        elif shape_choice == "Tube / Hollow Column":
            c1, c2, c3 = st.columns(3)
            draft_section.outer_diameter_in = c1.number_input("Outer Dia (in)", min_value=6.0, value=24.0, step=2.0)
            draft_section.inner_diameter_in = c2.number_input("Inner Dia (in)", min_value=2.0, value=18.0, step=2.0)
            draft_section.depth_ft = c3.number_input("Length / Height (ft)", min_value=0.5, value=8.0, step=0.5)
            if draft_section.inner_diameter_in >= draft_section.outer_diameter_in:
                st.error("Inner diameter must be smaller than outer diameter.")
                has_validation_error = True

        elif shape_choice == "Curb & Gutter Barrier":
            c1, c2, c3 = st.columns(3)
            draft_section.length_ft = c1.number_input("Total Run Length (ft)", min_value=1.0, value=25.0, step=1.0)
            draft_section.curb_depth_in = c2.number_input("Curb Depth (in)", min_value=2.0, value=6.0, step=1.0)
            draft_section.curb_height_in = c3.number_input("Curb Height (in)", min_value=2.0, value=6.0, step=1.0)
            c4, c5 = st.columns(2)
            draft_section.gutter_width_in = c4.number_input("Gutter Width (in)", min_value=2.0, value=12.0, step=1.0)
            draft_section.flag_thickness_in = c5.number_input("Flag Thickness (in)", min_value=2.0, value=6.0, step=1.0)

        elif shape_choice == "Stairs":
            c1, c2, c3 = st.columns(3)
            draft_section.num_steps = int(c1.number_input("Number of Steps", min_value=1, value=4, step=1))
            draft_section.run_in = c2.number_input("Tread Run (in)", min_value=6.0, value=11.0, step=0.5)
            draft_section.rise_in = c3.number_input("Step Rise (in)", min_value=4.0, value=7.5, step=0.5)
            c4, c5 = st.columns(2)
            draft_section.width_ft = c4.number_input("Stair Width (ft)", min_value=1.0, value=4.0, step=0.5)
            draft_section.platform_depth_in = c5.number_input("Top Platform Depth (in)", min_value=0.0, value=36.0, step=6.0)

        # Live 2D / 3D Visual Preview
        view_mode = st.radio("Visual Preview Mode", ["3D Isometric", "2D Blueprint"], horizontal=True)
        st.plotly_chart(render_shape_preview(draft_section, view_mode), width="stretch")

        if st.button(
            "➕ Add Section to Project",
            width="stretch",
            type="primary",
            disabled=has_validation_error,
        ):
            st.session_state.sections.append(draft_section)
            st.rerun()

    # Active Project Sections
    st.subheader("2. Active Project Sections")
    if not st.session_state.sections:
        st.info("No sections added yet. Configure a shape above and click Add Section.")
    else:
        for idx, sec in enumerate(st.session_state.sections):
            with st.container(border=True):
                sc1, sc2, sc3 = st.columns([3, 1.8, 0.5])
                sc1.markdown(f"**{sec.name}** *({sec.shape})*\n\n{sec.summary_text()}")
                sc2.metric("Volume", f"{sec.exact_cubic_yards():.2f} yd³", f"{sec.exact_cubic_meters():.2f} m³")
                if sc3.button("🗑️", key=f"del_{idx}"):
                    st.session_state.sections.pop(idx)
                    st.rerun()

with col_right:
    st.subheader("3. Waste & Order Summary")
    waste_preset = st.selectbox(
        "Waste Allowance Preset",
        [
            "Tightly formed flat slab (+5%)",
            "Standard residential pour (+10%)",
            "Uneven trench or footing (+15%)",
            "Custom (%)",
        ],
    )
    if "5%" in waste_preset:
        waste_pct = 5.0
    elif "10%" in waste_preset:
        waste_pct = 10.0
    elif "15%" in waste_preset:
        waste_pct = 15.0
    else:
        waste_pct = st.number_input("Custom Waste (%)", 0.0, 50.0, 10.0)

    summary = calculate_project_order(
        sections=st.session_state.sections,
        waste_percent=waste_pct,
        price_per_yard=price_per_yard,
        admixture_costs_per_yard=admix_selected,
        truck_capacity_yards=truck_capacity,
        short_load_threshold_yards=short_load_threshold,
        short_load_fee=short_load_fee,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Order Volume",
        f"{summary.recommended_order_yards:.1f} yd³",
        f"{summary.recommended_order_meters:.2f} m³",
    )
    m2.metric("Mixer Trucks", f"{summary.trucks_required}")
    m3.metric("Estimated Total", f"${summary.estimated_total:,.2f}")

    if summary.is_short_load:
        st.warning(
            f"🚚 Short-Load Alert: Order is under {short_load_threshold:.1f} yd³ (+${summary.short_load_fee_applied:,.2f} fee). Equivalent to ~{summary.equivalent_80lb_bags} bags (80-lb)."
        )
    elif summary.recommended_order_yards > 0:
        st.success("✅ Full-Load Tier: No short-load fee applied.")

    with st.container(border=True):
        st.markdown("**Imperial & Metric Breakdown**")
        st.write(f"• Net Exact Volume: {summary.exact_yards:.2f} yd³ | {summary.exact_meters:.2f} m³")
        st.write(f"• With {waste_pct:.0f}% Waste: {summary.yards_with_waste:.2f} yd³ | {summary.meters_with_waste:.2f} m³")
        st.write(
            f"• 4\" Gravel Sub-Base: {summary.subbase_gravel_tons:.2f} tons | Wire Mesh: {summary.wire_mesh_sqft:.1f} sq ft"
        )

    if summary.recommended_order_yards > 0:
        pdf_bytes = generate_pdf_quote(
            project_name,
            selected_mix,
            st.session_state.sections,
            summary,
            admix_selected,
        )
        st.download_button(
            "📄 Download PDF Quote & Dispatch Summary",
            data=pdf_bytes,
            file_name="concrete_quote.pdf",
            mime="application/pdf",
            width="stretch",
            type="primary",
        )