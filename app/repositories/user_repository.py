from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:

    def get_by_whatsapp_number(
        self,
        db: Session,
        whatsapp_number: str
    ):

        return (
            db.query(User)
            .filter(
                User.whatsapp_number
                == whatsapp_number
            )
            .first()
        )

    def create_user(
        self,
        db: Session,
        whatsapp_number: str,
        full_name: str = None
    ):

        user = User(

            whatsapp_number=
            whatsapp_number,

            full_name=
            full_name
        )

        db.add(user)

        db.commit()

        db.refresh(user)

        return user


user_repository = UserRepository()