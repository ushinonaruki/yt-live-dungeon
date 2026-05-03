from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NicknameWord(Base):
    __tablename__ = "nickname_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(64))
    part: Mapped[str] = mapped_column(String(16))
