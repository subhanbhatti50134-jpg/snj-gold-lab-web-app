from getpass import getpass

from sqlalchemy import select

from app.core.auth import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main():
    with SessionLocal() as db:
        existing_admins = db.execute(
            select(User.id, User.username, User.active)
            .where(User.role == "admin")
        ).all()

        if existing_admins:
            print("STOP: An admin account already exists.")
            print("No changes were made.")
            return

        username = input("New admin username (min 3 characters): ").strip()

        if len(username) < 3 or len(username) > 80:
            print("ERROR: Username must be 3-80 characters.")
            return

        if db.scalar(
            select(User.id).where(User.username == username)
        ) is not None:
            print("ERROR: This username already exists.")
            return

        password = getpass("New admin password (min 12 characters): ")
        confirmation = getpass("Confirm admin password: ")

        if len(password) < 12 or len(password) > 256:
            print("ERROR: Password must be 12-256 characters.")
            return

        if password != confirmation:
            print("ERROR: Passwords do not match.")
            return

        admin = User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("\nAdmin account created successfully.")
        print(f"User ID: {admin.id}")
        print(f"Username: {admin.username}")
        print(f"Role: {admin.role}")
        print("Password was stored as a secure hash.")


if __name__ == "__main__":
    main()
