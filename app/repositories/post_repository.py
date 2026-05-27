from sqlalchemy.orm import Session
from app.models.user_post import UserPost


class PostRepository:

    def create(
        self,
        db: Session,
        user_id,
        prompt: str,
        caption: str,
        image_url: str,
        extra_image_urls: list = None,
    ) -> UserPost:
        all_urls = [image_url] + (extra_image_urls or [])
        post = UserPost(
            user_id=user_id,
            caption=caption,
            url_list=all_urls,
            status="draft",
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return post

    def get_by_id(self, db: Session, post_id) -> UserPost:
        return db.query(UserPost).filter(UserPost.id == post_id).first()

    def get_all_image_urls(self, db: Session, post_id) -> list:
        post = self.get_by_id(db, post_id)
        if not post:
            return []
        return post.url_list or []

    def update_status(self, db: Session, post_id, status: str):
        post = self.get_by_id(db, post_id)
        if post:
            post.status = status
            db.commit()
            db.refresh(post)
        return post


post_repository = PostRepository()