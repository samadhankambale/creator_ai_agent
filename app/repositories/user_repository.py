from app.models.user import (
    User
)


class UserRepository:

    def get_user_by_whatsapp(
        self,
        db,
        whatsapp_number
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
        db,
        whatsapp_number
    ):

        user = User(

            whatsapp_number=
            whatsapp_number
        )

        db.add(user)

        db.commit()

        db.refresh(user)

        return user


user_repository = (
    UserRepository()
)