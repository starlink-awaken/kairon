"""kos-indexer command wrapper — delegates to kos.indexer package."""

import sys

from kos.indexer import main as indexer_main


def main() -> None:
    sys.argv[0] = "kos-indexer"
    indexer_main()


if __name__ == "__main__":
    main()
