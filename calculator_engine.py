import math
from dataclasses import dataclass
from typing import List, Dict, Optional

CUBIC_YARDS_TO_METERS = 0.764554858


@dataclass
class ConcreteSection:
    """Represents a concrete pour section across 6 distinct geometry types."""
    name: str
    shape: str
    quantity: int = 1
    # Shared & Rectangular / Circular dimensions
    length_ft: float = 0.0
    width_ft: float = 0.0
    thickness_in: float = 0.0
    diameter_in: float = 0.0
    depth_ft: float = 0.0
    # Tube / Hollow Cylinder dimensions
    outer_diameter_in: float = 0.0
    inner_diameter_in: float = 0.0
    # Curb & Gutter dimensions
    curb_depth_in: float = 0.0
    curb_height_in: float = 0.0
    gutter_width_in: float = 0.0
    flag_thickness_in: float = 0.0
    # Stairs dimensions
    num_steps: int = 1
    run_in: float = 0.0
    rise_in: float = 0.0
    platform_depth_in: float = 0.0

    def exact_cubic_yards(self) -> float:
        """Calculates raw net volume in cubic yards."""
        if self.shape == "Rectangular Slab / Footing":
            cubic_feet = self.length_ft * self.width_ft * (self.thickness_in / 12.0)

        elif self.shape == "Hole, Column & Round Footing":
            radius_ft = (self.diameter_in / 12.0) / 2.0
            cubic_feet = math.pi * (radius_ft ** 2) * self.depth_ft

        elif self.shape == "Circular Slab":
            radius_ft = (self.diameter_in / 12.0) / 2.0
            cubic_feet = math.pi * (radius_ft ** 2) * (self.thickness_in / 12.0)

        elif self.shape == "Tube / Hollow Column":
            r_outer_ft = (self.outer_diameter_in / 12.0) / 2.0
            r_inner_ft = (self.inner_diameter_in / 12.0) / 2.0
            if r_inner_ft >= r_outer_ft:
                return 0.0
            cubic_feet = math.pi * ((r_outer_ft ** 2) - (r_inner_ft ** 2)) * self.depth_ft

        elif self.shape == "Curb & Gutter Barrier":
            # Cross-sectional area = Gutter Flag + Vertical Curb Back
            flag_area_sqft = (self.gutter_width_in / 12.0) * (self.flag_thickness_in / 12.0)
            curb_area_sqft = (self.curb_depth_in / 12.0) * (self.curb_height_in / 12.0)
            cubic_feet = (flag_area_sqft + curb_area_sqft) * self.length_ft

        elif self.shape == "Stairs":
            # Sum of progressive step risers + optional top landing platform
            w_ft = self.width_ft
            run_ft = self.run_in / 12.0
            rise_ft = self.rise_in / 12.0
            plat_ft = self.platform_depth_in / 12.0

            steps_vol = sum((i * rise_ft) * run_ft * w_ft for i in range(1, self.num_steps + 1))
            total_height_ft = self.num_steps * rise_ft
            platform_vol = plat_ft * total_height_ft * w_ft
            cubic_feet = steps_vol + platform_vol

        else:
            raise ValueError(f"Unsupported shape: {self.shape}")

        return (cubic_feet * self.quantity) / 27.0

    def exact_cubic_meters(self) -> float:
        """Converts exact cubic yards to cubic meters."""
        return self.exact_cubic_yards() * CUBIC_YARDS_TO_METERS

    def surface_area_sqft(self) -> float:
        """Calculates flat footprint area in sq ft for sub-base and wire mesh."""
        if self.shape == "Rectangular Slab / Footing":
            return self.length_ft * self.width_ft * self.quantity
        elif self.shape == "Circular Slab":
            radius_ft = (self.diameter_in / 12.0) / 2.0
            return math.pi * (radius_ft ** 2) * self.quantity
        return 0.0

    def summary_text(self) -> str:
        """Returns a clean human-readable dimension string."""
        if self.shape == "Rectangular Slab / Footing":
            return f"{self.length_ft}' L × {self.width_ft}' W × {self.thickness_in}\" T (Qty: {self.quantity})"
        elif self.shape == "Hole, Column & Round Footing":
            return f"{self.diameter_in}\" Dia × {self.depth_ft}' Depth (Qty: {self.quantity})"
        elif self.shape == "Circular Slab":
            return f"{self.diameter_in}\" Dia × {self.thickness_in}\" Thick (Qty: {self.quantity})"
        elif self.shape == "Tube / Hollow Column":
            return f"{self.outer_diameter_in}\" OD / {self.inner_diameter_in}\" ID × {self.depth_ft}' L (Qty: {self.quantity})"
        elif self.shape == "Curb & Gutter Barrier":
            return f"{self.length_ft}' L | Curb {self.curb_depth_in}\"×{self.curb_height_in}\" + Gutter {self.gutter_width_in}\"×{self.flag_thickness_in}\" (Qty: {self.quantity})"
        elif self.shape == "Stairs":
            return f"{self.num_steps} Steps ({self.rise_in}\"R × {self.run_in}\"T) × {self.width_ft}' W (Qty: {self.quantity})"
        return ""


@dataclass
class OrderSummary:
    """Holds all calculated volumes (imperial & metric), logistics, and costs."""
    exact_yards: float
    exact_meters: float
    waste_percent: float
    yards_with_waste: float
    meters_with_waste: float
    recommended_order_yards: float
    recommended_order_meters: float
    is_short_load: bool
    trucks_required: int
    equivalent_80lb_bags: int
    subbase_gravel_tons: float
    wire_mesh_sqft: float
    concrete_subtotal: float
    admixtures_total: float
    short_load_fee_applied: float
    estimated_total: float


def round_up_half_yard(yards: float) -> float:
    """Rounds volume up to the nearest 0.5 cubic yard."""
    if yards <= 0:
        return 0.0
    return math.ceil(yards * 2.0) / 2.0


def calculate_project_order(
    sections: List[ConcreteSection],
    waste_percent: float = 10.0,
    price_per_yard: float = 168.0,
    admixture_costs_per_yard: Optional[Dict[str, float]] = None,
    truck_capacity_yards: float = 9.5,
    short_load_threshold_yards: float = 4.0,
    short_load_fee: float = 150.0,
    subbase_depth_in: float = 4.0,
) -> OrderSummary:
    """Computes complete concrete logistics, metric/imperial totals, and pricing."""
    admixture_costs_per_yard = admixture_costs_per_yard or {}

    exact_yards = sum(sec.exact_cubic_yards() for sec in sections)
    total_slab_sqft = sum(sec.surface_area_sqft() for sec in sections)

    yards_with_waste = exact_yards * (1.0 + (waste_percent / 100.0))
    order_yards = round_up_half_yard(yards_with_waste)

    # Metric equivalents
    exact_meters = exact_yards * CUBIC_YARDS_TO_METERS
    meters_with_waste = yards_with_waste * CUBIC_YARDS_TO_METERS
    order_meters = order_yards * CUBIC_YARDS_TO_METERS

    # Logistics & Bag Comparison
    is_short_load = 0 < order_yards < short_load_threshold_yards
    trucks_required = math.ceil(order_yards / truck_capacity_yards) if order_yards > 0 else 0
    equivalent_bags = math.ceil(yards_with_waste * 45.0)

    # Sub-base & Reinforcement
    subbase_yards = (total_slab_sqft * (subbase_depth_in / 12.0)) / 27.0
    subbase_tons = subbase_yards * 1.4
    wire_mesh_sqft = total_slab_sqft * 1.10

    # Pricing Breakdown
    concrete_subtotal = order_yards * price_per_yard
    admixture_rate = sum(admixture_costs_per_yard.values())
    admixtures_total = order_yards * admixture_rate
    applied_short_load = short_load_fee if is_short_load else 0.0
    estimated_total = concrete_subtotal + admixtures_total + applied_short_load

    return OrderSummary(
        exact_yards=round(exact_yards, 2),
        exact_meters=round(exact_meters, 2),
        waste_percent=waste_percent,
        yards_with_waste=round(yards_with_waste, 2),
        meters_with_waste=round(meters_with_waste, 2),
        recommended_order_yards=order_yards,
        recommended_order_meters=round(order_meters, 2),
        is_short_load=is_short_load,
        trucks_required=trucks_required,
        equivalent_80lb_bags=equivalent_bags,
        subbase_gravel_tons=round(subbase_tons, 2),
        wire_mesh_sqft=round(wire_mesh_sqft, 1),
        concrete_subtotal=round(concrete_subtotal, 2),
        admixtures_total=round(admixtures_total, 2),
        short_load_fee_applied=round(applied_short_load, 2),
        estimated_total=round(estimated_total, 2),
    )
