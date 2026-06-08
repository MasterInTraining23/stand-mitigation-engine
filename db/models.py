import time
from sqlalchemy import Column, Integer, BigInteger, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False)
    name = Column(String, nullable=False)
    written_rule = Column(Text, nullable=False)
    type = Column(String, nullable=False)
    definition = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="draft")
    activated_at = Column(BigInteger, nullable=True)
    deactivated_at = Column(BigInteger, nullable=True)
    author_id = Column(String, nullable=False)
    author_name = Column(String, nullable=False)
    change_note = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time() * 1000))

    mitigations = relationship("Mitigation", back_populates="rule", cascade="all, delete-orphan")
    audit_logs = relationship("RuleAuditLog", back_populates="rule")


class Mitigation(Base):
    __tablename__ = "mitigations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("rules.id"), nullable=False)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    modifier_params = Column(Text, nullable=True)

    rule = relationship("Rule", back_populates="mitigations")


class RuleAuditLog(Base):
    __tablename__ = "rule_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("rules.id"), nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    author_id = Column(String, nullable=False)
    author_name = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time() * 1000))

    rule = relationship("Rule", back_populates="audit_logs")
