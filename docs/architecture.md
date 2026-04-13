# TALASH v2.0 - System Architecture

## Overview
TALASH (Talent Acquisition & Learning Automation for Smart Hiring) is an AI-powered HR engine built to automate CV screening, candidate matching, and academic profiling.

## Core Pipeline
1. **Preprocessing (PDF to Image):** Ingests PDF CVs and converts them into high-resolution images for vision-based extraction.
2. **Data Extraction (Vision LLM):** Uses a local Vision LLM (Gemma 4) to parse document images into a strict, structured JSON schema.
3. **Evaluation Engine:** Applies logical reasoning to compute academic progression, verify publication quality, and analyze employment gaps.
4. **Web Dashboard:** A FastAPI + Frontend interface for HR recruiters to review generated applicant profiles and metrics.
