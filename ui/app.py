import streamlit as st
import httpx
import json
from typing import Any

# Base URL for the API
BASE_URL = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8000")

def api_call(method: str, endpoint: str, **kwargs) -> Any:
    try:
        with httpx.Client() as client:
            response = client.request(method, f"{BASE_URL}{endpoint}", **kwargs)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        st.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        st.error(f"Request error: {e}")
    except Exception as e:
        st.error(f"Error: {e}")
    return None

st.title("CodePulse Frontend")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Health", "Repos", "Graph", "Chat", "Analysis"])

with tab1:
    st.header("Health Check")
    if st.button("Check Health"):
        result = api_call("GET", "/health")
        if result:
            st.success(f"Status: {result.get('status', 'Unknown')}")

with tab2:
    st.header("Indexed Repositories")
    if st.button("Fetch Repos"):
        result = api_call("GET", "/repos/")
        if result:
            st.table(result)

with tab3:
    st.header("Graph Queries")
    subtab1, subtab2 = st.tabs(["Blast Radius", "Test Coverage"])
    
    with subtab1:
        symbol = st.text_input("Symbol", key="blast_symbol")
        max_depth = st.slider("Max Depth", 1, 10, 3, key="blast_depth")
        if st.button("Get Blast Radius"):
            result = api_call("GET", "/graph/blast-radius", params={"symbol": symbol, "max_depth": max_depth})
            if result:
                st.write(f"Found {len(result)} impacted symbols:")
                st.table([{"symbol": item.get("symbol", ""), "file": item.get("file", ""), "kind": item.get("kind", "")} for item in result])
    
    with subtab2:
        symbol = st.text_input("Symbol", key="test_symbol")
        if st.button("Check Test Coverage"):
            result = api_call("GET", "/graph/test-coverage", params={"symbol": symbol})
            if result:
                st.write(result)

with tab4:
    st.header("Chat")
    question = st.text_area("Question")
    symbol_hint = st.text_input("Symbol Hint (optional)")
    if st.button("Ask"):
        data = {"question": question}
        if symbol_hint:
            data["symbol_hint"] = symbol_hint
        result = api_call("POST", "/chat/", json=data)
        if result:
            st.write("Answer:")
            st.write(result.get("answer", ""))

with tab5:
    st.header("Diff Analysis")
    repo_path = st.text_input("Repository Path")
    commit_ref = st.text_input("Commit Ref", value="HEAD~1")
    if st.button("Analyze Diff"):
        data = {"repo_path": repo_path, "commit_ref": commit_ref}
        result = api_call("POST", "/analysis/diff", json=data)
        if result:
            st.write("Risk Result:")
            st.json(result)