"""
Collection of possibly useful collision rules

A collision rule is a function that takes the two colliding objects (plus a
reference to the current `Simulation` for context) and returns a list of
actions to take. Actions are callables of signature ``action(sim) -> None``
where ``sim`` is the current `Simulation`. Note that the collision rule itself
should not modify anything about the simulation. It returns the function that
actually does the changes necessary. That way we can synchronize collisions.

Note that for all collision rules shown here (which mostly deal with `Walker`
particles because to run into anything, you have to be able to run in the first
place) we explicitly check whether there actually is a collision. This is
because a directional particle probably only cares about things that happen in
front of it, not about whether it is bumped by something from behind (in which
case the collision rules of course also have to apply).
"""
from .framework import Event

def reflect(walker, particle, sim):
    """
    Reflect a `Walker` upon collision
    """
    if walker.position+walker.direction == particle.position:
        def action(sim) : walker.direction *= -1
        return [action]
    return []

def kickOff(walker, particle, sim):
    """
    Kick off collision partner
    """
    if walker.position+walker.direction == particle.position:
        def action(sim) : sim.load(Event(particle.unload))
        return [action]
    return []

def burnOff(walker, particle, sim):
    """
    Same as kickOff, but also acts when the walker is being bumped from behind.

    If you want a picture for the naming conventions: kicking someone off the
    track is an active thing, so it needs your focus, i.e. happens only in the
    direction you are looking/walking. Here on the other hand, the walker is
    burning hot, such that everyone touching it will just die, no matter
    whether it is actively paying attention or not.
    """
    front = walker.position+walker.direction
    back = walker.position-walker.direction
    if front == particle.position or back == particle.position:
        def action(sim) : sim.load(Event(particle.unload))
        return [action]
    return []

def fallOff(walker, particle, sim):
    """
    Fall off upon collision
    """
    if walker.position+walker.direction == particle.position:
        def action(sim) : sim.load(Event(walker.unload))
        return [action]
    return []
