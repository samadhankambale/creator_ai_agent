from sqlalchemy.orm import Session
from app.models.user import User


class UserRepository:

    def get_by_whatsapp(self, db: Session, whatsapp_number: str):
        return (
            db.query(User)
            .filter(User.whatsapp_number == whatsapp_number)
            .first()
        )

    # alias — old code used this name
    def get_user_by_whatsapp(self, db: Session, whatsapp_number: str):
        return self.get_by_whatsapp(db, whatsapp_number)

    def create_user(self, db: Session, whatsapp_number: str) -> User:
        user = User(whatsapp_number=whatsapp_number)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_or_create(self, db: Session, whatsapp_number: str) -> User:
        user = self.get_by_whatsapp(db, whatsapp_number)
        if not user:
            user = self.create_user(db, whatsapp_number)
        return user


user_repository = UserRepository()