from sqlalchemy.orm import Session
from app.models.post import Post


class PostRepository:

    def create(
        self,
        db: Session,
        user_id: int,
        prompt: str,
        caption: str,
        image_url: str,
    ) -> Post:
        post = Post(
            user_id=user_id,
            prompt=prompt,
            caption=caption,
            image_url=image_url,
            status="draft",
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return post

    def get_by_id(self, db: Session, post_id: int):
        return db.query(Post).filter(Post.id == post_id).first()

    def update_status(self, db: Session, post_id: int, status: str):
        post = self.get_by_id(db, post_id)
        if post:
            post.status = status
            db.commit()
            db.refresh(post)
        return post


post_repository = PostRepository()