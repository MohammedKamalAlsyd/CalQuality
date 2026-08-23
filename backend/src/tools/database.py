import os
import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_aws import ChatBedrockConverse

from src.clients.bedrock import bedrock
from src.config import DB_PATH, MODEL_ID


def create_scoped_db(account_id: str) -> SQLDatabase:
    """
    Creates an isolated in-memory DB with StaticPool so tables persist across queries.
    """
    main_conn = sqlite3.connect(DB_PATH)
    
    # 1. Read main tables
    accounts = pd.read_sql_query("SELECT * FROM accounts", main_conn)
    orders = pd.read_sql_query("SELECT * FROM orders", main_conn)
    tickets = pd.read_sql_query("SELECT * FROM tickets", main_conn)
    main_conn.close()
    
    # 2. Filter data at the code layer (Access Control)
    if account_id != "INTERNAL_OPS":
        accounts = accounts[accounts["account_id"] == account_id]
        orders = orders[orders["account_id"] == account_id]
        tickets = tickets[tickets["account_id"] == account_id]
        
    # 3. Create persistent in-memory Engine with StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # 4. Write scoped tables into the persistent memory
    accounts.to_sql("accounts", engine, index=False)
    orders.to_sql("orders", engine, index=False)
    tickets.to_sql("tickets", engine, index=False)
    
    return SQLDatabase(engine)

@tool
def query_structured_data(query: str, config: RunnableConfig) -> str:
    """
    Query or calculate information using the account, order, and ticket data.
    Useful for looking up order statuses, shipment fees, ticket history, etc.
    """
    # It comes from the FastAPI request.
    account_id = config.get("configurable", {}).get("account_id", "UNKNOWN")
    
    try:
        db = create_scoped_db(account_id)
        
        # 1. Get the database schema safely
        schema = db.get_table_info()
        
        # 2. Write a manual prompt (Bypasses LangChain's stopSequences bug)
        sql_prompt = f"""You are a SQLite expert. Write a SQL query to answer the user's question based on the schema below.
        Output ONLY the raw SQL query. Do not include markdown formatting, explanations, or quotes.

        SCHEMA:
        {schema}

        QUESTION: {query}
        SQL QUERY:"""

        # 3. Invoke LLM for SQL generation
        llm = ChatBedrockConverse(
            client=bedrock,
            model=MODEL_ID,
            temperature=0
        )
        response = llm.invoke(sql_prompt)
        
        # 4. Safely extract text content
        generated_sql = response.content
        if isinstance(generated_sql, list):
            # Handle block extraction if Llama returns a list
            generated_sql = next((block["text"] for block in generated_sql if isinstance(block, dict) and "text" in block), str(generated_sql))
            
        generated_sql = str(generated_sql).strip()
        
        # Clean up markdown if the LLM ignores instructions
        if "```sql" in generated_sql:
            generated_sql = generated_sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in generated_sql:
            generated_sql = generated_sql.split("```")[1].split("```")[0].strip()
            
        print(f"   📊 [SQL Executed for {account_id}]: {generated_sql}")
        
        # 5. Execute against the database
        execute_tool = QuerySQLDataBaseTool(db=db)
        result = execute_tool.invoke(generated_sql)
        print(f"   📊 [SQL Result]: {result}")
        
        return f"Executed SQL: {generated_sql}\nResult: {result}"
        
    except Exception as e:
        print(f"   ❌ [SQL Error]: {str(e)}")
        return f"Error querying structured data: {str(e)}"