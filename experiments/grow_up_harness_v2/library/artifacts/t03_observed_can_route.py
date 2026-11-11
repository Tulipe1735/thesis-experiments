def act(observation, task, state):
    routes = observation.get('routes') or []
    def safe(r):
        return (r.get('reachable') is True
                and r.get('obstacle_clearance_m') is not None
                and r.get('obstacle_clearance_m') >= 0.006
                and r.get('table_clearance_m') is not None
                and r.get('table_clearance_m') >= 0.001)
    chosen = None
    for r in routes:
        if r.get('route_id') == 'default' and safe(r):
            chosen = 'default'
            break
    if chosen is None:
        for r in routes:
            if r.get('route_id') != 'default' and safe(r):
                chosen = r.get('route_id')
                break
    return {'action': {'op': 'done'}, 'state': {'route_id': chosen}}