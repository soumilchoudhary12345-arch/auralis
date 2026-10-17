"""Auralis entry point."""

import sys


def main():
    from .app import Auralis

    app = Auralis()
    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()


if __name__ == "__main__":
    sys.exit(main())
