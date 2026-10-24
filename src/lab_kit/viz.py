"""
plotly で日本語が文字化けしないようにする設定と、図の保存。

使い方:
    from lab_kit.viz import apply_jp_font, save_figure
    fig = apply_jp_font(fig)
    save_figure(fig, results_path("exp1", "figures", "alpha_sweep"))
"""

import os
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio

# Mac / Windows / Linux のどれかで日本語フォントに当たるように並べる
JP_FONT_FAMILY = (
    "Hiragino Sans, Hiragino Kaku Gothic ProN, Yu Gothic, Meiryo, "
    "Noto Sans CJK JP, IPAexGothic, sans-serif"
)
TEMPLATE_NAME = "lab_jp"


def register_template(set_default: bool = True) -> str:
    """日本語フォント入りの plotly テンプレート `lab_jp` を登録する。"""
    template = go.layout.Template(layout=dict(font=dict(family=JP_FONT_FAMILY)))
    pio.templates[TEMPLATE_NAME] = template
    if set_default:
        pio.templates.default = f"plotly+{TEMPLATE_NAME}"
    return TEMPLATE_NAME


def apply_jp_font(fig: go.Figure) -> go.Figure:
    """図のフォントを日本語対応にする（図を返すので、そのまま続けて使える）。"""
    fig.update_layout(font=dict(family=JP_FONT_FAMILY))
    return fig


def save_figure(
    fig: go.Figure,
    path,
    width: int = 1200,
    height: int = 700,
    scale: int = 2,
    html: bool = False,
) -> Path:
    """
    図を PNG（必要なら HTML も）で保存し、PNG のパスを返す。

    Parameters:
    -----------
    path : str or Path
        拡張子なしでも、`.png` つきでもよい。フォルダがなければ作る。
    html : bool
        True なら同名の `.html` も保存する（確認用。.gitignore 対象にすること）。

    PNG の保存には kaleido と Google Chrome が必要（`uv add kaleido`、Chrome は `uv run plotly_get_chrome` でも入る）。
    """
    png_path = Path(os.fspath(path))
    if png_path.suffix.lower() != ".png":
        png_path = png_path.with_suffix(".png")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    apply_jp_font(fig)
    try:
        fig.write_image(str(png_path), width=width, height=height, scale=scale)
    except (ValueError, RuntimeError) as e:
        raise RuntimeError(
            "PNG の保存に失敗しました。kaleido(`uv add kaleido`)と Google Chrome が必要です。"
            f"Chrome は `uv run plotly_get_chrome` で入ります。元のエラー: {e}"
        ) from e

    if html:
        fig.write_html(str(png_path.with_suffix(".html")))
    return png_path
