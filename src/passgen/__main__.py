"""`python -m passgen` запускає вікно; `python -m passgen --cli ...` — консольний режим."""

import sys


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from passgen.cli import main as cli_main

        return cli_main(sys.argv[2:])
    from passgen.gui.app import main as gui_main

    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
