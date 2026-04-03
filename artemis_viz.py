import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

BG_COLOR   = "#0a0a1a"
EARTH_KM   = 384_400


def _pos_ratio(dist_earth_km: float) -> float:
    ratio = dist_earth_km / EARTH_KM
    return max(0.03, min(0.97, ratio))


def generate_position_map(data: dict) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Stars ────────────────────────────────────────────────────────────────
    rng = np.random.default_rng(42)
    sx  = rng.uniform(0, 1, 300)
    sy  = rng.uniform(0, 1, 300)
    ss  = rng.uniform(0.3, 1.5, 300)
    sa  = rng.uniform(0.3, 0.6, 300)
    sc  = rng.choice(["white", "#cce6ff", "#e0f0ff"], 300)
    ax.scatter(sx, sy, s=ss, c=sc, alpha=sa, zorder=1)

    # ── Earth ────────────────────────────────────────────────────────────────
    ex, ey = 0.12, 0.50
    glow_e = plt.Circle((ex, ey), 0.068, color="#2a9d5c", alpha=0.25, transform=ax.transData, zorder=2)
    body_e = plt.Circle((ex, ey), 0.055, color="#1a6b3c", zorder=3)
    ax.add_patch(glow_e)
    ax.add_patch(body_e)
    ax.text(ex, ey - 0.095, "🌍 Земля", color="white", fontsize=9,
            ha="center", va="top", zorder=4)

    # ── Moon ─────────────────────────────────────────────────────────────────
    mx, my = 0.88, 0.50
    glow_m = plt.Circle((mx, my), 0.052, color="#d0d0d0", alpha=0.20, transform=ax.transData, zorder=2)
    body_m = plt.Circle((mx, my), 0.040, color="#b0b0b0", zorder=3)
    ax.add_patch(glow_m)
    ax.add_patch(body_m)
    ax.text(mx, my - 0.080, "🌕 Луна", color="white", fontsize=9,
            ha="center", va="top", zorder=4)

    # ── Trajectory arc ───────────────────────────────────────────────────────
    t_pts = np.linspace(0, 1, 200)
    traj_x = ex + t_pts * (mx - ex)
    # slight upward bow
    traj_y = ey + 0.08 * np.sin(np.pi * t_pts)
    ax.plot(traj_x, traj_y, color="white", alpha=0.15, linewidth=1.5,
            linestyle="--", zorder=2)

    # ── Spacecraft position ───────────────────────────────────────────────────
    ratio = _pos_ratio(data.get("dist_earth_km", 0.0))
    sc_x = ex + ratio * (mx - ex)
    sc_y = ey + 0.08 * np.sin(np.pi * ratio)

    # Pulsing glow
    for sz, al in [(500, 0.10), (350, 0.20), (200, 0.40)]:
        ax.scatter([sc_x], [sc_y], s=sz, c="#FFD700", alpha=al, zorder=5)
    ax.scatter([sc_x], [sc_y], s=120, c="#FFD700", marker="^", zorder=6)
    ax.text(sc_x, sc_y + 0.07, "🛸 Orion", color="#FFD700", fontsize=10,
            ha="center", va="bottom", fontweight="bold", zorder=7)

    # ── Distance labels ───────────────────────────────────────────────────────
    de = data.get("dist_earth_km", 0.0)
    dm = data.get("dist_moon_km", EARTH_KM)
    label = f"← {de:,.0f} км  |  {dm:,.0f} км →"
    ax.text(0.50, ey - 0.18, label, color="white", fontsize=9,
            ha="center", va="center", alpha=0.80, zorder=4)

    # ── Pre-launch countdown overlay ──────────────────────────────────────────
    if not data.get("is_active", False) and data.get("countdown_str"):
        msg = f"Следующий запуск: {data['countdown_str']}"
        ax.text(0.50, 0.50, msg, color="#FFD700", fontsize=13,
                ha="center", va="center", fontweight="bold",
                alpha=0.75, zorder=8,
                bbox=dict(facecolor=BG_COLOR, edgecolor="#FFD700",
                          alpha=0.5, boxstyle="round,pad=0.4"))
        # small rocket near Earth
        ax.text(ex + 0.04, ey + 0.11, "🚀", fontsize=14, ha="center",
                va="bottom", zorder=8)

    # ── Title bar ────────────────────────────────────────────────────────────
    phase = data.get("phase", "")
    ax.text(0.01, 0.97, "ARTEMIS II — ПОЗИЦИЯ КОРАБЛЯ",
            color="white", fontsize=13, fontweight="bold",
            ha="left", va="top", transform=ax.transAxes, zorder=9)
    ax.text(0.99, 0.97, phase,
            color="white", fontsize=10,
            ha="right", va="top", transform=ax.transAxes, zorder=9)

    # ── Bottom status bar ────────────────────────────────────────────────────
    vel   = data.get("velocity_km_s", 0.0)
    pct   = data.get("progress_pct", 5.0)
    bar   = _progress_bar(pct)
    etime = data.get("elapsed_str", "0д 0ч 0м")

    ax.text(0.01, 0.03, f"⚡ {vel:.1f} км/с",
            color="#aaaaaa", fontsize=9, family="monospace",
            ha="left", va="bottom", transform=ax.transAxes, zorder=9)
    ax.text(0.50, 0.03, f"{bar} {pct:.0f}%",
            color="#aaaaaa", fontsize=9, family="monospace",
            ha="center", va="bottom", transform=ax.transAxes, zorder=9)
    ax.text(0.99, 0.03, f"🕐 {etime}",
            color="#aaaaaa", fontsize=9, family="monospace",
            ha="right", va="bottom", transform=ax.transAxes, zorder=9)

    # ── Save ─────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight",
                facecolor=BG_COLOR, dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf


def _progress_bar(percent: float, length: int = 16) -> str:
    filled = round(length * percent / 100)
    return "▓" * filled + "░" * (length - filled)
