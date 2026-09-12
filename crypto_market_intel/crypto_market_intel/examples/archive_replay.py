from __future__ import annotations

from pathlib import Path

from crypto_market_intel.storage import LocalArchive


def main() -> None:
    archive = LocalArchive(Path("./data"))
    try:
        for row in archive.replay("features", "BTCUSDT"):
            print(row)
    finally:
        archive.close()


if __name__ == "__main__":
    main()
