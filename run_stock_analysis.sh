#!/bin/bash

cd /home/kaochuchian/stock-ai

/home/kaochuchian/stock-ai/venv/bin/python scripts/run_pipeline.py pre_open --production-approved >> logs/daily.log 2>&1
