"""Create LangGraph's checkpoint tables (what PostgresSaver.setup() does)."""
import os

from langgraph.checkpoint.postgres import PostgresSaver

url = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
with PostgresSaver.from_conn_string(url) as saver:
    saver.setup()
print("checkpointer setup done")
