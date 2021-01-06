"""
This module provides a library of particle types that might be useful

Note that these should be seen more as examples than definitive implementations
of general patterns (those would go into `baseparticles`). This is because with
this module we get to the limits of the rule-agnostic approach, i.e. there are
many slightly different ways to implement e.g. a random walker, and depending
on use case you might prefer one or the other. Therefore, while the particles
in this library can also serve as actual base classes for a simulation, the
main purpose of the module is to give inspiration.

Examples
--------
Since the types in this module are intended as implementation inspirations,
being able to see the implementation is important. A useful tool here is
python's `!inspect` module:
>>> from karo.particles import RandomWalker
... import inspect
... print(inspect.getsource(RandomWalker)
"""
# Note: particles.py is exempt from unit testing, since it serves more as code
#       examples than functional library code.

from .baseparticles import *

class RandomWalker(Walker):
    """
    A random walker

    Attributes
    ----------
    p_forward : float in [0, 1]
        probability that the next step is aligned with ``self.direction``
        (which is inherited from `Walker`).

    Notes
    -----
    This implementation of the `RandomWalker` is "backward-conscious", i.e.
    while `Walker` checks for collisions only in the direction of motion, this
    random walker also checks behind it. This makes sense, because it might
    step backwards. On the other hand, omitting the backwards collision check
    can also be useful if you actually want the particle to pay attention to
    only one direction.
    """
    def __init__(self, p_forward=0.5, **kwargs):
        super().__init__(**kwargs)
        self.p_forward = p_forward

    def update(self, sim):
        # Only thing we have to do is to prepend the check for backwards
        # collisions, everything else is the same as for a Walker.
        self.checkCollisions(sim, relative_position=-self.direction)
        super().update(sim)

    def step(self, sim):
        old_dir = self.direction
        if random.random() >= self.p_forward:
            self.direction = -self.direction
        super().step(sim)
        self.direction = old_dir

class VariableWalker(Walker):
    """
    Useful, if you want a particle to slow down upon collision

    The idea for this particle came from a desire to model a collision, where
    the "strong" particle pushes everything else, but slows down because of the
    added load.

    Notes
    -----
    This implementation goes back to its original speed as soon as the pushed
    particle leaves. One could of course do this differently.

    The "slowdown" collision rules require this class' `!free_speed` attribute.

    Examples
    --------
    Assume we register collisions with ``mycollider``.
    >>> class weakPusher(VariableWalker):
    ...     steppingrule = karo.steppingrules.pushy_train
    ... # Slow down by a factor of 2 upon collision with anything else
    ... mycollider.register(weakPusher, Particle, VariableWalker.slowdown(2))
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.free_speed = self.speed

    def update(self, sim):
        self.speed = self.free_speed # try to get back to speed
        super().update(sim)

    @staticmethod
    def slowdown(factor):
        """
        A collision rule factory for slowdown collisions

        Parameters
        ----------
        factor : float
            the factor by which to slow down upon collision

        Returns
        -------
        callable
            a collision rule, where the first argument slows down by the given
            factor
        """
        def collision(self, other, sim):
            if self.position + self.direction == other.position:
                def action(sim): self.speed = self.free_speed/factor
                return [action]
            return []

        return collision
