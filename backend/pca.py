import numpy as np


def fit_pca(vectors: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    """在训练向量(知识块)上拟合 PCA 基底,返回 (均值, 前2主方向)。"""
    X = np.array(vectors)
    mean = X.mean(axis=0)
    _, _, Vt = np.linalg.svd(X - mean, full_matrices=False)
    return mean, Vt[:2].T  # (d,) 与 (d, 2)


def project(vectors: list[list[float]], mean: np.ndarray, basis: np.ndarray) -> list[tuple[float, float]]:
    """把向量投影到已拟合的 2D PCA 基底(知识块定基底,query 投影到同一坐标系)。"""
    if not vectors:
        return []
    X = np.array(vectors)
    pts = (X - mean) @ basis
    return [tuple(float(v) for v in row) for row in pts]
