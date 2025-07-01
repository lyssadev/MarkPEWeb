#!/bin/bash

# Start the FastAPI server with uvicorn
uvicorn api:app --host 0.0.0.0 --port $PORT
