"""Simple entry point for the engineering app."""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from engineering_app.web_app import main

if __name__ == "__main__":
    main()