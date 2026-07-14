"""Shared Neo4j connection helper for the maintenance scripts.

Reads the same configuration as the Go importer, with the same precedence:
real environment variables win over the repo-root .env file, which wins over
the local-development defaults. The password default is Neo4j's
out-of-the-box value - do not use in production.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_driver():
    load_dotenv(REPO_ROOT / ".env", override=False)
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    print(f"Connected to {uri} as {username}")
    return driver


def run(driver, query, **params):
    """Run one auto-commit query and return (records, summary counters)."""
    records, summary, _ = driver.execute_query(query, **params)
    return records, summary.counters
