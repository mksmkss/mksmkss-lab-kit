"""`lab-kit` コマンド。"""

import argparse
import sys
from pathlib import Path

from lab_kit import __version__


def _cmd_init(args) -> int:
    from lab_kit import scaffold

    root = Path(args.dir).resolve()
    report = scaffold.run(root, mode="init", dry_run=args.dry_run, agents=args.agents)
    report.print(args.dry_run)
    print()
    if report.count("conflict"):
        print(
            f"既に別の内容のファイルが {report.count('conflict')} 件ありました。"
            f"上書きはせず、横に *{scaffold.NEW_SUFFIX} を置いています。差分を見て、必要なら取り込んでください。"
        )
    if args.dry_run:
        print("(dry-run のため、何も変更していません)")
    else:
        print("次の手順:")
        print("  1. uv run lab-kit doctor     # 環境の確認")
        print("  2. uv run lab-kit labels     # GitHub にラベルを作る(gh のログインが必要)")
        print("  3. 既存コードの移行は、Claude に「lab-adopt で移行して」と頼む")
    return 0


def _cmd_update(args) -> int:
    from lab_kit import scaffold

    root = Path(args.dir).resolve()
    report = scaffold.run(root, mode="update", dry_run=args.dry_run, agents=args.agents)
    report.print(args.dry_run)
    if report.count("conflict"):
        print(
            f"\n手元で編集されたファイルが {report.count('conflict')} 件あるため、"
            f"上書きせず *{scaffold.NEW_SUFFIX} を置きました。差分を見て、必要なら取り込んでください。"
        )
    if args.dry_run:
        print("\n(dry-run のため、何も変更していません)")
    return 0


def _cmd_labels(args) -> int:
    from lab_kit import labels

    return labels.run(kinds=args.kinds, repo=args.repo, dry_run=args.dry_run)


def _cmd_doctor(args) -> int:
    from lab_kit import doctor

    return doctor.run(Path(args.dir).resolve())


def _cmd_lineage(args) -> int:
    from lab_kit import lineage

    root = Path(args.dir).resolve() if args.dir else None
    lineage.main(root=root, out_dir=args.out, verbose=not args.quiet)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab-kit", description="研究用の共通道具と Skill を、既存リポジトリに入れる"
    )
    parser.add_argument("--version", action="version", version=f"lab-kit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_dir(p, help_text="対象のプロジェクトのルート(既定: いまのフォルダ)"):
        p.add_argument("--dir", default=".", help=help_text)

    p_init = sub.add_parser(
        "init", help="Skill・.gitignore・CLAUDE.md などを入れる(既存ファイルは壊さない)"
    )
    add_dir(p_init)
    p_init.add_argument("--dry-run", action="store_true", help="何もせず、予定だけ表示する")
    p_init.add_argument("--agents", action="store_true", help=".agents/skills/ にもリンクを作る")
    p_init.set_defaults(func=_cmd_init)

    p_update = sub.add_parser(
        "update", help="入れたファイルを最新にする(手元で編集したものは上書きしない)"
    )
    add_dir(p_update)
    p_update.add_argument("--dry-run", action="store_true", help="何もせず、予定だけ表示する")
    p_update.add_argument("--agents", action="store_true", help=".agents/skills/ にもリンクを作る")
    p_update.set_defaults(func=_cmd_update)

    p_labels = sub.add_parser("labels", help="decision-log 用の GitHub ラベルを作る(無いものだけ)")
    p_labels.add_argument(
        "--kinds",
        default=None,
        help="種類ラベルも作る。`default`(experiment,method,data,analysis)か、カンマ区切りの名前",
    )
    p_labels.add_argument(
        "--repo", default=None, help="OWNER/REPO(既定: いまのフォルダのリポジトリ)"
    )
    p_labels.add_argument("--dry-run", action="store_true", help="何もせず、予定だけ表示する")
    p_labels.set_defaults(func=_cmd_labels)

    p_doctor = sub.add_parser("doctor", help="環境を確認する")
    add_dir(p_doctor)
    p_doctor.set_defaults(func=_cmd_doctor)

    p_lineage = sub.add_parser("lineage", help="*_metadata.yaml からデータの系譜図(Mermaid)を作る")
    p_lineage.add_argument(
        "--dir", default=None, help="メタデータを探すルート(既定: プロジェクトルート)"
    )
    p_lineage.add_argument("--out", default=None, help="出力先(既定: <root>/docs/data_lineage)")
    p_lineage.add_argument(
        "--quiet", action="store_true", help="Mermaid のコードを画面に表示しない"
    )
    p_lineage.set_defaults(func=_cmd_lineage)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    code = args.func(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
