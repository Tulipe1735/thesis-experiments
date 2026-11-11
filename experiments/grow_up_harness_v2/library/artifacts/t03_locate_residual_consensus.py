def act(observation, task, state):
    errors = observation["absolute_radial_errors_m"]
    band = None
    for limit in (0.0015, 0.002, 0.0025):
        supported = sum(error <= limit for error in errors)
        if 50 <= supported < len(errors) and supported * 10 >= len(errors) * 9:
            band = limit
            break
    return {"action": {"op": "done"}, "state": {"inlier_band_m": band}}
