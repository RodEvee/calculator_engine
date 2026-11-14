import numpy as np
import plotly.graph_objects as go
from calculator_engine import ConcreteSection


def render_shape_preview(section: ConcreteSection, view_mode: str = "3D Isometric") -> go.Figure:
    """Generates a scaled 2D cross-section/plan or 3D wireframe/mesh preview."""
    fig = go.Figure()

    if view_mode == "2D Blueprint":
        _add_2d_trace(fig, section)
        fig.update_layout(
            height=260,
            margin=dict(l=20, r=20, t=35, b=20),
            title=dict(text=f"2D Preview: {section.shape}", font=dict(size=14)),
            xaxis=dict(scaleanchor="y", scaleratio=1, showgrid=True, zeroline=False, title="ft"),
            yaxis=dict(showgrid=True, zeroline=False, title="ft"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(240,242,246,0.5)",
        )
    else:
        _add_3d_trace(fig, section)
        fig.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=35, b=0),
            title=dict(text=f"3D Preview: {section.shape}", font=dict(size=14)),
            scene=dict(
                aspectmode="data",
                xaxis=dict(title="X (ft)"),
                yaxis=dict(title="Y (ft)"),
                zaxis=dict(title="Z (ft)"),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
        )
    return fig


def _add_2d_trace(fig: go.Figure, s: ConcreteSection):
    if s.shape == "Rectangular Slab / Footing":
        x = [0, s.length_ft, s.length_ft, 0, 0]
        y = [0, 0, s.width_ft, s.width_ft, 0]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                fill="toself",
                fillcolor="rgba(100,116,139,0.4)",
                line=dict(color="#334155", width=2),
                name="Top Plan",
                showlegend=False,
            )
        )

    elif s.shape in ("Hole, Column & Round Footing", "Circular Slab"):
        r = (s.diameter_in / 12.0) / 2.0
        theta = np.linspace(0, 2 * np.pi, 60)
        fig.add_trace(
            go.Scatter(
                x=r * np.cos(theta),
                y=r * np.sin(theta),
                fill="toself",
                fillcolor="rgba(100,116,139,0.4)",
                line=dict(color="#334155", width=2),
                name="Top Circle",
                showlegend=False,
            )
        )

    elif s.shape == "Tube / Hollow Column":
        r_out = (s.outer_diameter_in / 12.0) / 2.0
        r_in = (s.inner_diameter_in / 12.0) / 2.0
        theta = np.linspace(0, 2 * np.pi, 60)
        fig.add_trace(
            go.Scatter(
                x=r_out * np.cos(theta),
                y=r_out * np.sin(theta),
                fill="toself",
                fillcolor="rgba(100,116,139,0.4)",
                line=dict(color="#334155", width=2),
                name="Outer",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=r_in * np.cos(theta),
                y=r_in * np.sin(theta),
                fill="toself",
                fillcolor="white",
                line=dict(color="#ef4444", width=2, dash="dash"),
                name="Hollow Core",
            )
        )

    elif s.shape == "Curb & Gutter Barrier":
        cd = s.curb_depth_in / 12.0
        ch = s.curb_height_in / 12.0
        gw = s.gutter_width_in / 12.0
        ft = s.flag_thickness_in / 12.0
        x = [0, cd + gw, cd + gw, cd, cd, 0, 0]
        y = [0, 0, ft, ft, ft + ch, ft + ch, 0]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                fill="toself",
                fillcolor="rgba(100,116,139,0.4)",
                line=dict(color="#334155", width=2),
                name="Profile",
                showlegend=False,
            )
        )

    elif s.shape == "Stairs":
        run = s.run_in / 12.0
        rise = s.rise_in / 12.0
        plat = s.platform_depth_in / 12.0
        x = [0.0]
        y = [0.0]
        for i in range(s.num_steps):
            x.extend([i * run, (i + 1) * run])
            y.extend([(i + 1) * rise, (i + 1) * rise])
        total_x = s.num_steps * run + plat
        total_y = s.num_steps * rise
        x.extend([total_x, total_x, 0.0])
        y.extend([total_y, 0.0, 0.0])
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                fill="toself",
                fillcolor="rgba(100,116,139,0.4)",
                line=dict(color="#334155", width=2),
                name="Side Profile",
                showlegend=False,
            )
        )


def _add_3d_trace(fig: go.Figure, s: ConcreteSection):
    if s.shape == "Rectangular Slab / Footing":
        l, w, h = s.length_ft, s.width_ft, s.thickness_in / 12.0
        fig.add_trace(
            go.Mesh3d(
                x=[0, l, l, 0, 0, l, l, 0],
                y=[0, 0, w, w, 0, 0, w, w],
                z=[0, 0, 0, 0, h, h, h, h],
                i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
                j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
                k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
                color="#64748b",
                opacity=0.75,
            )
        )

    elif s.shape in ("Hole, Column & Round Footing", "Circular Slab", "Tube / Hollow Column"):
        r_out = ((s.outer_diameter_in if "Tube" in s.shape else s.diameter_in) / 12.0) / 2.0
        h = s.depth_ft if "Slab" not in s.shape else (s.thickness_in / 12.0)
        theta = np.linspace(0, 2 * np.pi, 36)
        z = np.linspace(0, h, 2)
        theta_grid, z_grid = np.meshgrid(theta, z)

        # Outer wall
        fig.add_trace(
            go.Surface(
                x=r_out * np.cos(theta_grid),
                y=r_out * np.sin(theta_grid),
                z=z_grid,
                colorscale=[[0, "#64748b"], [1, "#94a3b8"]],
                showscale=False,
                opacity=0.8,
            )
        )
        # Top & bottom outer rings
        for z_cap in (0.0, h):
            fig.add_trace(
                go.Scatter3d(
                    x=r_out * np.cos(theta),
                    y=r_out * np.sin(theta),
                    z=[z_cap] * len(theta),
                    mode="lines",
                    line=dict(color="#334155", width=3),
                    showlegend=False,
                )
            )

        # Render inner hollow core if Tube
        if "Tube" in s.shape and s.inner_diameter_in > 0:
            r_in = (s.inner_diameter_in / 12.0) / 2.0
            fig.add_trace(
                go.Surface(
                    x=r_in * np.cos(theta_grid),
                    y=r_in * np.sin(theta_grid),
                    z=z_grid,
                    colorscale=[[0, "#ef4444"], [1, "#f87171"]],
                    showscale=False,
                    opacity=0.65,
                )
            )
            for z_cap in (0.0, h):
                fig.add_trace(
                    go.Scatter3d(
                        x=r_in * np.cos(theta),
                        y=r_in * np.sin(theta),
                        z=[z_cap] * len(theta),
                        mode="lines",
                        line=dict(color="#ef4444", width=3),
                        showlegend=False,
                    )
                )

    elif s.shape == "Curb & Gutter Barrier":
        l = s.length_ft
        cd, ch = s.curb_depth_in / 12.0, s.curb_height_in / 12.0
        gw, ft = s.gutter_width_in / 12.0, s.flag_thickness_in / 12.0
        px = [0.0, cd + gw, cd + gw, cd, cd, 0.0]
        pz = [0.0, 0.0, ft, ft, ft + ch, ft + ch]
        closed_px = px + [px[0]]
        closed_pz = pz + [pz[0]]
        for y_val in [0.0, l]:
            fig.add_trace(
                go.Scatter3d(
                    x=closed_px,
                    y=[y_val] * len(closed_px),
                    z=closed_pz,
                    mode="lines",
                    line=dict(color="#334155", width=5),
                    showlegend=False,
                )
            )
        for x_v, z_v in zip(px, pz):
            fig.add_trace(
                go.Scatter3d(
                    x=[x_v, x_v],
                    y=[0.0, l],
                    z=[z_v, z_v],
                    mode="lines",
                    line=dict(color="#475569", width=4),
                    showlegend=False,
                )
            )

    elif s.shape == "Stairs":
        w = s.width_ft
        run, rise = s.run_in / 12.0, s.rise_in / 12.0
        plat = s.platform_depth_in / 12.0
        px = [0.0]
        pz = [0.0]
        for i in range(s.num_steps):
            px.extend([i * run, (i + 1) * run])
            pz.extend([(i + 1) * rise, (i + 1) * rise])
        px.extend([s.num_steps * run + plat, s.num_steps * run + plat])
        pz.extend([s.num_steps * rise, 0.0])
        closed_px = px + [px[0]]
        closed_pz = pz + [pz[0]]
        for y_val in [0.0, w]:
            fig.add_trace(
                go.Scatter3d(
                    x=closed_px,
                    y=[y_val] * len(closed_px),
                    z=closed_pz,
                    mode="lines",
                    line=dict(color="#334155", width=5),
                    showlegend=False,
                )
            )
        for x_v, z_v in zip(px, pz):
            fig.add_trace(
                go.Scatter3d(
                    x=[x_v, x_v],
                    y=[0.0, w],
                    z=[z_v, z_v],
                    mode="lines",
                    line=dict(color="#475569", width=4),
                    showlegend=False,
                )
            )