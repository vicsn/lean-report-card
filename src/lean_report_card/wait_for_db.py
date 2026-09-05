from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from lean_report_card.database import engine, init_db


def main() -> None:
    for attempt in range(60):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            init_db()
            return
        except SQLAlchemyError:
            if attempt == 59:
                raise
            time.sleep(2)


if __name__ == "__main__":
    main()
