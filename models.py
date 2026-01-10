from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class UserInfo(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True)
    username = Column(String(100), unique=True, index=True)
    password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

      # 🔥 ONE → MANY
    transactions = relationship(
        "Transaction",
        back_populates="user"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))  # 🔑 FK

    username = Column(String(100), nullable=False)
    transaction_type = Column(String(50), nullable=False)  # Deposit / Withdraw
    amount = Column(Integer, nullable=False)
    current_balance = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 🔁 MANY → ONE
    user = relationship(
        "UserInfo",
        back_populates="transactions"
    )
