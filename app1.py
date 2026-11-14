import streamlit as st
from fpdf import FPDF
from datetime import datetime
from calculator_engine import ConcreteSection, calculate_project_order, OrderSummary

st.set_page_config(
    page_title="Concrete Ordering & Planning Calculator",
    page_icon="🏗️",
    layout="wide",
)

# Initialize session state for multi-section project builder
if "sections" not in st.session_state:
    st.session_state.sections = [
        ConcreteSection(
            name="Main Slab",
            shape="rectangle",
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
    """Builds a clean, itemized PDF quote/dispatch summary."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Concrete Order & Dispatch Summary", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    date_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    safe_project = _latin1_safe(project_name.strip() or "Untitled Pour")
    safe_mix = _latin1_safe(mix_psi)
    pdf.cell(0, 6, f"Project: {safe_project} | Generated: {date_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Selected Mix: {safe_mix} | Waste Allowance: {summary.waste_percent:.0f}%", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Sections Table Header
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "1. Pour Sections", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(55, 7, "Section Name", border=1)
    pdf.cell(30, 7, "Shape", border=1)
    pdf.cell(65, 7, "Dimensions", border=1)
    pdf.cell(40, 7, "Exact Vol (yd3)", border=1, new_x="LMARGIN", new_y="NEXT")

    # Sections Table Rows
    pdf.set_font("Helvetica", "", 9)
    for sec in sections:
        if sec.shape == "rectangle":
            dims = f"{sec.length_ft}' L x {sec.width_ft}' W x {sec.thickness_in}\" T (x{sec.quantity})"
        else:
            dims = f"{sec.diameter_in}\" Dia x {sec.depth_ft}' D (x{sec.quantity})"

        pdf.cell(55, 7, _latin1_safe(sec.name)[:28], border=1)
        pdf.cell(30, 7, sec.shape.capitalize(), border=1)
        pdf.cell(65, 7, dims, border=1)
        pdf.cell(40, 7, f"{sec.exact_cubic_yards():.2f}", border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Logistics & Materials
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "2. Volume & Logistics Summary", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    logistics_lines = [
        f"Exact Net Volume: {summary.exact_yards:.2f} cubic yards",
        f"Volume with {summary.waste_percent:.0f}% Waste: {summary.yards_with_waste:.2f} cubic yards",
        f"Recommended Order Quantity (0.5 yd increments): {summary.recommended_order_yards:.1f} cubic yards",
        f"Estimated Mixer Trucks Required: {summary.trucks_required} truck(s)",
        f"Short-Load Fee Triggered: {'Yes' if summary.is_short_load else 'No'}",
        f"Bagged Alternative Equivalent: ~{summary.equivalent_80lb_bags} bags (80-lb)",
        f"Est. 4\" Crushed Stone Sub-Base: {summary.subbase_gravel_tons:.2f} tons",
        f"Est. Wire Mesh Reinforcement (+10% overlap): {summary.wire_mesh_sqft:.1f} sq ft",
    ]
    for line in logistics_lines:
        pdf.cell(0, 6, f"  - {line}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Pricing Breakdown
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "3. Estimated Cost Breakdown", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"  - Ready-Mix Concrete Subtotal: ${summary.concrete_subtotal:,.2f}", new_x="LMARGIN", new_y="NEXT")
    admix_names = _latin1_safe(", ".join(admixtures.keys())) if admixtures else "None"
    pdf.cell(0, 6, f"  - Admixtures ({admix_names}): ${summary.admixtures_total:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"  - Short-Load Delivery Fee: ${summary.short_load_fee_applied:,.2f}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"  Estimated Total: ${summary.estimated_total:,.2f}", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


# --- SIDEBAR: Supplier, Mix & Pricing Settings ---
with st.sidebar:
    st.header("⚙️ Supplier & Mix Settings")
    project_name = st.text_input("Project / Job Name", value="Residential Driveway & Apron")

    st.subheader("Mix Strength & Base Price")
    mix_prices = {
        "3,000 PSI (Standard Footings/Walks)": 160.0,
        "3,500 PSI (Residential Slab)": 168.0,
        "4,000 PSI (Driveways/Structural)": 176.0,
    }
    selected_mix = st.selectbox("Concrete Mix Strength", options=list(mix_prices.keys()), index=1)
    price_per_yard = st.number_input(
        "Base Price per Cubic Yard ($)",
        min_value=50.0,
        max_value=500.0,
        value=mix_prices[selected_mix],
        step=5.0,
    )

    st.subheader("Admixtures (per Cubic Yard)")
    admix_selected = {}
    if st.checkbox("Fiber Mesh Reinforcement (+$12/yd³)", value=False):
        admix_selected["Fiber Mesh"] = 12.0
    if st.checkbox("Air Entrainment (+$8/yd³)", value=False):
        admix_selected["Air Entrainment"] = 8.0
    if st.checkbox("Hot-Weather Retarder (+$10/yd³)", value=False):
        admix_selected["Retarder"] = 10.0

    st.subheader("Batch Plant & Truck Rules")
    truck_capacity = st.number_input("Mixer Truck Capacity (yd³)", min_value=5.0, max_value=12.0, value=9.5, step=0.5)
    short_load_threshold = st.number_input("Short-Load Threshold (yd³)", min_value=1.0, max_value=8.0, value=4.0, step=0.5)
    short_load_fee = st.number_input("Flat Short-Load Fee ($)", min_value=0.0, max_value=500.0, value=150.0, step=25.0)


# --- MAIN WORKSPACE ---
st.title("🏗️ Concrete Ordering & Planning Calculator")
st.caption("Build multi-section pours, apply real-world waste presets, check short-load thresholds, and export dispatch quotes.")

col_left, col_right = st.columns([1.15, 1], gap="large")

with col_left:
    st.subheader("1. Add Pour Section")
    with st.container(border=True):
        shape_choice = st.radio(
            "Section Shape",
            options=["Rectangular Slab / Footing", "Cylindrical Column / Pier"],
            horizontal=True,
        )
        sec_name = st.text_input(
            "Section Label",
            value="Thickened Apron" if shape_choice.startswith("Rect") else "Gate Post Footing",
        )

        if shape_choice.startswith("Rect"):
            c1, c2, c3, c4 = st.columns(4)
            length_ft = c1.number_input("Length (ft)", min_value=0.5, value=10.0, step=1.0)
            width_ft = c2.number_input("Width (ft)", min_value=0.5, value=4.0, step=1.0)
            thickness_in = c3.number_input("Thickness (in)", min_value=1.0, value=6.0, step=0.5)
            qty = c4.number_input("Qty", min_value=1, value=1, step=1)

            # Unit-mismatch safeguard
            if thickness_in > 12.0:
                st.warning(
                    f"⚠️ **Check Units:** You entered **{thickness_in} inches** ({thickness_in / 12:.1f} feet) for slab thickness. "
                    "Make sure you didn't enter feet by mistake!"
                )

            if st.button("➕ Add Rectangular Section", use_container_width=True, type="primary"):
                st.session_state.sections.append(
                    ConcreteSection(
                        name=sec_name.strip() or "Rectangular Section",
                        shape="rectangle",
                        quantity=int(qty),
                        length_ft=length_ft,
                        width_ft=width_ft,
                        thickness_in=thickness_in,
                    )
                )
                st.rerun()
        else:
            c1, c2, c3 = st.columns(3)
            diameter_in = c1.number_input("Diameter (in)", min_value=4.0, value=12.0, step=2.0)
            depth_ft = c2.number_input("Depth / Height (ft)", min_value=0.5, value=3.0, step=0.5)
            qty = c3.number_input("Quantity", min_value=1, value=2, step=1)

            if diameter_in > 48.0:
                st.warning(
                    f"⚠️ **Check Units:** You entered **{diameter_in} inches** ({diameter_in / 12:.1f} feet) for pier diameter. "
                    "Confirm that inches were intended."
                )

            if st.button("➕ Add Cylindrical Section", use_container_width=True, type="primary"):
                st.session_state.sections.append(
                    ConcreteSection(
                        name=sec_name.strip() or "Cylindrical Section",
                        shape="cylinder",
                        quantity=int(qty),
                        diameter_in=diameter_in,
                        depth_ft=depth_ft,
                    )
                )
                st.rerun()

    # Display & Manage Existing Sections
    st.subheader("2. Active Project Sections")
    if not st.session_state.sections:
        st.info("No sections added yet. Use the form above to add your first slab or footing.")
    else:
        for idx, sec in enumerate(st.session_state.sections):
            with st.container(border=True):
                sc1, sc2, sc3 = st.columns([3, 2, 1])
                if sec.shape == "rectangle":
                    desc = f"{sec.length_ft}' L × {sec.width_ft}' W × {sec.thickness_in}\" T (Qty: {sec.quantity})"
                else:
                    desc = f"{sec.diameter_in}\" Dia × {sec.depth_ft}' Depth (Qty: {sec.quantity})"

                sc1.markdown(f"**{sec.name}**\n\n{desc}")
                sc2.metric("Net Volume", f"{sec.exact_cubic_yards():.2f} yd³")
                if sc3.button("🗑️", key=f"del_{idx}", help="Remove section"):
                    st.session_state.sections.pop(idx)
                    st.rerun()

        if st.button("Clear All Sections", type="secondary"):
            st.session_state.sections = []
            st.rerun()

    # Waste Allowance Preset
    st.subheader("3. Jobsite Waste Allowance")
    waste_rates = {
        "Tightly formed flat slab (+5%)": 5.0,
        "Standard residential pour (+10%)": 10.0,
        "Complex forms / uneven subgrade (+15%)": 15.0,
    }
    waste_preset = st.selectbox(
        "Select Site Condition",
        options=list(waste_rates.keys()),
    )
    waste_percent = waste_rates[waste_preset]

# --- RIGHT COLUMN: Order Summary & PDF Export ---
with col_right:
    st.subheader("4. Order Summary")
    if not st.session_state.sections:
        st.info("Add at least one pour section to calculate an order.")
    else:
        summary = calculate_project_order(
            sections=st.session_state.sections,
            waste_percent=waste_percent,
            price_per_yard=price_per_yard,
            admixture_costs_per_yard=admix_selected,
            truck_capacity_yards=truck_capacity,
            short_load_threshold_yards=short_load_threshold,
            short_load_fee=short_load_fee,
        )

        for alert in getattr(summary, "alerts", []):
            st.warning(alert)

        metric1, metric2 = st.columns(2)
        metric1.metric("Recommended Order", f"{summary.recommended_order_yards:.1f} yd³")
        metric2.metric("Estimated Total", f"${summary.estimated_total:,.2f}")

        st.write(f"**Exact volume:** {summary.exact_yards:.2f} yd³")
        st.write(f"**With waste ({waste_percent:.0f}%):** {summary.yards_with_waste:.2f} yd³")
        st.write(f"**Estimated mixer trucks:** {summary.trucks_required}")
        st.write(f"**Short-load fee:** ${summary.short_load_fee_applied:,.2f}")

        with st.expander("Site Prep & Bagged Equivalent"):
            st.write(f"**4\" Crushed Stone Sub-Base:** {summary.subbase_gravel_tons:.2f} tons")
            st.write(f"**Wire Mesh (+10% overlap):** {summary.wire_mesh_sqft:.1f} sq ft")
            st.write(f"**80-lb Bagged Equivalent:** ~{summary.equivalent_80lb_bags} bags")

        pdf_bytes = generate_pdf_quote(
            project_name=project_name,
            mix_psi=selected_mix,
            sections=st.session_state.sections,
            summary=summary,
            admixtures=admix_selected,
        )
        safe_filename = f"{project_name.strip().lower().replace(' ', '_') or 'concrete'}_quote.pdf"
        st.download_button(
            "📄 Download PDF Quote",
            data=pdf_bytes,
            file_name=safe_filename,
            mime="application/pdf",
            use_container_width=True,
        )