"""Collision-checked geometric walk routes with separate interaction samples."""

import heapq

import numpy as np


def walk_route(scene, anchors, spacing=0.10):
    width, length = scene['W'], scene['L']
    xs = np.linspace(0, width, int(np.ceil(width / spacing)) + 1)
    ys = np.linspace(0, length, int(np.ceil(length / spacing)) + 1)
    xx, yy = np.meshgrid(xs, ys)
    boxes = [scene['gt'][key] for key in ('desk', 'cab') if key in scene['gt']]
    blocked = np.zeros(xx.shape, bool)
    for x0, y0, x1, y1 in boxes:
        blocked |= (xx > x0) & (xx < x1) & (yy > y0) & (yy < y1)
    free = np.argwhere(~blocked)
    if not len(free):
        raise ValueError('No walkable floor in the declared desk/cabinet model')

    def nearest(point):
        distances = (xs[free[:, 1]] - point[0]) ** 2 + (ys[free[:, 0]] - point[1]) ** 2
        return tuple(int(v) for v in free[int(np.argmin(distances))])

    def clear(first, second):
        ay, ax = first
        by, bx = second
        for x0, y0, x1, y1 in boxes:
            if ay == by and y0 < ys[ay] < y1:
                if min(max(xs[ax], xs[bx]), x1) > max(min(xs[ax], xs[bx]), x0):
                    return False
            if ax == bx and x0 < xs[ax] < x1:
                if min(max(ys[ay], ys[by]), y1) > max(min(ys[ay], ys[by]), y0):
                    return False
        return True

    def connect(start, target):
        queue = [(0, 0, start)]
        costs, previous = {start: 0}, {}
        while queue:
            _, cost, current = heapq.heappop(queue)
            if cost != costs[current]:
                continue
            if current == target:
                route = [target]
                while route[-1] != start:
                    route.append(previous[route[-1]])
                return route[::-1]
            y, x = current
            for neighbor in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                ny, nx = neighbor
                if not (0 <= ny < len(ys) and 0 <= nx < len(xs)) or blocked[ny, nx]:
                    continue
                if not clear(current, neighbor):
                    continue
                next_cost = cost + 1
                if next_cost < costs.get(neighbor, float('inf')):
                    costs[neighbor], previous[neighbor] = next_cost, current
                    distance = abs(ny - target[0]) + abs(nx - target[1])
                    heapq.heappush(queue, (next_cost + distance, next_cost, neighbor))
        raise ValueError('Interaction approach is unreachable in the declared floor model')

    points, labels = [np.asarray(scene['S'], float)], [False]
    current = nearest(scene['S'])
    targets = [anchors[key] for key in ('seated', 'cabinet', 'lying') if key in anchors]
    targets.append(scene['S'])
    for target in targets:
        destination = nearest(target)
        route = connect(current, destination)
        for index, (y, x) in enumerate(route):
            points.append(np.array([xs[x], ys[y]]))
            labels.append(index > 0)
        # The phone can enter a contact footprint during sitting or lying.
        # These samples carry interaction state, not walk evidence.
        points.append(np.asarray(target, float))
        labels.append(False)
        points.append(np.array([xs[destination[1]], ys[destination[0]]]))
        labels.append(False)
        current = destination
    return np.asarray(points), np.asarray(labels, bool)
