import os


def get_db_config() -> dict[str, str]:
    return {
        "dbname": os.getenv("POSTGRES_DB", "assistant_db"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres_password"),
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5433"),
    }
