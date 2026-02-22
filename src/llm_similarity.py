from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np


def find_related_papers_by_cosine(
    target_paper_id: str,
    all_papers_vectors: Dict[str, List[float]],
    top_k: int = 3,
) -> List[Tuple[str, float]]:
    if target_paper_id not in all_papers_vectors:
        return []

    target_vec = np.array(all_papers_vectors[target_paper_id])
    if np.linalg.norm(target_vec) == 0:
        return []

    results: List[Tuple[str, float]] = []
    for paper_id, vector in all_papers_vectors.items():
        if paper_id == target_paper_id:
            continue

        current_vec = np.array(vector)
        norm_current_vec = np.linalg.norm(current_vec)
        if norm_current_vec == 0:
            continue

        similarity = np.dot(target_vec, current_vec) / (np.linalg.norm(target_vec) * norm_current_vec)
        results.append((paper_id, similarity))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]
