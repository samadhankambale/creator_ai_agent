from sqlalchemy.orm import Session

from app.models.post import Post


class PostRepository:

    def create_post(
        self,
        db: Session,
        user_id: int,
        prompt: str,
        caption: str,
        image_url: str,
        status: str = "draft"
    ):

        post = Post(
            user_id=user_id,
            prompt=prompt,
            caption=caption,
            image_url=image_url,
            status=status
        )

        db.add(post)

        db.commit()

        db.refresh(post)

        return post

    def get_post_by_id(
        self,
        db: Session,
        post_id: int
    ):

        return (
            db.query(Post)
            .filter(Post.id == post_id)
            .first()
        )

    def update_post_status(
        self,
        db: Session,
        post_id: int,
        status: str
    ):

        post = (
            db.query(Post)
            .filter(Post.id == post_id)
            .first()
        )

        if not post:
            return None

        post.status = status

        db.commit()

        db.refresh(post)

        return post


post_repository = PostRepository()