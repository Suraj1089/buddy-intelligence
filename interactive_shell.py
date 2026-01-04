import os
import sys

# Ensure backend dir is in path
sys.path.append(os.getcwd())

from sqlmodel import Session, select

from app.booking_models import BookingDB
from app.core.db import engine
from app.models import User


def init():
    print("\n--- Buddy Intelligence Interactive Shell ---")
    print("Database connection established.")
    print("\nAvailable objects:")
    print("  - session: Active SQLModel Session")
    print("  - select: SQLModel select function")
    print(
        "  - User, BookingDB, ProviderDB, ServiceDB, AssignmentQueueDB: Database Models"
    )
    print("  - engine: Database Engine")

    # Check basic stats
    try:
        user_count = session.exec(select(User)).all()
        booking_count = session.exec(select(BookingDB)).all()
        print(f"\nStats: {len(user_count)} Users, {len(booking_count)} Bookings")
    except Exception as e:
        print(f"\nWarning: Could not fetch stats ({e})")

    print("\nUsage Example: user = session.exec(select(User)).first()")
    print("--------------------------------------------\n")


if __name__ == "__main__":
    with Session(engine) as session:
        init()

        # Start IPython
        import IPython
        from traitlets.config import Config

        c = Config()
        c.TerminalInteractiveShell.banner1 = ""

        # Pass local variables to the shell
        IPython.start_ipython(argv=[], user_ns=locals(), config=c)
