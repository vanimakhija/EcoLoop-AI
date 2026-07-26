"""Render the EcoLoop-AI presentation architecture as SVG and PNG."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "docs"

NAVY = "#071525"
TEXT = "#E8F1F8"
MUTED = "#A6B8C7"
LINE = "#24435F"
SIM = "#38BDF8"
DATA = "#2DD4BF"
AI = "#A78BFA"
CONTROL = "#F59E0B"
SAFE = "#34D399"
HUMAN = "#F472B6"


def box(ax, x, y, w, h, title, subtitle, accent, fill="#0D2238"):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.35, edgecolor=accent, facecolor=fill,
    )
    ax.add_patch(patch)
    ax.add_patch(FancyBboxPatch((x, y + h - 0.025), w, 0.025, boxstyle="round,pad=0.0,rounding_size=0.01",
                                linewidth=0, facecolor=accent))
    ax.text(x + w / 2, y + h * 0.61, title, ha="center", va="center", color=TEXT, fontsize=10.2, fontweight="bold")
    ax.text(x + w / 2, y + h * 0.33, subtitle, ha="center", va="center", color=MUTED, fontsize=7.3, wrap=True)
    return (x, y, w, h)


def arrow(ax, source, target, color=LINE, text=None, curve=0.0):
    sx, sy, sw, sh = source
    tx, ty, tw, th = target
    start = (sx + sw / 2, sy)
    end = (tx + tw / 2, ty + th)
    patch = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12, linewidth=1.25,
                            color=color, connectionstyle=f"arc3,rad={curve}")
    ax.add_patch(patch)
    if text:
        ax.text((start[0] + end[0]) / 2 + curve * .08, (start[1] + end[1]) / 2, text,
                color=MUTED, fontsize=6.6, ha="center", va="center", bbox={"facecolor": NAVY, "edgecolor": "none", "pad": 1.8})


def upward_arrow(ax, source, target, color=LINE, text=None, curve=0.0):
    sx, sy, sw, sh = source
    tx, ty, tw, th = target
    start = (sx + sw / 2, sy + sh)
    end = (tx + tw / 2, ty)
    patch = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12, linewidth=1.25,
                            color=color, connectionstyle=f"arc3,rad={curve}")
    ax.add_patch(patch)
    if text:
        ax.text((start[0] + end[0]) / 2 + curve * .08, (start[1] + end[1]) / 2, text,
                color=MUTED, fontsize=6.6, ha="center", va="center", bbox={"facecolor": NAVY, "edgecolor": "none", "pad": 1.8})


def lane(ax, y, height, label, color):
    ax.add_patch(FancyBboxPatch((0.028, y), 0.944, height, boxstyle="round,pad=0.006,rounding_size=0.01",
                                linewidth=0.8, edgecolor=color, facecolor="#091C2E"))
    ax.text(0.042, y + height / 2, label.upper(), rotation=90, ha="center", va="center",
            color=color, fontsize=7.2, fontweight="bold")


def render():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=180)
    fig.patch.set_facecolor(NAVY)
    ax.set_facecolor(NAVY)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.055, 0.955, "EcoLoop-AI", color=TEXT, fontsize=23, fontweight="bold", va="center")
    ax.text(0.055, 0.925, "Governed smart-building optimisation architecture", color=MUTED, fontsize=10, va="center")
    ax.text(0.945, 0.952, "DIGITAL TWIN  •  EXPLAINABLE AI  •  SAFETY GOVERNANCE", color=SIM, fontsize=7.8, ha="right", va="center", fontweight="bold")
    ax.plot([0.04, 0.96], [0.902, 0.902], color=LINE, lw=1)

    lane(ax, .795, .078, "Simulation", SIM)
    lane(ax, .675, .090, "Integration", DATA)
    lane(ax, .440, .205, "AI orchestration", AI)
    lane(ax, .275, .125, "Control governance", CONTROL)
    lane(ax, .065, .175, "Operations", HUMAN)

    twin = box(ax, .12, .810, .27, .046, "EnergyPlus Digital Twin", "DOE medium office • thermal and energy simulation", SIM)
    reader = box(ax, .56, .810, .28, .046, "State Reader", "Zone temperature • facility electricity [J] • weather", SIM)
    mcp = box(ax, .28, .700, .45, .046, "MCP Server", "Read state • record audit • Safety-gated HVAC command • run simulation", DATA)
    graph = box(ax, .29, .590, .42, .042, "LangGraph Orchestrator", "Validates data before advisory agents execute", AI)

    agent_width = .142
    agent_y = .490
    agents = [
        box(ax, .105, agent_y, agent_width, .060, "Comfort Agent", "Thermal comfort target", AI),
        box(ax, .270, agent_y, agent_width, .060, "Energy Agent", "Tariff-aware strategy", AI),
        box(ax, .435, agent_y, agent_width, .060, "Weather Forecast", "Outdoor conditions", AI),
        box(ax, .600, agent_y, agent_width, .060, "Carbon Impact", "Estimated CO₂ impact", AI),
        box(ax, .765, agent_y, agent_width, .060, "Occupancy Agent", "Pre-conditioning forecast", AI),
    ]
    coordinator = box(ax, .33, .345, .34, .045, "HVAC Coordinator", "Explains why one recommendation is selected over the others", CONTROL)
    supervisor = box(ax, .33, .286, .34, .045, "Safety Supervisor", "Deterministic: validity • bounds • rate limit • audit", SAFE, "#0B2B32")
    controller = box(ax, .33, .215, .34, .045, "HVAC Control Layer", "Applies only a Safety Supervisor-approved setpoint", CONTROL)

    dashboard = box(ax, .14, .117, .24, .050, "Operations Dashboard", "Energy • comfort • explainability • monitoring", HUMAN)
    manager = box(ax, .45, .117, .20, .050, "Facility Manager", "Accept AI or submit a reasoned override", HUMAN)
    manual = box(ax, .72, .117, .18, .050, "Manual Override", "Request only; never bypasses safety", HUMAN)

    arrow(ax, twin, reader, SIM, "Simulation output")
    arrow(ax, reader, mcp, DATA)
    arrow(ax, mcp, graph, DATA, "Validated building state")
    for agent in agents:
        arrow(ax, graph, agent, AI)
        arrow(ax, agent, coordinator, AI)
    arrow(ax, coordinator, supervisor, CONTROL, "Advisory setpoint")
    arrow(ax, supervisor, controller, SAFE, "Approved value only")
    arrow(ax, controller, twin, CONTROL, "Setpoint + next simulation")
    upward_arrow(ax, dashboard, supervisor, HUMAN, "Audit visibility", curve=-.13)
    arrow(ax, manager, manual, HUMAN)
    upward_arrow(ax, manual, supervisor, HUMAN, "Reasoned request", curve=.22)

    ax.text(.5, .028, "Industrial control principle: AI recommends; deterministic safety authorises; the facility manager remains accountable.",
            ha="center", va="center", color=MUTED, fontsize=8.5)
    OUTPUT.mkdir(exist_ok=True)
    fig.savefig(OUTPUT / "architecture.png", dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(OUTPUT / "architecture.svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    render()
