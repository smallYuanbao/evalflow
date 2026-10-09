from backend.pca import fit_pca, project


def test_pca_projects_to_2d():
    train = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    mean, basis = fit_pca(train)
    pts = project(train, mean, basis)
    assert len(pts) == 3
    assert all(len(p) == 2 for p in pts)


def test_project_empty():
    mean, basis = fit_pca([[1, 0], [0, 1]])
    assert project([], mean, basis) == []
