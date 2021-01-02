"""
The backbone of the library.

This module sets up the framework to run 1d simulations in a reasonably
straight forward manner. Overarching everything is the `Simulation` class. It
is the centralized storage for everything and actually runs the simulation.

Naturally there are many moving parts within the simulation, so there are a few
helper types to keep these organized:
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
      runtime. Examples include `UnloadingEvent` and `Reporter`.
    - the actual particles being simulated of course should have all of these
      capabilities. Consequently, `Particle` subclasses all three.

Next up, `Track` provides the playing field for the simulation. We use a
`BoundSafeList` (such that we can easily query neighbors etc., without having
to take care not to run out of bounds) whose entries are simple lists of
references to `Updateable` objects. It is thus possible to implement logics
where particles occupy the same space on the track. The main reason to subclass
`BoundSafeList` here is to provide the `Track.remove` method, which cleanly
removes an object from wherever it appears on the track. Ideally this would
only be used as a fallback, since it scales with system size; in principle,
objects should be able to keep track of their own references and delete them
when prompted to do so.

The `Collider` class is probably the central ingredient to the flexibility of
the framework. It stores the actions to take when things collide on the track,
and provides a method to resolve the collision logic, given the data types of
the two colliding particles. Note that this resolution is such that **all**
matching actions are executed, i.e. if a "moving particle" collides with a
"boundary particle", the collider will execute the rules for ``moving particle
<--> boundary particle``, ``particle <--> boundary particle``, ``moving
particle <--> particle``, and ``particle <--> particle``, as long as the
corresponding rules are specified, and assuming that "moving particle" as well
as "boundary particle" are subclasses of "particle".

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

from . import datastructures

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
    def nextUpdate(self):
        """
        Should return the time until the next update is necessary.
        """
        return float('inf')
    
    def queue(self, sim):
        sim.nextUpdates.insert(sim.time+self.nextUpdate(), self)
        
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
            sim.nextUpdates.insert(sim.time+self.nextUpdate(), self)
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
        sim.track.remove(self) # Doesn't raise
        try:
            sim.nextUpdates.removeData(self)
        except ValueError as err:
            pass
        try:
            sim.reporter.reportables.remove(self)
        except ValueError:
            pass
        
class UnloadingEvent(Updateable, Loadable):
    """
    Should be submitted to the simulation to unload any `Loadable`.

    Simply calling `Loadable.unload` during an update cycle might leave updates
    unfinished and break stuff. So better to treat this as a separate event.

    Parameters
    ----------
    ref : Loadable
        the object to unload

    Notes
    -----
    `Simulation.unload` is the preferred shorthand for this.

    See also
    --------
    Simulation.load, Simulation.unload

    Examples
    --------
    Assuming we have a `Simulation` ``sim`` and some ``particle`` that we need
    to get rid of (which is a subclass of `Loadable`):
    >>> sim.load(UnloadingEvent(particle))
    ... sim.unload(particle) # equivalent
    """
    def __init__(self, ref):
        self.ref = ref
        
    def nextUpdate(self):
        return 0
    
    def update(self, sim):
        self.ref.unload(sim)
        
        # Just in case
        self.unqueue(sim)
        
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
    Using the types from the particle library, we can build a simulation of
    "bouncy" particles confined to a finite track:
    >>> mycoll = Collider()
    ... mycoll.register(Walker, Particle, Walker.collide_reflect)
    ...
    ... sim = Simulation(L=100, collider=mycoll, dt=None) # event-based reporting
    ... sim.load(Boundary(0))
    ... sim.load(Boundary(len(sim.track)-1))
    ... for i in range(10):
    ...     sim.load(Walker(speed=np.pi**(i/10)))
    ... sim.run(50)

    Note that in an actual simulation setting where you might have other,
    non-reflecting walkers, you might want to subclass `Walker` to have a
    specific type that reflects off other particles:
    >>> class ReflectedWalker(Walker):
    ...     pass
    ... ### mycoll.register(Walker, Particle, Walker.collide_reflect)
    ... mycoll.register(ReflectedWalker, Particle, Walker.collide_reflect)

    """
    def __init__(self, L, collider=None, dt=None):
        self.time = 0
        self.track = Track(L)
        self.nextUpdates = OrderedLinkedList()
        
        if dt is None:
            self.reporter = EventBasedReporter()
        else:
            self.reporter = TimeBasedReporter(dt)
            self.load(self.reporter)
        
        self.collider = collider
        if self.collider is None:
            self.collider = Collider()
        
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
        This simply calls ``self.load(UnloadingEvent(loadable))``. Note
        however, that one should not call ``loadable.unload`` directly, as this
        might break the update cycle.

        See also
        --------
        load
        """
        self.load(UnloadingEvent(loadable))
            
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
        while self.time < T:
            self.time, updateable = self.nextUpdates.pop()
            updateable.update(self)
            
            if isinstance(self.reporter, EventBasedReporter):
                self.reporter.doReport(self)
        
###############################################################################

class Track(BoundSafeList):
    """
    The playing field of the simulation

    This class keeps track of the objects in the simulation in the way we also
    imagine them: as arranged on a linear track. This makes random access by
    location O(1). The track itself is a list of lists of references to said
    objects, such that an arbitrary number of objects can sit at the same
    position. An empty field is marked by an empty list of references, as
    expected. Consequently, it makes sense to simply return an empty list when
    indices outside the actual range of the track are queried. This is the
    behavior of `BoundSafeList`.

    Parameters
    ----------
    L : int
        total length of the track
    """
    def __init__(self, L):
        # Note: L*[[]] gives a list of length L where each entry is *the same* empty list
        super().__init__([[] for _ in range(L)], outOfBounds_value=[])
        
    def remove(self, value):
        """
        Remove a given reference from all of the positions it appears in.

        This function is only for fallback, ideally a particle would keep track
        of its own references and delete them upon unloading.  Only if
        performance is not crucial, this function might be easier

        Parameters
        ----------
        value : object
            the object to remove
        """
        for pos in self:
            try:
                while True:
                    pos.remove(value)
            except ValueError:
                pass
                
###############################################################################
                
class Collider:
    """
    Registry for collision behavior

    A collision rule consists of two types (the types of things colliding) and
    a function determining what happens. These functions are called "actions"
    and have the signature ``action(obj0, obj1, sim) -> None``. Collision rules
    are added with `register`. When assembling the full collision for two given
    types (c.f. `get`), all appropriate rules are applied, i.e. all rules
    applying to either the specific types given or any of their superclasses.

    Notes
    -----
    While the treatment of actions in this class is deliberately symmetric, it
    practice one often wants to define the collision behavior as a class
    method. For this case, note that for ``obj = Class()``, the two calls
    ``obj.method(args)`` and ``Class.method(obj, args)`` are equivalent, such
    that you could ``register(Class, other_Class, Class.method)``.
    """
    def __init__(self):
        self.registry = dict()
        
    def register(self, type0, type1, action):
        """
        Create a new collision rule

        Parameters
        ----------
        type0, type1 : type
            the types to apply the rule to
        action : callable
            the action to take. Will be called as ``action(obj0, obj1, sim)``

        Notes
        -----
        Rules are always symmetrized, i.e. it does not matter whether you
        register ``(type0, type1, action)`` or ``(type1, type0, action_swap)``.
        Note however that ``action is always called with the correct type
        order, i.e. registering ``(type0, type1, action)`` will always result
        in the call ``action(obj_of_type0, obj_of_type1, sim)``.
        """
        self.registry[(type0, type1)] = action
        
    def get(self, type0, type1):
        """
        Assemble full collision rule for a given pair of types (or objects)

        Parameters
        ----------
        type0, type1 : type or object
            if these are objects, those object's type will be used.

        Returns
        -------
        callable
            the action to take when these two types collide (taking into
            account inherited actions).

        See also
        --------
        execute
        """
        if not isinstance(type0, type):
            type0 = type(type0)
        if not isinstance(type1, type):
            type1 = type(type1)
            
        actions = []
        type_order_correct = []
        for coltypes in self.registry:
            if issubclass(type0, coltypes[0]) and issubclass(type1, coltypes[1]):
                actions.append(self.registry[coltypes])
                type_order_correct.append(True)
            elif issubclass(type0, coltypes[1]) and issubclass(type1, coltypes[0]):
                actions.append(self.registry[coltypes])
                type_order_correct.append(False)
                
        def fullCollision(p1, p2, sim):
            for action, order_correct in zip(actions, type_order_correct):
                if order_correct:
                    action(p1, p2, sim)
                else:
                    action(p2, p1, sim)
                
        return fullCollision
    
    def execute(self, obj0, obj1, sim):
        """
        Execute collision for two objects

        Parameters
        ----------
        obj0, obj1 : object
            the objects to collide
        sim : Simulation
            the current simulation, for context

        Notes
        -----
        This is simply a shorthand for ``self.get(type(obj0), type(obj1))(obj0,
        obj1, sim)``.

        See also
        --------
        get
        """
        self.get(type(obj0), type(obj1))(obj0, obj1, sim)
        
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
    def __init__(self, dt=None):
        self.dt = dt
        self.nextReport = 0
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
    """
    def __init__(self, dt):
        super().__init__()
        self.dt = dt
        self.nextReport = 0 # report initial conditions

    def nextUpdate(self):
        return self.nextReport
            
    def update(self, sim):
        self.nextReport -= sim.time - self.lastUpdate
        if self.nextReport < 1e10:
            self.doReport(sim)
            self.nextReport = self.dt
            
        Updateable.update(self, sim) # Housekeeping (update to-do and keep track of lastUpdate)

################################################################################
# Probably just for development

from matplotlib import pyplot as plt
import numpy as np

def showSim(reporter_out, colors):
    """
    Plot a visualization of the simulation

    This is pretty slow, because it uses ``plt.scatter``. Maybe there are
    better things we could do.

    Assumes that anything reported is a position.

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
            pos = np.asarray(report[curtype]).flatten()
            plt.scatter(report['time']*np.ones(len(pos)), pos)
