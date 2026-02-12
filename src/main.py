import argparse
import os
from datetime import date


def cmd_postprocess(args):
    from src.scrapper.postprocess import run_postprocess
    run_postprocess(args.db_path, date.fromisoformat(args.date), args.output_dir)


def cmd_scrapper(args):
    from src.scrapper.database import archive_db
    from src.scrapper.scrapper import Scrapper
    db_path = os.path.join(args.data_dir, "current.sql")
    if args.archive:
        archive_db(db_path)
    Scrapper(
        db_path=db_path,
        poll_interval=args.interval,
        status_interval=args.status_interval,
    ).run()


def main():
    parser = argparse.ArgumentParser(description="TIPE-BSSR")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp = subparsers.add_parser("scrapper", help="Lancer le scrapper")
    sp.add_argument("--interval", type=int, default=5,
                    help="Intervalle polling /bikes en secondes (défaut: 5)")
    sp.add_argument("--status-interval", type=int, default=300,
                    help="Intervalle recalage /station_status en secondes (défaut: 300)")
    sp.add_argument("--data-dir", type=str, default="data",
                    help="Répertoire des données (défaut: data)")
    sp.add_argument("--no-archive", dest="archive", action="store_false",
                    help="Ne pas archiver la session précédente")
    sp.set_defaults(func=cmd_scrapper)

    sp_pp = subparsers.add_parser("postprocess", help="Nettoyage données pour un jour")
    sp_pp.add_argument("db_path")
    sp_pp.add_argument("--date", required=True)
    sp_pp.add_argument("--output-dir", default=None)
    sp_pp.set_defaults(func=cmd_postprocess)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
