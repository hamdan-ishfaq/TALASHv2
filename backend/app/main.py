from fastapi import FastAPI

# Initialize the FastAPI application
app = FastAPI(
    title="TALASH v2.0 API",
    description="The Hybrid Vision-Reasoning HR Engine",
    version="2.0.0"
)

# Root endpoint
@app.get("/")
def read_root():
    return {"status": "TALASH v2.0 Core is Online"}

# Health check endpoint for system monitoring
@app.get("/health")
def health_check():
    return {
        "system": "Healthy", 
        "ollama_connection": "Pending", 
        "pdf_processor": "Pending"
    }