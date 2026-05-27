import uuid
from sqlalchemy.orm import Session
from app.models.user import User


class UserService:

    def get_or_create(self, db: Session, whatsapp_number: str) -> User:
        user = db.query(User).filter(User.number == whatsapp_number).first()
        if not user:
            user = User(number=whatsapp_number)
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"USER CREATED: {user.id} | {whatsapp_number}")
        return user

    def get_by_number(self, db: Session, whatsapp_number: str) -> User | None:
        return db.query(User).filter(User.number == whatsapp_number).first()


user_service = UserService()