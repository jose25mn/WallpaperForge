"""Entry point: python -m wallpaperforge [comando] [opções]"""

from __future__ import annotations

import argparse
import sys

from wallpaperforge.utils.log import setup_logging


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallpaperforge",
        description="Coleta, processa e exporta wallpapers 4K para múltiplos monitores.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python -m wallpaperforge monitors\n"
            "  python -m wallpaperforge scrape --query 'Violet Evergarden' --limit 200\n"
            "  python -m wallpaperforge all --url https://wall.alphacoders.com/... --no-ui\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", metavar="COMANDO")

    # monitors
    sub.add_parser("monitors", help="Lista os monitores detectados e sai.")

    # scrape
    s = sub.add_parser("scrape", help="Coleta imagens da internet.")
    s.add_argument("--query", "-q", metavar="TEXTO",  help="Palavra-chave de busca.")
    s.add_argument("--url",   "-u", metavar="URL",    help="URL de board/tag/galeria.")
    s.add_argument("--limit", "-n", metavar="N", type=int, default=300,
                   help="Número máximo de imagens (padrão: 300).")

    # filter
    sub.add_parser("filter", help="Aplica filtros automáticos às imagens coletadas.")

    # select (UI de seleção)
    sel = sub.add_parser("select", help="Abre a interface de seleção de imagens.")
    sel.add_argument("--no-ui", action="store_true",
                     help="Modo headless: processa tudo sem interface gráfica.")

    # upscale
    up = sub.add_parser("upscale", help="Faz upscale das imagens selecionadas.")
    up.add_argument("--model", default=None, metavar="MODELO",
                    help="Modelo Real-ESRGAN (padrão: settings.toml).")

    # crop
    sub.add_parser("crop", help="Corta as imagens para cada monitor.")

    # web (interface React + servidor FastAPI)
    w = sub.add_parser("web", help="Inicia a interface web React (FastAPI + browser).")
    w.add_argument("--host",       default="127.0.0.1", help="Endereço do servidor (padrão: 127.0.0.1).")
    w.add_argument("--port", "-p", default=8000, type=int, help="Porta (padrão: 8000).")
    w.add_argument("--no-browser", action="store_true", help="Não abre o browser automaticamente.")

    # all (pipeline completo)
    a = sub.add_parser("all", help="Executa o pipeline completo de ponta a ponta.")
    a.add_argument("--query", "-q", metavar="TEXTO")
    a.add_argument("--url",   "-u", metavar="URL")
    a.add_argument("--limit", "-n", metavar="N", type=int, default=300)
    a.add_argument("--no-ui", action="store_true")
    a.add_argument("--model", default=None, metavar="MODELO")

    return parser


def main() -> None:
    log_file = setup_logging()
    parser   = _build_parser()
    args     = parser.parse_args()

    if args.command == "monitors":
        from wallpaperforge.monitors import cmd_list_monitors
        cmd_list_monitors()

    elif args.command == "web":
        from wallpaperforge.server import start_server
        start_server(host=args.host, port=args.port, open_browser=not args.no_browser)

    elif args.command == "scrape":
        from wallpaperforge.scraper import cmd_scrape
        cmd_scrape(query=args.query, url=args.url, limit=args.limit)

    elif args.command == "filter":
        from wallpaperforge.filter import cmd_filter
        cmd_filter()

    elif args.command == "select":
        from wallpaperforge.ui import cmd_select
        cmd_select(no_ui=args.no_ui)

    elif args.command == "upscale":
        from wallpaperforge.upscale import cmd_upscale
        cmd_upscale(model=args.model)

    elif args.command == "crop":
        from wallpaperforge.crop import cmd_crop
        cmd_crop()

    elif args.command == "all":
        _run_pipeline(args)

    else:
        parser.print_help()
        sys.exit(0)


def _run_pipeline(args: argparse.Namespace) -> None:
    from wallpaperforge.scraper import cmd_scrape
    from wallpaperforge.filter  import cmd_filter
    from wallpaperforge.ui      import cmd_select
    from wallpaperforge.upscale import cmd_upscale
    from wallpaperforge.crop    import cmd_crop

    cmd_scrape(query=args.query, url=args.url, limit=args.limit)
    cmd_filter()
    cmd_select(no_ui=args.no_ui)
    cmd_upscale(model=args.model)
    cmd_crop()


if __name__ == "__main__":
    main()
