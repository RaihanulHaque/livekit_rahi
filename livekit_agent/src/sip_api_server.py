#!/usr/bin/env python
"""
Standalone SIP API server.
Runs FastAPI server for SIP agent management.
"""

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from sip_api import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sip_api_server")


def main():
    app = FastAPI(title="SIP Agent Management API")

    # Add CORS middleware to allow requests from frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins (for development)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    logger.info("Starting SIP API server on 0.0.0.0:8089...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8089,
        log_level="info",
    )


if __name__ == "__main__":
    main()
