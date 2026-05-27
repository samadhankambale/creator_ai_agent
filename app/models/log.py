import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.database.base import Base


class Log(Base):
    __tablename__ = "logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    log_level = Column(String)          # info | warning | error | critical
    log_type = Column(String)           # api | webhook | publish | auth
    source = Column(String)             # service/function name
    log_message = Column(Text)
    api_endpoint = Column(String)
    http_method = Column(String)
    status_code = Column(Integer)
    response_time_ms = Column(Integer)
    request_payload = Column(JSON)
    context = Column(JSON)
    error_message = Column(Text)
    ip_address = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)