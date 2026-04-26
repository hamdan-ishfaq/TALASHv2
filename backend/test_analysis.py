from app.db import SessionLocal
from app.services.education_analysis import run_education_analysis
import logging

logging.basicConfig(level=logging.INFO)
db = SessionLocal()
res = run_education_analysis(db, 1)
print(res)
db.close()
