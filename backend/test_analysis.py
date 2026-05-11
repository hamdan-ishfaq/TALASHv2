import logging

from app.db import SessionLocal
from app.services.education_analysis import run_education_analysis


def main() -> None:
	logging.basicConfig(level=logging.INFO)
	db = SessionLocal()
	try:
		res = run_education_analysis(db, 1)
		print(res)
	finally:
		db.close()


if __name__ == "__main__":
	main()
