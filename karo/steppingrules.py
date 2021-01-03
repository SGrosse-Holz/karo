"""
Collection of stepping rules

This module contains a few exemplatory stepping rules for use with
`baseparticles.Walker`.

A stepping rule has signature ``rule(obj, sim) -> <list or None>``. Their job
is twofold: check whether a `Walker` should take a step, and determine any
actions that should be taken immediately before the step. The rule itself
should not modify anything, just run through the logic and return a to-do list,
i.e. a list of actions, where ``action(sim) -> None``. Returning an empty list
means "do take the step, but no pre-processing necessary". If the step should
not be taken, the rule should ``return None`` (which is equivalent to a missing
``return`` statement).
"""

from .baseparticles import Walker, TrackEnd

def careful(walker, sim):
    """
    Careful stepping: only step if target site is free
    """
    if len(sim.track[walker.position + walker.direction]) == 0:
        return []

def transparent(walker, sim):
    """
    Always step, except off the track
    """
    if any(isinstance(particle, TrackEnd) for particle in sim.track[walker.position + walker.direction]):
        return None
    return []

def pushy_soft(walker, sim):
    """
    Soft pushing: ask other walkers to move

    Note that even though they will be asked whether they want to move, and the
    required actions will be taken, the pushed walkers will not actually be
    asked to `step <Walker.step>`, but simply moved.
    """
    if all(isinstance(p, Walker) for p in sim.track[walker.position+walker.direction]):
        actions = []
        for other_walker in sim.track[walker.position+walker.direction]:
            old_dir = other_walker.direction
            other_walker.direction = walker.direction
            try:
                actions += other_walker.steppingrule(sim)
            except TypeError: # One of the walkers didn't want to move
                return None
            finally:
                other_walker.direction = old_dir

        def shiftOthers(sim):
            for other_walker in sim.track[walker.position+walker.direction]:
                sim.track[walker.position+2*walker.direction].append(other_walker)
                other_walker.position += walker.direction
            sim.track[walker.position+walker.direction] = []

        actions.append(shiftOthers)
        return actions

def pushy_hard(walker, sim):
    """
    Hard pushing: simply move everyone, without asking them
    """
    for particle in sim.track[walker.position+walker.direction]:
        if isinstance(particle, TrackEnd):
            return None

    def shiftOthers(sim):
        for other in sim.track[walker.position+walker.direction]:
            sim.track[walker.position+2*walker.direction].append(other)
            other.position += walker.direction
        sim.track[walker.position+walker.direction] = []

    return [shiftOthers]

def pushy_train(walker, sim):
    """
    A stepping rule that allows to push whole trains of stuff. This is a riff
    on `pushy_hard`, which would collapse the train. Note that you might want
    to reimplement this, if there are any Boundaries that can halt the train.
    """
    curpos = 1
    others = sim.track[walker.position + curpos*walker.direction]
    while len(others) > 0:
        if any(isinstance(particle, TrackEnd) for particle in others):
            return None
        curpos += 1
        others = sim.track[walker.position + curpos*walker.direction]

    def shiftOthers(sim):
        # Get whole train
        train_end = 1
        while len(sim.track[walker.position + train_end*walker.direction]) > 0:
            train_end += 1

        # Move all of it
        while train_end >= 2:
            sim.track[walker.position + train_end*walker.direction] = sim.track[walker.position + (train_end-1)*walker.direction]
            for particle in sim.track[walker.position + train_end*walker.direction]:
                particle.position += walker.direction
            train_end -= 1
        sim.track[walker.position + walker.direction] = []

    return [shiftOthers]
