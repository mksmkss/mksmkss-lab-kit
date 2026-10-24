"""計算デバイスの自動選択（Apple Silicon の MPS > CUDA > CPU）。"""


def get_device(preferred: str = "auto") -> str:
    """
    使うデバイス名を返す。

    Parameters:
    -----------
    preferred : str
        "auto"（既定）なら mps > cuda > cpu の順で選ぶ。
        "cpu" / "cuda" / "mps" を渡すと、使えるときだけそれを返し、
        使えなければ警告を出して自動選択に戻る。

    torch が入っていない環境では、常に "cpu" を返す。
    """
    try:
        import torch
    except ImportError:
        return "cpu"

    available = {
        "mps": bool(getattr(torch.backends, "mps", None)) and torch.backends.mps.is_available(),
        "cuda": torch.cuda.is_available(),
        "cpu": True,
    }

    if preferred != "auto":
        if available.get(preferred):
            return preferred
        print(f"警告: デバイス '{preferred}' は使えないため、自動選択します。")

    for name in ("mps", "cuda", "cpu"):
        if available[name]:
            return name
    return "cpu"
