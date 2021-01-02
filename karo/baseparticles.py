"""
Base classes for particles one might want to simulate

The absolute base is `Particle` which on its own would basically sit on the
track and do nothing (which is exactly the behavior we need for a `Boundary`).
There is also a `Walker`, i.e. a particle that regularly takes steps in a
persistent direction. `Walker` also provides some examples for collisions.
These could be used as follows, assuming we are using a `Collider` named
``mycoll``:
>>> class ReflectedWalker(Walker):
...     pass
... mycoll.register(ReflectedWalker, Particle, Walker.collide_reflect)
...
... class Cleaner(Walker):
...     # Don't get fazed by anything except Boundaries
...     def shouldStep(self, sim):
...         return not any(isinstance(p, Boundary) for p in sim.track[self.position+self.direction])
... mycoll.register(Cleaner, Particle, Walker.collide_kickOff)

Randomness where needed is generated from python's `!random` module, so this
should be seeded for reproducible results.
"""

import random
from .framework import Updateable, Reportable, Loadable

class Particle(Updateable, Reportable, Loadable):
    """
    Base class for particles living on the track

    Attributes
    ----------
    position : int, optional
        my position on the track. Set at (or after) initialization to load at
        that position. If not specified, a position will be chosen at random at
        `load` time.
    """
    def __init__(self, position=None):
        self.position = position
    
    def report(self):
        return self.position
    
    def load(self, sim):
        """
        Load the particle into a simulation

        Parameters
        ----------
        sim : Simulation
            the current simulation

        Notes
        -----
        Since the 'bookkeeping' things (like inserting into the update queue)
        are already taken care of by the superclass `Loadable`, here we can
        focus on the `Particle` specific stuff, i.e. loading onto the track.
        """
        Loadable.load(self, sim) # super() might be confusing with multiple inheritance
        
        if self.position is None:
            possible_positions = [i for i, pos in enumerate(sim.track) if len(pos) == 0]
            self.position = random.choice(possible_positions)
                
        sim.track[self.position].append(self)
    
    def checkCollisions(self, sim, relative_position=0):
        """
        Process collisions with my neighbors

        Parameters
        ----------
        sim : Simulation
            the current simulation
        relative_position : int, optional
            the position relative to my own that should be checked for
            collisions. Could be e.g. ``+1`` for right neighbors, ``-1`` for
            left neighbors, etc.
        """
        for other in sim.track[self.position+relative_position]:
            if relative_position == 0 and other is self:
                continue
            sim.collider.execute(self, other, sim)
            sim.collider.execute(other, self, sim)
            other.update(sim)
            
class Boundary(Particle):
    """
    Stationary particle that can serve as boundary
    """
    pass
        
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
    This class provides a few ``collide_...`` methods that can be used to set
    up collision rules for subclasses. Note that for all collision rules shown
    here we explicitly check whether there actually is a collision. This is
    because a directional particle probably only cares about things that happen
    in front of it, not about whether it is bumped by something from behind (in
    which case the collision rules of course also have to apply).

    A moving particle needs one rule in addition to the collision rules, namely
    when to take a step. This behavior can be adjusted by overriding
    `shouldStep`.
    """
    def __init__(self, speed=1, direction=None, **kwargs):
        super().__init__(**kwargs)
        self.direction = direction
        if self.direction is None:
            self.direction = random.choice([-1, 1])
        self.speed = speed
        self.untilStep = 1/self.speed
            
    def nextUpdate(self):
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
        
    def shouldStep(self, sim):
        """
        Whether the current state of affairs allows to take a step

        Default behavior is to step only if the target spot is completely free.

        Parameters
        ----------
        sim : Simulation
            the current state of affairs

        Returns
        -------
        bool
        """
        return len(sim.track[self.position + self.direction]) == 0
        
    def step(self, sim):
        """
        Take a step, if possible (listens to `shouldStep`)
        """
        if self.shouldStep(sim):
            sim.track[self.position].remove(self)
            self.position += self.direction
            sim.track[self.position].append(self)

    ########## a few example collision handlers ###########
            
    def collide_reflect(self, particle, sim):
        """
        Reflect upon collision
        """
        if self.position+self.direction == particle.position:
            self.direction *= -1

    def collide_kickOff(self, particle, sim):
        """
        Kick off collision partner, unless it is a `Boundary`
        """
        if (not isinstance(particle, Boundary)) and self.position+self.direction == particle.position:
            sim.unload(particle)

    def collide_fallOff(self, particle, sim):
        """
        Fall off upon collision
        """
        if self.position+self.direction == particle.position:
            sim.unload(self)
