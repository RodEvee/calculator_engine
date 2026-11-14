import math
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


@dataclass
class ConcreteSection:
    """Represents a single pour section (slab, footing, or cylindrical pier)."""

    name: str
    shape: Literal["rectangle", "cylinder"]
    quantity: int = 1
    # Rectangle dimensions
    length_ft: float = 0.0
    width_ft: float = 0.0
    thickness_in: float = 0.0
    # Cylinder dimensions
    diameter_in: float = 0.0
    depth_ft: float = 0.0

    def validate(self) -> None:
        """Reject invalid dimensions and quantities before calculating."""
        if self.shape not in ("rectangle", "cylinder"):
            raise ValueError(f"Unsupported shape: {self.shape}")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity <= 0
        ):
            raise ValueError(f"{self.name}: quantity must be a positive integer.")

        dimensions = (
            (
                ("length_ft", self.length_ft),
                ("width_ft", self.width_ft),
                ("thickness_in", self.thickness_in),
            )
            if self.shape == "rectangle"
            else (("diameter_in", self.diameter_in), ("depth_ft", self.depth_ft))
        )
        for dimension_name, value in dimensions:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    f"{self.name}: {dimension_name} must be a finite positive number."
                )

    def exact_cubic_yards(self) -> float:
        """Calculates raw volume in cubic yards without waste."""
        self.validate()
        if self.shape == "rectangle":
            cubic_feet = self.length_ft * self.width_ft * (self.thickness_in / 12.0)
        elif self.shape == "cylinder":
            radius_ft = (self.diameter_in / 12.0) / 2.0
            cubic_feet = math.pi * (radius_ft**2) * self.depth_ft
        else:
            raise ValueError(f"Unsupported shape: {self.shape}")

        return (cubic_feet * self.quantity) / 27.0

    def surface_area_sqft(self) -> float:
        """Calculates flat surface area in square feet (for wire mesh & sub-base)."""
        self.validate()
        if self.shape == "rectangle":
            return self.length_ft * self.width_ft * self.quantity
        return 0.0

    def has_thickness_warning(self) -> bool:
        """Flags potential unit-mismatch if slab thickness exceeds 12 inches."""
        return self.shape == "rectangle" and self.thickness_in > 12.0


@dataclass
class OrderSummary:
    """Holds all calculated volumes, logistics, materials, and costs."""

    exact_yards: float
    waste_percent: float
    yards_with_waste: float
    recommended_order_yards: float
    is_short_load: bool
    trucks_required: int
    equivalent_80lb_bags: int
    subbase_gravel_tons: float
    wire_mesh_sqft: float
    concrete_subtotal: float
    admixtures_total: float
    short_load_fee_applied: float
    estimated_total: float
    alerts: List[str] = field(default_factory=list)


def round_up_half_yard(yards: float) -> float:
    """Rounds volume up to the nearest 0.5 cubic yard (standard batch billing)."""
    if yards <= 0:
        return 0.0
    return math.ceil(yards * 2.0) / 2.0


def _validate_finite_number(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite number.")


def calculate_project_order(
    sections: List[ConcreteSection],
    waste_percent: float = 10.0,
    price_per_yard: float = 165.0,
    admixture_costs_per_yard: Optional[Dict[str, float]] = None,
    truck_capacity_yards: float = 9.5,
    short_load_threshold_yards: float = 4.0,
    short_load_fee: float = 150.0,
    subbase_depth_in: float = 4.0,
) -> OrderSummary:
    """Computes complete concrete logistics, material add-ons, and pricing."""
    if sections is None:
        raise ValueError("sections must be a list of concrete sections.")

    for name, value in (
        ("waste_percent", waste_percent),
        ("price_per_yard", price_per_yard),
        ("truck_capacity_yards", truck_capacity_yards),
        ("short_load_threshold_yards", short_load_threshold_yards),
        ("short_load_fee", short_load_fee),
        ("subbase_depth_in", subbase_depth_in),
    ):
        _validate_finite_number(name, value)

    if waste_percent < 0:
        raise ValueError("waste_percent cannot be negative.")
    if price_per_yard < 0 or short_load_fee < 0:
        raise ValueError("Prices and fees cannot be negative.")
    if truck_capacity_yards <= 0:
        raise ValueError("truck_capacity_yards must be greater than zero.")
    if short_load_threshold_yards < 0 or subbase_depth_in < 0:
        raise ValueError("Short-load threshold and sub-base depth cannot be negative.")

    admixture_costs_per_yard = admixture_costs_per_yard or {}
    for name, cost in admixture_costs_per_yard.items():
        _validate_finite_number(f"Admixture cost for {name}", cost)
        if cost < 0:
            raise ValueError(f"Admixture cost for {name} cannot be negative.")

    for section in sections:
        section.validate()

    exact_yards = sum(sec.exact_cubic_yards() for sec in sections)
    total_slab_sqft = sum(sec.surface_area_sqft() for sec in sections)

    yards_with_waste = exact_yards * (1.0 + (waste_percent / 100.0))
    order_yards = round_up_half_yard(yards_with_waste)

    # Logistics & bag comparison
    is_short_load = 0 < order_yards < short_load_threshold_yards
    trucks_required = (
        math.ceil(order_yards / truck_capacity_yards) if order_yards > 0 else 0
    )
    # One 80-lb bag yields ~0.60 cubic feet (45 bags per cubic yard)
    equivalent_bags = math.ceil(yards_with_waste * 45.0)

    # Sub-base & reinforcement (based on rectangular slabs)
    # Crushed stone weighs ~1.4 tons per cubic yard
    subbase_yards = (total_slab_sqft * (subbase_depth_in / 12.0)) / 27.0
    subbase_tons = subbase_yards * 1.4
    wire_mesh_sqft = total_slab_sqft * 1.10  # 10% overlap allowance

    # Pricing breakdown
    concrete_subtotal = order_yards * price_per_yard
    admixture_rate = sum(admixture_costs_per_yard.values())
    admixtures_total = order_yards * admixture_rate
    applied_short_load = short_load_fee if is_short_load else 0.0
    estimated_total = concrete_subtotal + admixtures_total + applied_short_load

    alerts = []
    if is_short_load:
        alerts.append(
            f"Short load: {order_yards:g} yd³ is below the "
            f"{short_load_threshold_yards:g} yd³ threshold."
        )
    for section in sections:
        if section.has_thickness_warning():
            alerts.append(
                f"{section.name}: slab thickness of {section.thickness_in:g} in "
                "exceeds 12 in; confirm the measurement and units."
            )

    return OrderSummary(
        exact_yards=round(exact_yards, 2),
        waste_percent=waste_percent,
        yards_with_waste=round(yards_with_waste, 2),
        recommended_order_yards=order_yards,
        is_short_load=is_short_load,
        trucks_required=trucks_required,
        equivalent_80lb_bags=equivalent_bags,
        subbase_gravel_tons=round(subbase_tons, 2),
        wire_mesh_sqft=round(wire_mesh_sqft, 1),
        concrete_subtotal=round(concrete_subtotal, 2),
        admixtures_total=round(admixtures_total, 2),
        short_load_fee_applied=round(applied_short_load, 2),
        estimated_total=round(estimated_total, 2),
        alerts=alerts,
    )


if __name__ == "__main__":
    sample_sections = [
        ConcreteSection(
            name="Driveway Slab",
            shape="rectangle",
            length_ft=20,
            width_ft=12,
            thickness_in=4,
        ),
        ConcreteSection(
            name="Gate Posts",
            shape="cylinder",
            diameter_in=12,
            depth_ft=3,
            quantity=2,
        ),
    ]
    summary = calculate_project_order(
        sections=sample_sections,
        waste_percent=10.0,
        price_per_yard=170.0,
        admixture_costs_per_yard={"Fiber Mesh": 12.0},
    )
    print(f"Exact Volume: {summary.exact_yards} cu yd")
    print(f"Order Volume (rounded): {summary.recommended_order_yards} cu yd")
    print(f"Alerts: {summary.alerts}")
    print(f"Trucks: {summary.trucks_required}")
    print(f"Estimated Total: ${summary.estimated_total:,.2f}")
