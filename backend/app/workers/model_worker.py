"""Model worker entrypoint — owned by Vritika; stub so Compose can start."""

from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("model_worker")


def main() -> None:
    log.info("model_worker stub idle (Vritika owns full implementation)")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
