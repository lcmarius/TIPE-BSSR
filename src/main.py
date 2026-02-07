import argparse
import os

from src.scrapper.database import archive_db
from src.scrapper.scrapper import Scrapper


def cmd_scrapper(args):
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
