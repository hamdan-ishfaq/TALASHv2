import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import Base, Candidate, EducationRecord, MissingInformationRequest, WorkExperience
from app.services.missing_information_service import generate_missing_information_requests


class TestMissingInformationService(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def test_generate_patents_force_creates_request(self):
        db = self.Session()
        cand = Candidate(name="A", email=None, raw_text="")
        db.add(cand)
        db.commit()

        res = generate_missing_information_requests(
            db,
            cand.id,
            modules=["patents"],
            force=True,
        )
        db.commit()

        self.assertEqual(res.generated_modules, ["patents"])
        req = db.query(MissingInformationRequest).filter_by(candidate_id=cand.id, module_name="patents").first()
        self.assertIsNotNone(req)
        self.assertIn("patents_list", json.loads(req.missing_fields_json))

        db.close()

    def test_generate_patents_default_requires_signal(self):
        db = self.Session()
        cand = Candidate(name="A", email=None, raw_text="no relevant signals")
        db.add(cand)
        db.commit()

        res = generate_missing_information_requests(db, cand.id, modules=["patents"], force=False)
        db.commit()

        self.assertEqual(res.generated_modules, [])
        req = db.query(MissingInformationRequest).filter_by(candidate_id=cand.id, module_name="patents").first()
        self.assertIsNone(req)

        db.close()

    def test_upsert_updates_existing_request(self):
        db = self.Session()
        cand = Candidate(name="A", email=None, raw_text="patent")
        db.add(cand)
        db.commit()

        res1 = generate_missing_information_requests(db, cand.id, modules=["patents"], force=False)
        db.commit()
        self.assertEqual(res1.generated_modules, ["patents"])

        # Second run should update, not duplicate
        res2 = generate_missing_information_requests(db, cand.id, modules=["patents"], force=True)
        db.commit()
        self.assertEqual(res2.generated_modules, ["patents"])

        reqs = db.query(MissingInformationRequest).filter_by(candidate_id=cand.id, module_name="patents").all()
        self.assertEqual(len(reqs), 1)

        db.close()

    def test_education_incomplete_creates_request(self):
        db = self.Session()
        cand = Candidate(name="Edu", email=None, raw_text="")
        db.add(cand)
        db.commit()
        db.add(
            EducationRecord(
                candidate_id=cand.id,
                stage="SSE",
                institution="Govt High School",
                marks_percentage=None,
                cgpa=None,
            )
        )
        db.commit()

        res = generate_missing_information_requests(db, cand.id, modules=["education_analysis"], force=False)
        db.commit()

        self.assertIn("education_analysis", res.generated_modules)
        req = (
            db.query(MissingInformationRequest)
            .filter_by(candidate_id=cand.id, module_name="education_analysis")
            .first()
        )
        self.assertIsNotNone(req)
        fields = json.loads(req.missing_fields_json or "[]")
        self.assertTrue(any("marks" in f.lower() or "percentage" in f.lower() for f in fields))

        db.close()

    def test_experience_missing_dates_creates_request(self):
        db = self.Session()
        cand = Candidate(name="Exp", email=None, raw_text="")
        db.add(cand)
        db.commit()
        db.add(
            WorkExperience(
                candidate_id=cand.id,
                job_title="Engineer",
                organization="ACME",
                is_current=False,
            )
        )
        db.commit()

        res = generate_missing_information_requests(db, cand.id, modules=["experience_analysis"], force=False)
        db.commit()

        self.assertIn("experience_analysis", res.generated_modules)
        req = (
            db.query(MissingInformationRequest)
            .filter_by(candidate_id=cand.id, module_name="experience_analysis")
            .first()
        )
        self.assertIsNotNone(req)

        db.close()


if __name__ == "__main__":
    unittest.main()
