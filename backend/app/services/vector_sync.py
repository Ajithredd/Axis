import logging
import uuid
from typing import List, Any, Dict

from qdrant_client.http import models

from app.database.qdrant import get_qdrant_client
from app.services.embeddings import embedding_engine
from app.models.vector import VectorPayload

logger = logging.getLogger(__name__)

async def sync_node_to_vector_store(
    collection_name: str,
    node_id: str | uuid.UUID,
    project_id: str | uuid.UUID,
    node_type: str,
    content: str,
    metadata: Dict[str, Any] = None
) -> bool:
    """
    Generate an embedding for the given content and upsert it into Qdrant.
    """
    if not content or not content.strip():
        logger.warning(f"Empty content for node {node_id}, skipping vector sync.")
        return False

    embedding = await embedding_engine.generate_embedding(content)
    if not embedding:
        logger.error(f"Failed to generate embedding for node {node_id}")
        return False

    client = get_qdrant_client()
    
    payload = VectorPayload(
        project_id=str(project_id),
        node_type=node_type,
        node_id=str(node_id),
        content=content,
        metadata=metadata or {}
    )

    try:
        await client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=str(node_id),
                    vector=embedding,
                    payload=payload.model_dump()
                )
            ]
        )
        return True
    except Exception as e:
        logger.error(f"Failed to upsert node {node_id} into Qdrant: {e}")
        return False


async def sync_batch_to_vector_store(
    collection_name: str,
    nodes: List[Dict[str, Any]]
) -> int:
    """
    Generate embeddings for a batch of nodes and upsert them into Qdrant.
    
    Expects nodes to be a list of dicts with:
    'node_id', 'project_id', 'node_type', 'content', 'metadata' (optional)
    
    Returns the number of successfully synced nodes.
    """
    if not nodes:
        return 0

    valid_nodes = [n for n in nodes if n.get('content') and str(n['content']).strip()]
    if not valid_nodes:
        return 0

    contents = [str(n['content']) for n in valid_nodes]
    embeddings = await embedding_engine.generate_batch_embeddings(contents)
    
    if not embeddings or len(embeddings) != len(valid_nodes):
        logger.error(f"Failed to generate batch embeddings, got {len(embeddings) if embeddings else 0} expected {len(valid_nodes)}")
        return 0

    points = []
    for node, embedding in zip(valid_nodes, embeddings):
        payload = VectorPayload(
            project_id=str(node['project_id']),
            node_type=node['node_type'],
            node_id=str(node['node_id']),
            content=str(node['content']),
            metadata=node.get('metadata', {})
        )
        points.append(
            models.PointStruct(
                id=str(node['node_id']),
                vector=embedding,
                payload=payload.model_dump()
            )
        )

    client = get_qdrant_client()
    try:
        await client.upsert(
            collection_name=collection_name,
            points=points
        )
        return len(points)
    except Exception as e:
        logger.error(f"Failed to upsert batch into Qdrant: {e}")
        return 0
