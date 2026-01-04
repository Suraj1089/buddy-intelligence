#!/bin/bash
# Start Redis with 500MB memory limit for local development
echo "Starting Redis with 500MB maxmemory limit..."
redis-server --maxmemory 500mb --maxmemory-policy allkeys-lru --appendonly yes
