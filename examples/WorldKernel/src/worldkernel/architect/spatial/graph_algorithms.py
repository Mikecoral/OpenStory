"""Pure-Python graph algorithms: BFS, Dijkstra, Fruchterman-Reingold layout."""

from __future__ import annotations

import heapq
import math
import random
from collections import deque


def bfs_components(adj: dict[str, set[str]]) -> list[list[str]]:
    """Find connected components via BFS.

    Returns a list of components, each being a sorted list of node IDs.
    Components are sorted by their first node.
    """
    visited: set[str] = set()
    components: list[list[str]] = []
    for start in sorted(adj.keys()):
        if start in visited:
            continue
        component: list[str] = []
        queue: deque[str] = deque([start])
        visited.add(start)
        while queue:
            node = queue.popleft()
            component.append(node)
            for neighbor in sorted(adj.get(node, set())):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    return components


def bfs_distances(adj: dict[str, set[str]], source: str) -> dict[str, int]:
    """BFS shortest hop distances from source.

    Returns {node: distance} for all reachable nodes.
    """
    distances: dict[str, int] = {source: 0}
    queue: deque[str] = deque([source])
    while queue:
        node = queue.popleft()
        for neighbor in adj.get(node, set()):
            if neighbor not in distances:
                distances[neighbor] = distances[node] + 1
                queue.append(neighbor)
    return distances


def dijkstra(adj: dict[str, dict[str, float]], source: str) -> dict[str, float]:
    """Dijkstra shortest paths from source using weighted adjacency.

    adj: {node: {neighbor: weight, ...}, ...}
    Returns {node: distance} for all reachable nodes.
    """
    distances: dict[str, float] = {source: 0.0}
    heap: list[tuple[float, str]] = [(0.0, source)]
    while heap:
        dist, node = heapq.heappop(heap)
        if dist > distances.get(node, float("inf")):
            continue
        for neighbor, weight in adj.get(node, {}).items():
            new_dist = dist + weight
            if new_dist < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))
    return distances


def fruchterman_reingold(
    nodes: list[str],
    edges: list[tuple[str, str]],
    iterations: int = 200,
    seed: int = 42,
    width: float = 160.0,
    height: float = 100.0,
    margin: float = 6.0,
) -> dict[str, tuple[float, float]]:
    """Fruchterman-Reingold force-directed graph layout.

    Parameters
    ----------
    nodes : list of node IDs
    edges : list of (from, to) undirected edges
    iterations : number of FR iterations
    seed : random seed for deterministic output
    width, height : canvas dimensions (continuous coordinates)
    margin : minimum distance from canvas border

    Returns
    -------
    {node_id: (x, y)} continuous coordinates within [margin, width-margin] x [margin, height-margin]
    """
    if not nodes:
        return {}

    rng = random.Random(seed)
    n = len(nodes)
    area = width * height
    k = math.sqrt(area / n) if n > 1 else 1.0  # ideal spring length

    # Initialize random positions
    pos: dict[str, list[float]] = {
        node: [rng.uniform(margin, width - margin), rng.uniform(margin, height - margin)]
        for node in nodes
    }

    # Build adjacency set for quick lookup
    edge_set: set[tuple[str, str]] = set()
    for a, b in edges:
        edge_set.add((a, b))
        edge_set.add((b, a))

    # Temperature schedule: linear cooling from t_max to 0
    t_max = max(width, height) / 10.0

    for iteration in range(iterations):
        t = t_max * (1.0 - iteration / iterations) if iterations > 0 else 0.0

        # Displacement accumulator
        disp: dict[str, list[float]] = {node: [0.0, 0.0] for node in nodes}

        # Repulsive forces: all pairs
        for i, u in enumerate(nodes):
            for v in nodes[i + 1:]:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                dist = max(math.hypot(dx, dy), 0.01)
                # fr = k^2 / dist
                fr = (k * k) / dist
                fx = (dx / dist) * fr
                fy = (dy / dist) * fr
                disp[u][0] += fx
                disp[u][1] += fy
                disp[v][0] -= fx
                disp[v][1] -= fy

        # Attractive forces: edges only
        for u, v in edges:
            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            dist = max(math.hypot(dx, dy), 0.01)
            # fa = dist^2 / k
            fa = (dist * dist) / k
            fx = (dx / dist) * fa
            fy = (dy / dist) * fa
            disp[u][0] -= fx
            disp[u][1] -= fy
            disp[v][0] += fx
            disp[v][1] += fy

        # Apply displacements, capped by temperature
        for node in nodes:
            dx, dy = disp[node][0], disp[node][1]
            disp_len = max(math.hypot(dx, dy), 0.01)
            # Cap displacement to temperature
            capped = min(disp_len, t)
            pos[node][0] += (dx / disp_len) * capped
            pos[node][1] += (dy / disp_len) * capped
            # Clamp to canvas bounds
            pos[node][0] = max(margin, min(width - margin, pos[node][0]))
            pos[node][1] = max(margin, min(height - margin, pos[node][1]))

    return {node: (pos[node][0], pos[node][1]) for node in nodes}


def astar_orthogonal(
    grid: list[list[int]],
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked_value: int = 0,
    allow_through_blocked: bool = False,
    blocked_cost: int = 5,
) -> list[tuple[int, int]] | None:
    """Orthogonal A* pathfinding on a 2D grid.

    Parameters
    ----------
    grid : 2D array where grid[y][x] == blocked_value means impassable.
    start : (x, y) start tile
    goal : (x, y) goal tile
    blocked_value : value that means blocked (default 0)
    allow_through_blocked : if True, blocked tiles are passable at higher cost
    blocked_cost : movement cost through blocked tiles (only used when allow_through_blocked=True)

    Returns
    -------
    List of (x, y) from start to goal inclusive, or None if no path.
    """
    if not grid or not grid[0]:
        return None
    height = len(grid)
    width = len(grid[0])

    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < width and 0 <= sy < height):
        return None
    if not (0 <= gx < width and 0 <= gy < height):
        return None
    if not allow_through_blocked:
        if grid[sy][sx] == blocked_value or grid[gy][gx] == blocked_value:
            return None
    if start == goal:
        return [start]

    def h(x: int, y: int) -> int:
        return abs(x - gx) + abs(y - gy)

    open_set: list[tuple[int, int, int, int]] = []  # (f, h, x, y)
    heapq.heappush(open_set, (h(sx, sy), 0, sx, sy))

    g_score: dict[tuple[int, int], int] = {(sx, sy): 0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}

    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]

    while open_set:
        f, _, cx, cy = heapq.heappop(open_set)
        if (cx, cy) == (gx, gy):
            path: list[tuple[int, int]] = [(cx, cy)]
            while (cx, cy) in came_from:
                cx, cy = came_from[(cx, cy)]
                path.append((cx, cy))
            path.reverse()
            return path

        current_g = g_score[(cx, cy)]
        if f > current_g + h(cx, cy):
            continue

        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            is_blocked = grid[ny][nx] == blocked_value
            if is_blocked and not allow_through_blocked:
                continue
            step_cost = blocked_cost if is_blocked else 1
            tentative_g = current_g + step_cost
            if tentative_g < g_score.get((nx, ny), float("inf")):
                g_score[(nx, ny)] = tentative_g
                came_from[(nx, ny)] = (cx, cy)
                f_new = tentative_g + h(nx, ny)
                heapq.heappush(open_set, (f_new, h(nx, ny), nx, ny))

    return None


def astar_weighted_orthogonal(
    width: int,
    height: int,
    start: tuple[int, int],
    goal: tuple[int, int],
    cost_fn,
    min_step_cost: float = 0.3,
) -> list[tuple[int, int]] | None:
    """Orthogonal A* with a per-tile movement cost callback.

    ``cost_fn(x, y)`` should return a positive cost for passable tiles, or
    ``None``/``inf`` to make the tile impassable.
    """
    sx, sy = start
    gx, gy = goal
    if width <= 0 or height <= 0:
        return None
    if not (0 <= sx < width and 0 <= sy < height):
        return None
    if not (0 <= gx < width and 0 <= gy < height):
        return None
    if start == goal:
        return [start]

    def h(x: int, y: int) -> float:
        return (abs(x - gx) + abs(y - gy)) * min_step_cost

    open_set: list[tuple[float, float, int, int]] = []
    heapq.heappush(open_set, (h(sx, sy), 0.0, sx, sy))

    g_score: dict[tuple[int, int], float] = {(sx, sy): 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]

    while open_set:
        f, _, cx, cy = heapq.heappop(open_set)
        if (cx, cy) == (gx, gy):
            path: list[tuple[int, int]] = [(cx, cy)]
            while (cx, cy) in came_from:
                cx, cy = came_from[(cx, cy)]
                path.append((cx, cy))
            path.reverse()
            return path

        current_g = g_score[(cx, cy)]
        if f > current_g + h(cx, cy) + 1e-9:
            continue

        for dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            step_cost = cost_fn(nx, ny)
            if step_cost is None or step_cost == float("inf"):
                continue
            tentative_g = current_g + float(step_cost)
            if tentative_g < g_score.get((nx, ny), float("inf")):
                g_score[(nx, ny)] = tentative_g
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_set, (tentative_g + h(nx, ny), h(nx, ny), nx, ny))

    return None
