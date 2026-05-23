from sqlalchemy.orm import Session
from app.models.post import Post
from app.models.post_image import PostImage


class PostRepository:

    def create(
        self,
        db: Session,
        user_id: int,
        prompt: str,
        caption: str,
        image_url: str,          # primary image
        extra_image_urls: list = None,  # additional images
    ) -> Post:
        post = Post(
            user_id=user_id,
            prompt=prompt,
            caption=caption,
            image_url=image_url,
            status="draft",
        )
        db.add(post)
        db.flush()  # get post.id before adding images

        # Save all images to post_images table
        all_urls = [image_url] + (extra_image_urls or [])
        for i, url in enumerate(all_urls):
            img = PostImage(post_id=post.id, url=url, position=i)
            db.add(img)

        db.commit()
        db.refresh(post)
        return post

    def get_by_id(self, db: Session, post_id: int) -> Post:
        return db.query(Post).filter(Post.id == post_id).first()

    def get_all_image_urls(self, db: Session, post_id: int) -> list:
        """Return all image URLs for a post in order."""
        post = self.get_by_id(db, post_id)
        if not post:
            return []
        if post.images:
            return [img.url for img in post.images]
        # fallback for old posts without post_images records
        return [post.image_url] if post.image_url else []

    def update_status(self, db: Session, post_id: int, status: str):
        post = self.get_by_id(db, post_id)
        if post:
            post.status = status
            db.commit()
            db.refresh(post)
        return post


post_repository = PostRepository()