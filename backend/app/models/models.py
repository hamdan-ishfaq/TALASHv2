from sqlalchemy import Boolean, Column, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    file_hash = Column(String(64), unique=True, index=True, nullable=True)
    file_path = Column(String(500), nullable=True)
    raw_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")

    education_records = relationship(
        "EducationRecord", back_populates="candidate", cascade="all, delete-orphan"
    )
    work_experiences = relationship(
        "WorkExperience", back_populates="candidate", cascade="all, delete-orphan"
    )
    publications = relationship(
        "Publication", back_populates="candidate", cascade="all, delete-orphan"
    )
    supervision_records = relationship(
        "SupervisionRecord", back_populates="candidate", cascade="all, delete-orphan"
    )
    books = relationship("Book", back_populates="candidate", cascade="all, delete-orphan")
    patents = relationship("Patent", back_populates="candidate", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="candidate", cascade="all, delete-orphan")
    scores = relationship(
        "CandidateScore", back_populates="candidate", cascade="all, delete-orphan"
    )


class EducationRecord(Base):
    __tablename__ = "education_records"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    degree_level = Column(String(100), nullable=True)
    title = Column(String(255), nullable=True)
    institution = Column(String(255), nullable=True)
    passing_year = Column(Integer, nullable=True)
    cgpa = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="education_records")


class WorkExperience(Base):
    __tablename__ = "work_experiences"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    job_title = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)

    candidate = relationship("Candidate", back_populates="work_experiences")


class Publication(Base):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    authors = Column(Text, nullable=True)
    venue = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    type = Column(String(100), nullable=True)

    candidate = relationship("Candidate", back_populates="publications")


class SupervisionRecord(Base):
    __tablename__ = "supervision_records"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    level = Column(String(100), nullable=True)
    student_name = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)

    candidate = relationship("Candidate", back_populates="supervision_records")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    authors = Column(Text, nullable=True)
    publisher = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True)
    isbn = Column(String(50), nullable=True)

    candidate = relationship("Candidate", back_populates="books")


class Patent(Base):
    __tablename__ = "patents"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    inventors = Column(Text, nullable=True)
    patent_no = Column(String(100), nullable=True)
    year = Column(Integer, nullable=True)
    status = Column(String(100), nullable=True)

    candidate = relationship("Candidate", back_populates="patents")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    proficiency_level = Column(String(100), nullable=True)
    years_of_experience = Column(Float, nullable=True)

    candidate = relationship("Candidate", back_populates="skills")


class CandidateScore(Base):
    __tablename__ = "candidate_scores"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    score_type = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="scores")
