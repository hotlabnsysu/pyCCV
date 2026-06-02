from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisplaySettings:
    plot_now: int
    grid_skip: int
    quiver_factor: float
    vector_color: str


def choose_vectors(results, display_settings: DisplaySettings):
    if not results:
        return None, None

    mode_idx = display_settings.plot_now

    if mode_idx == 1:
        u, v = results.get("u_raw"), results.get("v_raw")
    elif mode_idx == 2:
        u = results.get("u_interp") if results.get("u_interp") is not None else results.get("u_filt")
        v = results.get("v_interp") if results.get("v_interp") is not None else results.get("v_filt")
    elif mode_idx == 3:
        u, v = results.get("u_smooth"), results.get("v_smooth")
    else:
        u, v = None, None

    if u is None:
        u = results.get("u_final")
    if v is None:
        v = results.get("v_final")
    return u, v


class PlotPresenter:
    def redraw(self, axes, figure, canvas, image, vectors, display_settings: DisplaySettings):
        if display_settings.plot_now == 0:
            axes.clear()
            axes.set_facecolor("black")
            axes.set_xticks([])
            axes.set_yticks([])
            figure.patch.set_facecolor("black")
            canvas.draw()
            return

        figure.patch.set_facecolor("#2b2b2b")
        axes.set_facecolor("#1a1a1a")

        if image is None:
            return

        axes.clear()
        cmap = "gray" if len(image.shape) == 2 else None
        axes.imshow(image, cmap=cmap)

        if vectors:
            x, y, results = vectors
            u, v = choose_vectors(results, display_settings)
            if u is not None and v is not None:
                self._plot_vectors(axes, x, y, u, v, display_settings)

        axes.set_xlim(0, image.shape[1])
        axes.set_ylim(image.shape[0], 0)
        axes.set_axis_off()
        try:
            figure.tight_layout(pad=0)
        except Exception:
            pass
        canvas.draw()

    def _plot_vectors(self, axes, x, y, u, v, display_settings: DisplaySettings):
        skip = max(1, int(display_settings.grid_skip))
        scale = max(0.1, float(display_settings.quiver_factor))

        axes.quiver(
            x[::skip, ::skip],
            y[::skip, ::skip],
            u[::skip, ::skip],
            v[::skip, ::skip],
            color=display_settings.vector_color,
            angles="xy",
            scale_units="xy",
            scale=1.0 / scale,
            pivot="mid",
        )
