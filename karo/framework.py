"""
The backbone of the library.

This module sets up the framework to run 1d simulations in a reasonably
straight forward manner. Overarching everything is the `Simulation` class. It
is the centralized storage for everything and actually runs the simulation.

Naturally there are many moving parts within the simulation, so there are a few
helper types to keep these organized. These helper types are collected in the
`constituents` module. It includes base classes for `Updateable` things,
`Reportable` ones, `Particles <Particle>`, `Events <Event>`, etc. I would
recommend reading its docstring now.

Continuing with the contents of this module, `Track` provides the playing field
for the simulation. We use a `BoundSafeList` (such that we can easily query
neighbors etc., without having to take care not to run out of bounds) whose
entries are simple lists of references to `Updateable` objects. It is thus
possible to implement logics where particles occupy the same space on the
track. The main reason to subclass `BoundSafeList` here is to provide the
`Track.remove` method, which cleanly removes an object from wherever it appears
on the track. Ideally this would only be used as a fallback, since it scales
with system size; in principle, objects should be able to keep track of their
own references and delete them when prompted to do so.

The `Collider` class is probably the central ingredient to the flexibility of
the framework. It stores the actions to take when things collide on the track,
and provides a method to resolve the collision logic, given the two colliding
particles. Note that this resolution is such that **all** matching rules apply,
i.e. if a `Walker` collides with a `Boundary` (both of which are subclasses of
`Particle`), the collider will execute the rules for ``Walker <--> Boundary``,
``Particle <--> Boundary``, ``Walker <--> Particle``, and ``Particle <-->
Particle``, as long as the corresponding rules are specified. For more details,
see the `collisionrules` submodule.

Finally, the `Reporter` class keeps track of the generated data. Objects that
should be included in the report have to be registered with the reporter; this
is done automatically by `Loadable.load`, as long as the `Loadable` object is
also `Reportable`. Note that there are two modes of reporting: event-based,
i.e. report whenever anything changes, or (because this might produce a lot of
unnecessary data) time-based, i.e. report at fixed time intervals. `Simulation`
chooses the right type of reporting based on the `!dt` argument to its
constructor. Set this to some number for regular reporting at that time
interval, or to ``None`` for event-based reporting. Note that at runtime, the
simulation will notify the reporter about events, if it is an instance of
`EventBasedReporter`. Thus, if you want to write your own event-based reporter,
subclass this one.
"""

import random
from copy import deepcopy

from . import datastructures
from .constituents import *
from .baseparticles import TrackEnd

###############################################################################

class Simulation:
    """
    Contains all structure and the main loop.

    Parameters
    ----------
    L : int
        total length of the track that everything runs on
    collider : Collider, optional
        the collection of collision rules
    dt : float, optional
        reporting time step. Set to ``None`` (default) to report all events
        whenever they happen.
    markEnds : bool, optional
        whether to put `TrackEnd` markers at the first and last positions of
        the track. These will (usually) prevent things from falling off the
        track.

    Attributes
    ----------
    time : float
        absolute simulation time
    nextUpdates : OrderedLinkedList
        the update queue. 
    track : Track
        the track everything lives on
    reporter : Reporter
        reporter reports things
    collider : Collider
        collider collides things

    Notes
    -----
    `nextUpdates` is kept in absolute simulation time, while
    `Updateable.update` returns time until next event. The queue could be kept
    in relative time (i.e.  storing time until the requested update, instead of
    the absolute time when that update should happen) using
    `OrderedLinkedList.movet`, but that function is O(n), so probably not worth
    the effort.

    Examples
    --------
    Using the particles defined in the `baseparticles` module, we can setup a
    small simulation of "bouncy" particles:
    >>> sim = Simulation(L=100, dt=None) # event-based reporting
    ... for i in range(10):
    ...     sim.load(Walker(speed=np.pi**(i/10)))
    ... sim.collider.register(Walker, Particle, collisionrules.reflect)
    ... sim.run(50)

    Note that in an actual simulation setting where you might have other,
    non-reflecting walkers, you might want to subclass `Walker` to have a
    specific type that reflects off other particles:
    >>> class GummyBear(Walker):
    ...     pass
    ... ### sim.collider.register(Walker, Particle, collisionrules.reflect)
    ... sim.collider.register(GummyBear, Particle, collisionrules.reflect)

    """
    def __init__(self, L, collider=None, dt=None, markEnds=True):
        self.time = 0
        self.track = Track(L)
        self.nextUpdates = datastructures.OrderedLinkedList()
        
        if dt is None:
            self.reporter = EventBasedReporter()
        else:
            self.reporter = TimeBasedReporter(dt)
            self.load(self.reporter)
        
        self.collider = collider
        if self.collider is None:
            self.collider = Collider()

        if markEnds:
            self.load(TrackEnd(0))
            self.load(TrackEnd(L-1))
        
    def load(self, loadable):
        """
        Load an object into the simulation

        Parameters
        ----------
        loadable : Loadable
            the thing to load

        Notes
        -----
        This is literally just calling ``loadable.load(self)``. It mostly
        exists for conceptual reasons, and symmetry with `unload`.

        See also
        --------
        unload
        """
        loadable.load(self)
        
    def unload(self, loadable):
        """
        Queue an object for unloading from the simulation

        Parameters
        ----------
        loadable : Loadable
            the thing to kill

        Notes
        -----
        This simply calls ``self.load(Event(loadable))``. Note however, that
        one should not call ``loadable.unload`` directly, as this might break
        the update cycle.

        See also
        --------
        load
        """
        self.load(Event(loadable.unload))
            
    def run(self, T):
        """
        Actually run the simulation for some time T.

        This function really just iterates through the `nextUpdates` and
        `updates <Updateable.update>` accordingly. Plus reporting, if
        event-based.

        Data from the simulation will be in ``self.reporter`` afterwards.

        Parameters
        ----------
        T : float
            maximum time to run for
        """
        T += self.time # self.time is absolute time
        running = True
        try:
            while running:
                self.time, updateable = self.nextUpdates.pop()
                if self.time > T:
                    self.time = T
                    running = False

                updateable.update(self)
                
                if isinstance(self.reporter, EventBasedReporter):
                    self.reporter.doReport(self)
        except datastructures.EmptyList: # self.nextUpdates is empty, i.e. there's nothing left to do
            pass
        
###############################################################################

class Track(datastructures.BoundSafeList):
    """
    The playing field of the simulation

    This class keeps track of the objects in the simulation in the way we also
    imagine them: as arranged on a linear track. This makes random access by
    location O(1). The track itself is a list of sets of references to said
    objects, such that an arbitrary number of objects can sit (unordered) at
    the same position. An empty field is marked by an empty set of references,
    as expected. Consequently, it makes sense to simply return an empty set
    when indices outside the actual range of the track are queried. This is the
    behavior of `BoundSafeList`.

    Parameters
    ----------
    L : int
        total length of the track
    """
    def __init__(self, L):
        # Note: L*[set()] gives a list of length L where each entry is *the same* empty set
        super().__init__([set() for _ in range(L)], outOfBounds_value=set())
        
    def remove(self, value):
        """
        Remove the specified object.

        Parameters
        ----------
        value : object
            the object to remove

        Notes
        -----
        We have to override list's ``remove()``, because that would remove a
        track space, instead of an item in that space.

        This will remove only the first occurence of `value`. Particles should
        not occur in multiple places on the track. See
        `baseparticles.MultiHeadParticle` for a way to implement something that
        interacts with the track in multiple places (spoiler: have each
        interaction point be a `Particle` and just tie them together in
        some overarching object).
        """
        for pos in self:
            try:
                pos.remove(value)
            except KeyError:
                continue

    def nextEmpty(self, start, direction):
        """
        Find index of next empty space on the track

        This is useful for detecting/processing "trains" of stuff, i.e. if
        there is one particle pushing five others in front of it. In this case,
        this function would quickly give the end of this train.

        Parameters
        ----------
        start : int
            the start of the train, i.e. where to start looking
        direction : {-1, 1}
            in which direction to advance

        Returns
        -------
        int
            the index of the first empty space found in the given direction
        """
        pos = start
        while len(self[pos]) > 0:
            pos += direction
        return pos

    def aggregate(self, positions):
        """
        Get a union of all the given positions

        Parameters
        ----------
        positions : iterable
            the positions 

        Examples
        --------
        Check whether some stretch of ``track`` contains a given particle type:
        >>> if any(isinstance(p, Boundary) for p in track.aggregate(range(5, 20))):
        ...     print("There's a Boundary somewhere in the stretch [5, 20)")
        """
        return set().union(*(self[i] for i in positions))
                
###############################################################################
                
class Collider:
    """
    Registry for collision rules

    For a definition of "collision rule", see `collisionrules`.

    By registering a collision rule you specify that this rule should apply, if
    the two objects in question are of the given types. Note that a rule also
    applies to all subclasses.
    """
    def __init__(self):
        self.registry = dict()
        self.nextActions = []
        
    def register(self, type0, type1, rule):
        """
        Register a new collision rule

        Parameters
        ----------
        type0, type1 : type or list of types
            the types to which the rule should apply. Can be lists to indicate
            multiple types at once. If both are lists, rules for their
            cartesian product will be registered.
        rule : callable or list of such
            the rule to apply. Should have signature ``rule(obj0, obj1, sim) ->
            list of actions``, where ``action(sim) -> None`` implements the
            actual actions to take under this rule. Can also be a list of
            rules.

        Notes
        -----
        Rules are always symmetrized, i.e. it does not matter whether you
        register ``(type0, type1, rule)`` or ``(type1, type0, rule_swap)``.
        Note however that ``rule`` is always called with the correct type
        order, i.e. registering ``(type0, type1, rule)`` will always result
        in the call ``rule(obj_of_type0, obj_of_type1, sim)``.
        """
        # Resolve lists recursively
        if isinstance(type0, list):
            for t in type0:
                self.register(t, type1, rule)
            return
        if isinstance(type1, list):
            for t in type1:
                self.register(type0, t, rule)
            return

        # Assemble rule, if it needs assembling
        if isinstance(rule, list):
            def concatRule(obj0, obj1, sim):
                actions = []
                for subrule in rule:
                    actions += subrule(obj0, obj1, sim)
                return actions
            rule = concatRule

        # Finally, actually register
        self.registry[(type0, type1)] = rule
        if not type0 is type1:
            self.registry[(type1, type0)] = lambda obj1, obj0, sim : rule(obj0, obj1, sim)
        # if the two types are identical, the symmetrization has to happen
        # explicitly at runtime. See newCollision.

    def newCollision(self, obj0, obj1, sim):
        """
        Process collision and append necessary actions to to-do list.

        Parameters
        ----------
        obj0, obj1 : objects
            the objects undergoing collision
        sim : Simulation
            the current simulation, for context

        Notes
        -----
        This function only runs through all the rules appropriate to the two
        input objects, but does not yet execute anything, such that you can
        first process more collisions, before changing the simulation state.
        Once all rules are applied, call `execute` to run all the accumulated
        actions.

        See also
        --------
        execute
        """
        for type0, type1 in self.registry:
            if isinstance(obj0, type0) and isinstance(obj1, type1):
                self.nextActions += self.registry[(type0, type1)](obj0, obj1, sim)
                if type0 is type1:
                    self.nextActions += self.registry[(type1, type0)](obj1, obj0, sim)

    def execute(self, sim):
        """
        Execute all actions accumulated since last call

        Parameters
        ----------
        sim : Simulation
            the current simulation, for context
        """
        try:
            while True:
                self.nextActions.pop()(sim)
        except IndexError:
            pass
        
###############################################################################

class Reporter:
    """
    Base class for reporting of simulation data

    Attributes
    ----------
    out : list of dict
        each entry in the list is a report. Each report has a key 'time',
        giving the absolute simulation time at which the report was generated.
        The other keys are the types of objects that reported, each entry then
        being a list of those individual reports (e.g. a list of positions for
        a simple particle).

    See also
    --------
    EventBasedReporter, TimeBasedReporter
    """
    def __init__(self):
        self.reportables = []
        self.out = []
        
    def register(self, reportable):
        """
        Register an object for reporting

        Parameters
        ----------
        reportable : Reportable
            reportable to be reported in reports
        """
        if reportable not in self.reportables:
            self.reportables.append(reportable)

    def unregister(self, reportable):
        """
        Remove an object from reporting

        Parameters
        ----------
        reportable : Reportable
            the object that should not appear in the reports
        """
        try:
            while True:
                self.reportables.remove(reportable)
        except ValueError:
            pass
        
    def doReport(self, sim):
        """
        Save a report of the current state of the simulation

        Parameters
        ----------
        sim : Simulation
            current simulation, for context
        """
        report = {'time' : sim.time}
        for reportable in self.reportables:
            curtype = type(reportable)
            if curtype not in report.keys():
                report[curtype] = []
            report[curtype].append(reportable.report())
        self.out.append(report)

    def resample(self, discretization=1, **kwargs):
        """
        Resample my reports and return a corresponding `TimeBasedReporter`.

        All input not listed below will be forwarded to the constructor of the
        returned `TimeBasedReporter`.

        Parameters
        ----------
        discretization : tuple or float, optional
            how to discretize. If this is a float, it will simply be the time
            step and all the data in `self` will be discretized, starting
            at the first time point. If it is a tuple, it should be ``(start,
            stop, step)``, where all but ``step`` can be ``None`` to indicate
            maximal extent. Python style, we will report everything within the
            half-open ``[start, stop)``.

        See also
        --------
        TimeBasedReporter
        """
        if isinstance(discretization, (float, int)):
            discretization = (None, None, discretization)
        if not (isinstance(discretization, tuple) and len(discretization) == 3) or discretization[2] is None:
            raise ValueError("Did not understand 'discretization' argument: {}".format(str(discretization)))
        start, stop, step = discretization
        if start is None:
            start = self.out[0]['time']
        if stop is None:
            stop = self.out[-1]['time'] + step

        # Once all Nones are resolved, we know all the time points that should
        # appear in the output reporter (i.e. those do not depend on the data
        # anymore)
        def dt_gen(start, stop, step):
            cur = start
            while cur < stop:
                yield cur
                cur += step

        # Assemble output
        timebased = TimeBasedReporter(step, **kwargs)
        i_report = -1
        for reporttime in dt_gen(start, stop, step):
            while i_report+1 < len(self.out) and self.out[i_report+1]['time'] <= reporttime + timebased.offset:
                i_report += 1

            rep = deepcopy(self.out[i_report])
            rep['time'] = reporttime
            timebased.out.append(rep)

        # Fix up timebased to actually look like a Reporter that was used for
        # simulation. Probably this is useless beautification, but you never
        # know what people get up to. (If we return a Reporter, it should
        # really be a valid one, not just a container for out)
        timebased.reportables = self.reportables.copy() # Top-level copy only, i.e. exactly what we need here
        timebased.nextReport = step
        timebased.lastUpdate = timebased.out[-1]['time'] + timebased.offset
        return timebased

class EventBasedReporter(Reporter):
    """
    Event-based reporter

    If `Simulation.reporter` is of this type, it will be asked to `doReport`
    after each update step of the simulation.
    """
    pass

class TimeBasedReporter(Reporter, Updateable, Loadable):
    """
    Time-based reporter

    Reporters of this type should be loaded into the event queue of a
    `Simulation` and will then produce reports regularly.

    Parameters
    ----------
    dt : float
        time interval between two reports
    offset : float, optional
        by how much to offset the reporting times from integer multiples of
        `!dt`. This is useful when running simulations in discrete time,
        because with a slight offset, the simulation can update at integer
        multiples of `!dt`, then will be reported. Note that the offset will be
        removed from the reported times, i.e. ultimately the report stating it
        happened at a time ``t`` will be generated from the simulation at time
        ``t+offset``.
    """
    def __init__(self, dt, offset=1e-5):
        super().__init__()
        self.dt = dt
        self.offset = offset
        self.nextReport = offset # report initial conditions

    def nextUpdate(self, sim):
        return self.nextReport
            
    def update(self, sim):
        self.nextReport -= sim.time - self.lastUpdate
        if self.nextReport < 1e-10:
            self.doReport(sim)
            self.nextReport += self.dt
            
        Updateable.update(self, sim) # Housekeeping (update to-do and keep track of lastUpdate)

    def doReport(self, sim):
        Reporter.doReport(self, sim)
        self.out[-1]['time'] -= self.offset

################################################################################
# Probably just for development

from matplotlib import pyplot as plt
import numpy as np

def showSim(reporter_out, colors, **kwargs):
    """
    Plot a visualization of the simulation

    This is pretty slow, because it uses ``plt.scatter``. Maybe there are
    better things we could do.

    Assumes that anything reported is a position.

    kwargs will be forwarded to `!plt.scatter`.

    Parameters
    ----------
    reporter_out : list of dict
        the report list from the simulation, i.e. ``sim.reporter.out``.
    colors : dict
        determines what particle gets which colors. Keys should be particle
        types, values the (to be) associated colors, in any format that
        `!pyplot` understands. Types have to match exactly, any type that does
        not appear here will be drawn in black.
    """
    for report in reporter_out:
        for curtype in report:
            if type(curtype) is not type:
                continue
            pos = np.asarray(report[curtype]).flatten()
            try:
                color = colors[curtype]
            except KeyError:
                color = 'black'
            plt.scatter(report['time']*np.ones(len(pos)), pos, color=color, **kwargs)
