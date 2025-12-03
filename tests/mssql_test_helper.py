"""
Shared MSSQL test database helper for testing SQL queries against a real
SQL Server instance with compatibility level 100 (matching TPP's production).

This module provides:
- Connection to the sqlrunner test MSSQL container
- Auto-start of the container if not running
- Helper functions for setting up test tables and running queries

Prerequisites:
- Docker running
- sqlrunner repo cloned at ../sqlrunner (relative to tpp-code-counts)

Usage:
    from mssql_test_helper import get_connection, run_query

    conn = get_connection()
    # ... set up tables and data ...
    results = run_query(conn, "path/to/query.sql")
"""

import time
from pathlib import Path

import docker
import pymssql


# Path to sqlrunner repo (needed for MSSQL setup scripts)
# Look for sqlrunner as sibling of the tpp-code-counts repo
SQLRUNNER_PATH = Path(__file__).parent.parent.parent / "sqlrunner"
MSSQL_SETUP_DIR = SQLRUNNER_PATH / "tests" / "support" / "mssql"

# Container configuration
CONTAINER_NAME = "sqlrunner-mssql"
PASSWORD = "Your_password123!"
MSSQL_PORT = 1433


def get_or_start_mssql_container():  # pragma: no cover
    """Start the MSSQL test container or connect to existing one.

    Returns:
        dict: Connection configuration with host, port, password
    """
    if not SQLRUNNER_PATH.exists():
        raise RuntimeError(
            f"sqlrunner repo not found at {SQLRUNNER_PATH}\n"
            "Please clone it: git clone https://github.com/opensafely-core/sqlrunner.git ../sqlrunner"
        )

    client = docker.from_env()

    # Check if container is already running
    try:
        container = client.containers.get(CONTAINER_NAME)
        if container.status == "running":
            port_config = container.attrs["NetworkSettings"]["Ports"][
                f"{MSSQL_PORT}/tcp"
            ]
            host_port = int(port_config[0]["HostPort"])
            return {"host": "localhost", "port": host_port, "password": PASSWORD}
        else:
            # Container exists but not running, remove it
            container.remove()
    except docker.errors.NotFound:
        pass

    # Start the container
    print(f"Starting MSSQL container '{CONTAINER_NAME}'...")
    container = client.containers.run(
        name=CONTAINER_NAME,
        image="mcr.microsoft.com/mssql/server:2019-CU28-ubuntu-20.04",
        volumes={
            str(MSSQL_SETUP_DIR): {"bind": "/mssql", "mode": "ro"},
        },
        ports={MSSQL_PORT: None},  # Random host port
        environment={
            "SA_PASSWORD": PASSWORD,
            "ACCEPT_EULA": "Y",
            "MSSQL_TCP_PORT": str(MSSQL_PORT),
        },
        entrypoint="/mssql/entrypoint.sh",
        command="/opt/mssql/bin/sqlservr",
        detach=True,
    )

    # Get the assigned port
    container.reload()
    port_config = container.attrs["NetworkSettings"]["Ports"][f"{MSSQL_PORT}/tcp"]
    host_port = int(port_config[0]["HostPort"])

    print(f"Container started on port {host_port}")
    return {"host": "localhost", "port": host_port, "password": PASSWORD}


def wait_for_database(config, timeout=60):
    """Wait for database to be ready."""
    print(f"Waiting for database (timeout: {timeout}s)...", end="", flush=True)
    start = time.time()
    limit = start + timeout

    while True:
        try:
            conn = pymssql.connect(
                user="SA",
                password=config["password"],
                server=config["host"],
                port=config["port"],
                database="test",
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 'hello'")
            conn.close()
            print(" ready!")
            return
        except pymssql.OperationalError:
            if time.time() > limit:
                raise Exception(
                    f"Failed to connect to database after {timeout} seconds"
                )
            time.sleep(1)
            print(".", end="", flush=True)


def get_connection():
    """Get a connection to the test MSSQL database.

    Returns:
        pymssql.Connection: Database connection
    """
    config = get_or_start_mssql_container()
    wait_for_database(config)

    return pymssql.connect(
        user="SA",
        password=config["password"],
        server=config["host"],
        port=config["port"],
        database="test",
    )


def run_query(conn, sql_file_or_string, as_dict=True):
    """Run a SQL query and return results.

    Args:
        conn: Database connection
        sql_file_or_string: Either a path to a .sql file or a SQL string
        as_dict: If True, return results as list of dicts; otherwise list of tuples

    Returns:
        list: Query results
    """
    # Determine if it's a file path or SQL string
    if (
        isinstance(sql_file_or_string, (str, Path))
        and Path(sql_file_or_string).exists()
    ):
        sql = Path(sql_file_or_string).read_text()
    else:
        sql = sql_file_or_string

    cursor = conn.cursor(as_dict=as_dict)
    cursor.execute(sql)
    return list(cursor)


def execute_sql(conn, sql, params=None):
    """Execute SQL statement(s) without returning results.

    Args:
        conn: Database connection
        sql: SQL statement(s) to execute
        params: Optional parameters for parameterized queries
    """
    cursor = conn.cursor()
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    conn.commit()


def drop_table_if_exists(conn, table_name):
    """Drop a table if it exists."""
    execute_sql(
        conn, f"IF OBJECT_ID('{table_name}', 'U') IS NOT NULL DROP TABLE {table_name}"
    )


def setup_t1oo_table(conn, opted_out_patient_ids=None):
    """Create and populate the Type 1 opt-out table.

    Args:
        conn: Database connection
        opted_out_patient_ids: List of patient IDs who have opted out
    """
    drop_table_if_exists(conn, "PatientsWithTypeOneDissent")
    execute_sql(
        conn, "CREATE TABLE PatientsWithTypeOneDissent (Patient_ID BIGINT PRIMARY KEY)"
    )

    if opted_out_patient_ids:
        for patient_id in opted_out_patient_ids:
            execute_sql(
                conn,
                "INSERT INTO PatientsWithTypeOneDissent (Patient_ID) VALUES (%s)",
                (patient_id,),
            )
