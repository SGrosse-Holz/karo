"""
Types for simulation constituents.

The simulation needs a few things with different combinations of some basic
capabilities. This module contains base classes for these:
    - `Loadable` objects can be added to the simulation using their `load
      <Loadable.load>` function, or equivalently `Simulation.load`. This does
      not mean that they actually have to show up anywhere in the simulation;
      they could also just register (parts of) themselves for reporting or
      updating, such as for example the `Reporter`.
    - `Reportable` objects can produce a summary of themselves for simulation
      output. For a simple particle, this would probably just be the position
      (i.e. simply a float), but in principle this could be anything.
    - `Updateable` objects are those that actually interact when the simulation
      is running. They provide information on when they have to be updated
      next, and a function to do so. For convenience, the base class also
      defines a few functions to interact with the simulation's update queue.
      Note that these do not necessarily have to be objects of the simulation
      logic, but simply represent anything that needs action at simulation
      runtime. Examples include `Event` and `Reporter`.
    - `Events <Event>` can be submitted to the simulation's update queue to
      execute arbitrary tasks at a specified time. They are mainly used for
      unloading of things, since its better to do this in a separate step, than
      in the middle of an update cycle.
    - `Particles <Particle>` are the things that live on the track, i.e. the
      "actual particles being simulated". See `baseparticles` for some usage
      patterns, and consult the example script for examples of concrete
      Particle implementations.
"""

import random

class Updateable:
    """
    Base class for anything that needs action at simulation runtime

    Attributes
    ----------
    lastUpdate : float
        time of the last call to `update`. Is updated by `update`, so make sure
        to either call ``super().update(sim)`` or do ``self.lastUpdate =
        sim.time`` when subclassing and overriding `update`.
    """
    def nextUpdate(self, sim):
        """
        Should return the time until the next update is necessary.

        Parameters
        ----------
        sim : Simulation
            the current simulation, for context
        """
        return float('inf')
    
    def queue(self, sim):
        sim.nextUpdates.insert(sim.time+self.nextUpdate(sim), self)
        
    def unqueue(self, sim):
        try:
            sim.nextUpdates.removeData(self)
        except ValueError:
            pass
        
    def requeue(self, sim):
        self.unqueue(sim)
        self.queue(sim)
    
    def update(self, sim):
        """
        Bring the object up to date.

        Parameters
        ----------
        sim : Simulation
            the current simulation

        Notes
        -----
         - this might be called earlier than the time requested by
           `nextUpdate`, so should not rely on getting a beat from there.
           Simply check the current state of the simulation and do whatever
           needs to be done.
         - you should make sure to `queue` (or, safer, `requeue`) yourself if
           you want to be updated in the future.
        """
        self.requeue(sim)           # Update the to-do list in the simulation
        self.lastUpdate = sim.time  # Remember last update
    
class Reportable:
    """
    Base class for anything that can talk to a reporter
    """
    def report(self):
        """
        Should return useful information to be stored in the report
        """
        return None
    
class Loadable:
    """
    Base class for anything that is loaded into the simulation as one piece.
    """
    def load(self, sim):
        """
        Load stuff into the simulation

        Parameters
        ----------
        sim : Simulation
            the current simulation

        Notes
        -----
        Things to do here:
         - `insert <OrderedLinkedList.insert>` `Updateable` things to ``sim.nextUpdates``
         - `register <Reporter.register>` `Reportable` things with ``sim.reporter``
         - put things on ``sim.track`` and generally do any initialization that
           depends on the simulation
        """
        if isinstance(self, Updateable):
            sim.nextUpdates.insert(sim.time+self.nextUpdate(sim), self)
            self.lastUpdate = sim.time
        if isinstance(self, Reportable):
            sim.reporter.register(self)
    
    def unload(self, sim):
        """
        Remove yourself from the simulation.

        The implementation here is a fallback that should be rigorous, but
        might be slow.

        Parameters
        ----------
        sim : Simulation
            the current simulation
        """
        sim.track.remove(self)
        sim.reporter.unregister(self)
        try:
            while True:
                sim.nextUpdates.removeData(self)
        except ValueError as err:
            pass

class Event(Updateable, Loadable):
    """
    Can be submitted to a simulation to do things in a timed way

    Parameters
    ----------
    action : callable
        what to do when called. Should have signature ``action(sim) -> None``
        where ``sim`` is the current `Simulation`.
    remaining_time : float, optional
        the time until the action is to be taken. By default, events are queued
        for immediate execution.

    Examples
    --------
    Unloading any `Loadable` from the simulation should happen via events.
    Assuming we want to unload some ``particle`` (instance of `Loadable`) from
    the `Simulation` ``sim``:
    >>> sim.load(Event(particle.unload))
    ... sim.unload(particle) # For the special case of unloading things, there is a shortcut.
    """
    def __init__(self, action, remaining_time=0):
        self.action = action
        self.countdown = remaining_time
        
    def nextUpdate(self, sim):
        return self.countdown
    
    def update(self, sim):
        self.countdown -= sim.time - self.lastUpdate
        if self.countdown <= 0:
            self.action(sim)
            self.unqueue(sim)
        self.lastUpdate = sim.time
        
class Particle(Updateable, Reportable, Loadable):
    """
    Base class for particles living on the track

    Attributes
    ----------
    position : int, optional
        my position on the track. Set at (or after) initialization to load at
        that position. If not specified, a position will be chosen at random at
        `load` time.

    Examples
    --------
    One way to set up a `Particle` with a finite lifetime would be to submit a
    timed `Event` when the particle loads:
    >>> class FiniteLifeParticle(Particle):
    ...     def load(self, sim):
    ...         super().load(sim)
    ...         sim.load(Event(self.unload, random.expovariate(10)))

    Alternatively, if you want the option of changing the life time
    mid-simulation, you can implement it as a separate counter:
    >>> class FiniteMutableLifeParticle(Particle):
    ...     def __init__(self, lifetime=float('inf'), **kwargs):
    ...         super().__init__(**kwargs)
    ...         self.lifetime = lifetime
    ...
    ...     def nextUpdate(self, sim):
    ...         return min(self.lifetime, super().nextUpdate(sim))
    ...
    ...     def update(self, sim):
    ...         self.lifetime -= sim.time - self.lastUpdate
    ...         if self.lifetime < 1e-10: # small positive threshold for numerical safety
    ...             sim.load(Event(self.unload))
    ...
    ...         super().update(sim)

    Note that in an actual use case (for both implementations), you might want
    to also modify `unload` to submit a loading `Event` for a new particle.

    Edit: by now, exactly the second implementation exists as
    `baseparticles.FiniteLife`. Note that this doesn't even have to be a
    `Particle`, it just has to be `Updateable` and `Loadable`.
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
        others = sim.track[self.position+relative_position]
        for other in others:
            if relative_position == 0 and other is self:
                continue
            sim.collider.newCollision(self, other, sim)

        sim.collider.execute(sim)
