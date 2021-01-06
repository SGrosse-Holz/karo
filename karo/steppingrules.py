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
    nextPos = sim.track[walker.position+walker.direction]
    if len(nextPos) > 0 and all(isinstance(p, Walker) for p in nextPos):
        actions = []
        for other_walker in nextPos:
            old_dir = other_walker.direction
            other_walker.direction = walker.direction
            try:
                actions += other_walker.steppingrule(sim)
            except TypeError: # One of the walkers didn't want to move
                return None
            finally:
                other_walker.direction = old_dir

        def shiftOthers(sim):
            for other_walker in nextPos:
                sim.track[walker.position+2*walker.direction].add(other_walker)
                other_walker.position += walker.direction
            sim.track[walker.position+walker.direction] = set()

        actions.append(shiftOthers)
        return actions
    else:
        return None

def pushy_hard(walker, sim):
    """
    Hard pushing: simply move everyone, without asking them
    """
    for particle in sim.track[walker.position+walker.direction]:
        if isinstance(particle, TrackEnd):
            return None

    def shiftOthers(sim):
        for other in sim.track[walker.position+walker.direction]:
            sim.track[walker.position+2*walker.direction].add(other)
            other.position += walker.direction
        sim.track[walker.position+walker.direction] = set()

    return [shiftOthers]

def pushy_train(walker, sim):
    """
    A stepping rule that allows to push whole trains of stuff. This is a riff
    on `pushy_hard`, which would collapse the train. Note that you might want
    to reimplement this, if there are any Boundaries that can halt the train.
    """
    train_start = walker.position + walker.direction
    train_end = sim.track.nextEmpty(walker.position, walker.direction)
    if walker.direction > 0:
        train_range = range(train_start, train_end)
    else:
        train_range = range(train_end+1, train_start+1)

    train_particles = sim.track.aggregate(train_range)

    if any(isinstance(particle, TrackEnd) for particle in train_particles):
        return None

    def shiftOthers(sim):
        # All references for particles in the train are in 'others', so we can
        # just wipe the range and repopulate
        for pos in train_range:
            sim.track[pos] = set()
        for particle in train_particles:
            particle.position += walker.direction
            sim.track[particle.position].add(particle)

    return [shiftOthers]
