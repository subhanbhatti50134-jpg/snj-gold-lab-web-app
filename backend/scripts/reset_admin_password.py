from getpass import getpass

from sqlalchemy import select

from app.core.auth import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main():
    username = "snjjewellers"

    password = getpass("Enter new admin password: ")
    confirmation = getpass("Confirm new admin password: ")

    if len(password) < 12 or len(password) > 256:
        print("ERROR: Password must be 12-256 characters.")
        return

    if password != confirmation:
        print("ERROR: Passwords do not match.")
        return

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))

        if user is None:
            print("ERROR: Admin account not found.")
            return

        if user.role != "admin":
            print("ERROR: This account is not an admin.")
            return

        user.password_hash = hash_password(password)
        db.commit()

    print(f"Password updated for '{username}'.")


if __name__ == "__main__":
    main()
