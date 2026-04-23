"""Neo4j client + ingestion pipeline for graph persistence."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from neo4j import GraphDatabase

from codepulse.config import settings
from codepulse.graph.schema import GraphMapper, IngestQueries, Neo4jSchema
from codepulse.logging import get_logger

log = get_logger(__name__)


class Neo4jClient:
    """Thin wrapper around the Neo4j Python driver."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
    ):
        self._uri = uri or settings.neo4j_uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self.database = database
        self.driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(self, query: str, **params: Any) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(query, **params)


class Neo4jIngestion:
    """Source-compatible ingestion behavior adapted for target graph layer."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        *,
        batch_size: int = 1000,
    ):
        self.client = Neo4jClient(uri=uri, user=user, password=password, database=database)
        self.batch_size = batch_size

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Neo4jIngestion":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def initialize_schema(self) -> None:
        for query in [*Neo4jSchema.constraints(), *Neo4jSchema.indexes()]:
            self.client.run(query)

    def ingest_from_json(self, json_data: dict[str, Any]) -> dict[str, int]:
        # Note: incremental mode not yet implemented

        file_nodes = GraphMapper.extract_file_nodes(json_data)
        symbol_nodes = GraphMapper.extract_symbol_nodes(json_data)
        package_nodes = GraphMapper.extract_package_nodes(json_data)

        contains = GraphMapper.extract_contains_relationships(json_data)
        all_calls = GraphMapper.extract_calls_relationships(json_data)
        calls = [rel for rel in all_calls if rel.get("resolved")]
        if len(all_calls) > len(calls):
            log.warning(f"Discarding {len(all_calls) - len(calls)} unresolved call relationships")
        imports = GraphMapper.extract_imports_relationships(json_data)

        self._run_batched(IngestQueries.UPSERT_FILES, "files", [asdict(node) for node in file_nodes])
        self._run_batched(IngestQueries.UPSERT_SYMBOLS, "symbols", [asdict(node) for node in symbol_nodes])
        self._run_batched(IngestQueries.UPSERT_PACKAGES, "packages", [asdict(node) for node in package_nodes])

        self._run_batched(IngestQueries.CREATE_CONTAINS, "rels", contains)
        self._run_batched(IngestQueries.CREATE_CALLS, "rels", calls)
        self._run_batched(IngestQueries.CREATE_IMPORTS, "rels", imports)

        stats = {
            "files_processed": len(file_nodes),
            "files_updated": len(file_nodes),
            "symbols_created": len(symbol_nodes),
            "packages_created": len(package_nodes),
            "relationships_created": len(contains) + len(calls) + len(imports),
        }
        log.info(f"Neo4j ingestion complete: {stats}")
        return stats

    def _run_batched(self, query: str, param_name: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i : i + self.batch_size]
            self.client.run(query, **{param_name: batch})
