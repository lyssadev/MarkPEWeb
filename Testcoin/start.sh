#!/bin/bash

uvicorn api:app --host 0.0.0.0 --port $PORT --workers 4 --loop asyncio
