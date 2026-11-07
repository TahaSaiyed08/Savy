"""Create the AI Search (Vector Search) endpoint and the flyer_items_idx Delta Sync index. Idempotent.

Usage: uv run python databricks/setup/ai_search_index.py    (after the pipeline has built flyer_items)
Free Edition allows one endpoint and one index, so this makes exactly one of each.
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    EndpointType,
    PipelineType,
    VectorIndexType,
)

ENDPOINT = "realdeal"
INDEX = "realdeal.core.flyer_items_idx"
SOURCE = "realdeal.core.flyer_items"
EMBEDDING_MODEL = "databricks-gte-large-en"

w = WorkspaceClient()
if ENDPOINT not in {e.name for e in w.vector_search_endpoints.list_endpoints()}:
    print(f"creating endpoint {ENDPOINT} (takes several minutes)")
    w.vector_search_endpoints.create_endpoint_and_wait(name=ENDPOINT, endpoint_type=EndpointType.STANDARD)

try:
    w.vector_search_indexes.get_index(INDEX)
    print(f"{INDEX} exists; syncing")
    w.vector_search_indexes.sync_index(INDEX)
except NotFound:
    w.vector_search_indexes.create_index(
        name=INDEX,
        endpoint_name=ENDPOINT,
        primary_key="item_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=SOURCE,
            pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[
                EmbeddingSourceColumn(name="match_text", embedding_model_endpoint_name=EMBEDDING_MODEL)
            ],
            columns_to_sync=["item_id", "brand", "item", "variant", "store", "price", "unit_price", "unit"],
        ),
    )
    print(f"created {INDEX}")

# Smoke query: the 20-pair tuning set starts here.
r = w.vector_search_indexes.query_index(INDEX, columns=["item_id", "brand", "item", "store"],
                                        query_text="2% milk 4 l", num_results=3)
print(r.result.data_array if r.result else "index not ready yet")
