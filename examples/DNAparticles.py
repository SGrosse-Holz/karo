"""
Example implementation of DNA bound particles like cohesin, CTCF, RNAP.
"""
import random

import karo
from karo.particles import *

################################################################################

class CohesinLeg(Walker):
    def __init__(self, parent, **kwargs):
        self.parent = parent # Keep track of where I belong
        super().__init__(**kwargs)

class Cohesin(MultiHeadParticle, FiniteLife):
    # Note that since MultiHeadParticle is not Updateable, and FiniteLife
    # overrides only the Updateable methods, we don't have to explicitly take
    # care of their interaction
    def __init__(self, meanlife=float('inf'), **kwargs):
        self.meanlife = meanlife
        if self.meanlife < float('inf'):
            mylifetime = random.expovariate(1/self.meanlife)
        else:
            mylifetime = float('inf')

        FiniteLife.__init__(self, lifetime=mylifetime)
        MultiHeadParticle.__init__(self, [CohesinLeg(self, direction=-1, **kwargs), CohesinLeg(self, direction=1, **kwargs)])

    def load(self, sim):
        # If loading randomly, make sure that two adjacent spaces are free. In
        # any case, load the legs right next to each other
        if self.heads[0].position is None:
            possible_positions = []
            for i in range(len(sim.track)-2):
                if len(sim.track[i]) == 0 and len(sim.track[i+1]) == 0:
                    possible_positions.append(i)
            self.heads[0].position = random.choice(possible_positions)
        self.heads[1].position = self.heads[0].position + 1

        # Now use base class for loading
        MultiHeadParticle.load(self, sim)

    def unload(self, sim):
        MultiHeadParticle.unload(self, sim)
        FiniteLife.unload(self, sim)

        # If we unload bc of lifetime, immediately reload a new one
        if self.lifetime < 1e-10:
            def myreload(sim):
                sim.load(Cohesin(meanlife=self.meanlife, speed=self.heads[0].speed))

            sim.load(Event(myreload))

################################################################################

class CTCF(Boundary):
    pass

################################################################################

class RNAP(Walker):
    steppingrule = karo.steppingrules.pushy_train

################################################################################

if __name__ == "__main__":
    # Run a short simulation with these particles and plot the results
    L_track = 100
    N_cohesin = 5
    CTCFs = [30, 45, 70]

    # Setup system and collision rules
    # Note: with the old extrusion scheme, we actually don't really need
    #   collision rules at all, since "just don't move further" is the stepping
    #   rule. For demonstration purposes, here we make cohesin legs bounce off
    #   each other
    sim = karo.Simulation(L=L_track)
    sim.collider.register(CohesinLeg, CohesinLeg, karo.collisionrules.reflect) # for fun

    # Load particles
    for pos in CTCFs:
        sim.load(CTCF(position=pos))

    for _ in range(N_cohesin):
        sim.load(Cohesin(meanlife=10, speed=2))

    # Run for a bit
    sim.run(50)

    # Now RNAP enters the game! (push everything a little bit, then disappear)
    # We just keep the simulation running for a bit after RNAP falls off.
    rnap = RNAP(position = 25, direction = 1, speed = 1)
    sim.load(rnap)
    sim.load(Event(rnap.unload, remaining_time=50))
    sim.run(100)

    # Output
    from matplotlib import pyplot as plt

    colors = {Cohesin : 'blue', Boundary : 'black', CTCF : 'red', RNAP : 'green'}
    plt.figure(figsize=[15, 7])
    karo.showSim(sim.reporter.resample((None, None, 0.5)).out, colors, s=5)
    plt.show()
