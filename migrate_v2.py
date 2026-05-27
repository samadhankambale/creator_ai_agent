"""
V2 Migration — drops old tables and creates all new UUID-based tables.

    python migrate_v2.py

WARNING: This DROPS all existing tables and recreates them.
All existing data will be lost.
"""
import sys
from sqlalchemy import text

from app.database.connection import engine
from app.database.base import Base

# Import ALL models so SQLAlchemy registers them
from app.models.user import User  # noqa
from app.models.user_social_account import UserSocialAccount  # noqa
from app.models.user_post import UserPost  # noqa
from app.models.draft import Draft  # noqa
from app.models.conversation import Conversation  # noqa
from app.models.ai_analytics import AIAnalytics  # noqa
from app.models.publish_job import PublishJob  # noqa
from app.models.subscription import (  # noqa
    SubscriptionPlan,
    UserSubscription,
    Order,
    PaymentTransaction,
)
from app.models.log import Log  # noqa


# Old tables to drop (in correct order to avoid FK violations)
OLD_TABLES = [
    "post_images",
    "publish_jobs",
    "posts",
    "social_accounts",
    "users",
    # v2 tables (in case partial migration happened before)
    "payment_transactions",
    "orders",
    "user_subscriptions",
    "subscription_plans",
    "ai_analytics",
    "conversations",
    "drafts",
    "user_posts",
    "user_social_accounts",
    "publish_jobs",
    "logs",
    "users",
]


def run():
    print("=" * 50)
    print("CREATOR AI V2 MIGRATION")
    print("=" * 50)
    print("\n⚠️  WARNING: This will DROP all existing tables.")
    print("All existing data will be permanently deleted.")

    if "--force" not in sys.argv:
        confirm = input(
            "\nType 'yes' to continue: "
        ).strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return

    print("\nDropping old tables...")
    with engine.connect() as conn:
        # Disable FK checks temporarily
        conn.execute(text("SET session_replication_role = replica;"))

        for table in OLD_TABLES:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                print(f"  ✓ Dropped: {table}")
            except Exception as e:
                print(f"  - Skip: {table} ({e})")

        conn.execute(text("SET session_replication_role = DEFAULT;"))
        conn.commit()

    print("\nCreating new UUID-based tables...")
    Base.metadata.create_all(bind=engine)

    print("\n✅ Migration complete!")
    print("\nNew tables created:")
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
        ))
        for row in result:
            print(f"  - {row[0]}")


if __name__ == "__main__":
    run()