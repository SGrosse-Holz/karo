"""
Base classes for particles one might want to simulate

All of these inherit from `Particle`. Note that ideally, these classes would
not be instantiated, but serve as base classes for concrete implementations.
Otherwise specifying collision rules gets harder.

Examples
--------
Assuming we have a `Collider` instance ``mycoll``:
>>> class ReflectedWalker(Walker):
...     pass
... mycoll.register(ReflectedWalker, Particle, collisionrules.reflect)
...
... class Cleaner(Walker):
...     # Don't get fazed by anything except Boundaries
...     def steppingrule(self, sim):
...         if not any(isinstance(p, Boundary) for p in sim.track[self.position+self.direction]):
...             return []
... mycoll.register(Cleaner, Particle, Walker.collide_kickOff)

Randomness where needed is generated from python's `!random` module, so this
should be seeded for reproducible results.
"""

import random
from .constituents import *

class Boundary(Particle):
    """
    Stationary particle that can serve as boundary
    """
    pass

class TrackEnd(Boundary):
    """
    Used by `Simulation` to prevent particles from falling off at the end.
    """
    pass

class FiniteLife(Updateable, Loadable):
    """
    Base class for anything with a finite life time

    Attributes
    ----------
    lifetime : float
        the remaining lifetime

    Notes
    -----
    If subclassing this together with some other particle type, make sure to
    call both types' `!nextUpdate` and `!update` method.
    """
    def __init__(self, lifetime=float('inf')):
        self.lifetime = lifetime

    def nextUpdate(self, sim):
        return min(self.lifetime, Updateable.nextUpdate(self, sim))

    def update(self, sim):
        self.lifetime -= sim.time - self.lastUpdate
        if self.lifetime < 1e-10: # small positive threshold for numerical safety
            sim.load(Event(self.unload))

        self.lastUpdate = sim.time
        # Note that Updateable.update automatically requeues, which would lead
        # to an endless recursion here. So no super() call.
        
class Walker(Particle):
    """
    A simple moving particle

    Attributes
    ----------
    direction : {-1, 1}
        the current direction of motion. Chosen randomly if not specified
        otherwise at initialization
    speed : float
        the walking speed (steps / unit time)

    Notes
    -----
    In addition to collision rules, a moving particle needs a `steppingrule` to
    decide when to take (or not take) a step. In addition, `steppingrule` can
    return a list of actions to take before the actual step. See
    `steppingrules`. The default rule for this class is
    `steppingrules.careful`.

    Side note: if your simulation contains things that happen at exactly equal
    time in theory, the order of these might be unpredictable due to floating
    point arithmetic. This is considered okay, since for things that happen at
    **exactly** the same time in theory, the order should not matter. If this
    is a problem, consider introducing a small shift in the timing (e.g. by
    using an `Event` to load your particle a little bit after the integer
    time). Floating point errors on most machines are of order 1 in 10**16, so
    an offset of ``1e-7`` should be fine, if you're planning to take less than
    a billion steps.
    """
    def __init__(self, speed=1, direction=None, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
        if self.direction is None:
            self.direction = random.choice([-1, 1])
        self.speed = speed
        self.untilStep = 1/self.speed
            
    def nextUpdate(self, sim):
        return self.untilStep
        
    def update(self, sim):
        """
        Checks collisions and prompts steps if needed.

        Notes
        -----
        When subclassing, remember that ``super().update`` does the
        householding with `Simulation` for you (plus possibly other things).
        """
        self.checkCollisions(sim, relative_position=self.direction)
        
        self.untilStep -= sim.time - self.lastUpdate
        if self.untilStep < 1e10:
            self.step(sim)
            self.untilStep = 1/self.speed
            
        super().update(sim)
        
    def steppingrule(self, sim):
        """
        The stepping rule for this walker. See `steppingrules` for examples.

        Default behavior is to step only if the target spot is completely free,
        which is also implemented as `steppingrules.careful`.

        Parameters
        ----------
        sim : Simulation
            the current state of affairs

        Returns
        -------
        list or None
            if the step is to be taken, a list of actions to take before. If
            the step should not happen, ``None``.

        See also
        --------
        steppingrules
        """
        if len(sim.track[self.position+self.direction]) == 0:
            return []
        
    def step(self, sim):
        """
        Take a step, if possible (listens to `steppingrule`)
        """
        # Check whether we can move
        actions = self.steppingrule(sim)
        if actions is None:
            return

        # OK, so do pre-processing
        for action in actions:
            action(sim)

        # Take the actual step
        try:
            sim.track[self.position].remove(self)
        except:
            if self.position < 0 or self.position >= len(sim.track):
                raise RuntimeError("{} left the track at t={}. Set up your simulation such that particles are contained.".format(self, sim.time))
            else:
                raise RuntimeError("Missing a {} on the track. This is likely an internal bug.".format(type(self)))
        self.position += self.direction
        sim.track[self.position].add(self)

class MultiHeadParticle(Loadable, Reportable):
    """
    Base class for particles with multiple 'heads' on the track

    Note that the `MultiHeadParticle` itself does not live on the track, and
    therefore also is not `Updateable`. It's individual heads should be
    `Particles <Particle>`, i.e. those will be updated. The purpose of
    `MultiHeadParticle` is just to coordinate loading and reporting of these
    heads.

    Attributes
    ----------
    heads : list of Particle
        the individual heads of the particle

    Parameters
    ----------
    iterable : iterable of `Particle` objects, optional
        the particles to tie together in this object. Instead of specifying at
        initialization, you can also edit `MultiHeadParticle.heads` yourself.
    """
    def __init__(self, iterable=None):
        if iterable:
            self.heads = list(iterable)
        else:
            self.heads = []

    def load(self, sim):
        Loadable.load(self, sim)

        for head in self.heads:
            head.load(sim)
            sim.reporter.unregister(head)

    def unload(self, sim):
        sim.reporter.unregister(self)
        for head in self.heads:
            head.unload(sim)

    def report(self):
        return tuple(head.position for head in self.heads)
