import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import Base, Candidate, CandidateAssessment, Skill
from app.services.skill_alignment import compute_and_persist_skill_alignment


class TestSkillAlignment(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def test_compute_and_persist(self):
        db = self.Session()
        cand = Candidate(name="A", email=None)
        db.add(cand)
        db.commit()

        db.add(Skill(candidate_id=cand.id, name="Python", strength_of_evidence="Strongly evidenced"))
        db.add(Skill(candidate_id=cand.id, name="SQL", strength_of_evidence="Partially evidenced"))
        db.commit()

        res = compute_and_persist_skill_alignment(db, cand.id)

        self.assertEqual(res.skills_total, 2)
        self.assertEqual(res.skills_strong, 1)
        self.assertEqual(res.skills_partial, 1)
        self.assertAlmostEqual(res.score, 7.5, places=1)

        assessment = (
            db.query(CandidateAssessment)
            .filter_by(candidate_id=cand.id)
            .order_by(CandidateAssessment.generated_at.desc())
            .first()
        )
        self.assertIsNotNone(assessment)
        self.assertAlmostEqual(assessment.skill_alignment_score, 7.5, places=1)

        db.close()


if __name__ == "__main__":
    unittest.main()
