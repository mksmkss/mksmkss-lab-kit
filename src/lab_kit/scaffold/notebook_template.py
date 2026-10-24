import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import plotly.graph_objects as go
    from tqdm import tqdm

    from lab_kit import (
        data_path,
        get_device,
        load_data_with_metadata,
        project_root,
        results_path,
        save_data_with_metadata,
    )
    from lab_kit.viz import apply_jp_font, save_figure

    print(f"プロジェクトルート: {project_root()}")
    print(f"デバイス: {get_device()}")
    return (
        apply_jp_font,
        data_path,
        go,
        load_data_with_metadata,
        mo,
        pd,
        results_path,
        save_data_with_metadata,
        save_figure,
        tqdm,
    )


@app.cell
def _():
    # このノートブックを作ったスクリプト名。save_data_with_metadata の created_by に渡す
    created_by = "notebooks/_template.py"
    return (created_by,)


@app.cell
def _(created_by, data_path, pd, save_data_with_metadata):
    # 例: データを保存するときは、必ず元データと処理内容を書く
    # df = pd.read_csv(data_path("raw", "input.csv"))
    # save_data_with_metadata(
    #     df,
    #     data_path("interim", "cleaned.csv"),
    #     created_by=created_by,
    #     source_info=data_path("raw", "input.csv"),
    #     processing_steps=["欠損値の除去"],
    #     config={"drop_na": True},
    #     format="csv",
    # )
    return


if __name__ == "__main__":
    app.run()
