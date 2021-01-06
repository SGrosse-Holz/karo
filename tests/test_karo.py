import os,sys
try: # prevent any plotting
    del os.environ['DISPLAY']
except KeyError:
    pass

import subprocess # for running example script

import unittest
from unittest.mock import patch, Mock

from context import karo
# Import the internals that are not automatically included in the namespace
import karo.datastructures
import karo.constituents
import karo.framework

class TestBoundSafeList(unittest.TestCase):
    def test_init(self):
        lst = karo.datastructures.BoundSafeList([1, 2, 3], outOfBounds_value={})

    def test_getitem(self):
        lst = karo.datastructures.BoundSafeList([1, 2, 3], outOfBounds_value=-1)
        self.assertEqual(lst[-1], -1)
        self.assertEqual(lst[1], 2)
        self.assertListEqual(lst[-2:5], [-1, -1, 1, 2, 3, -1, -1])
        self.assertListEqual(lst[:-1], [])
        self.assertListEqual(lst[2:], [3])

    def test_mutableOOR(self):
        lst = karo.datastructures.BoundSafeList([1, 2, 3], outOfBounds_value=set())
        lst[5].add(6)
        self.assertSetEqual(lst[5], set())

class TestOLL(unittest.TestCase):
    def setUp(self):
        self.lst = karo.datastructures.OrderedLinkedList()

    def test_str(self):
        self.assertEqual(str(self.lst), "[]")
        self.lst.insert(0, 5)
        self.assertEqual(str(self.lst), "(0, 5)")

    def test_len(self):
        for i in range(10):
            self.lst.insert(i, 5)
        self.assertEqual(len(self.lst), 10)

    def test_checkNotEmpty(self):
        with self.assertRaises(karo.datastructures.EmptyList):
            self.lst.checkNotEmpty()
        self.lst.insert(0, 5)
        self.lst.checkNotEmpty()

    def test_lastNodeBefore(self):
        for i in range(10):
            self.lst.insert(i/11, i)
        self.assertEqual(self.lst.lastNodeBefore(1).data, 9)
        self.assertIs(self.lst.lastNodeBefore(0), self.lst.head)
        self.assertEqual(self.lst.lastNodeBefore(0.5).data, 5)
        node = self.lst.lastNodeBefore(0.5)
        self.assertEqual(self.lst.lastNodeBefore(0.8, node).data, 8)
        self.assertEqual(self.lst.lastNodeBefore(0.4, node).data, 5)

    def test_insert(self):
        self.lst.insert(0, 5)
        mutableData = [1, 2, 3]
        self.lst.insert(3.14, mutableData)
        self.assertEqual(len(self.lst), 2)
        mutableData.append(4)
        self.assertEqual(len(self.lst.lastNodeBefore(4).data), 4)

    def test_movet(self):
        for i in range(10):
            self.lst.insert(10-i, i)
        self.lst.movet(5)
        self.assertEqual(self.lst.head.next.next.t, 7)
        self.lst.movet(-10)
        self.assertEqual(self.lst.head.next.next.t, -3)

    def test_pop(self):
        data = {'a' : 5, 'b' : 7}
        self.lst.insert(5, 10)
        self.lst.insert(1, data)
        t, dat = self.lst.pop()
        self.assertIs(dat, data)
        t, dat = self.lst.pop()
        self.assertEqual(dat, 10)

    def test_remove(self):
        self.lst.insert(5, 10)
        self.lst.insert(3, 5)
        self.lst.insert(7, 100)
        self.lst.insert(0.1, 7)
        with self.assertRaises(RuntimeError):
            self.lst.remove(4)
        self.lst.remove(3)
        self.assertEqual(len(self.lst), 3)
        self.lst.remove(4, 7)
        self.assertEqual(len(self.lst), 2)
        self.lst.remove(0, 8)
        self.assertEqual(len(self.lst), 0)

    def test_removeData(self):
        # Note that this uses 'is' for comparison!
        data = []
        for i in range(11):
            data.append([i/10])
            self.lst.insert(i/13, data[-1])
        self.lst.removeData(data[5])
        self.assertEqual(len(self.lst), 10)
        with self.assertRaises(ValueError):
            self.lst.removeData([5])

class TestTrack(unittest.TestCase):
    def setUp(self):
        self.track = karo.framework.Track(10)

    def test_remove(self):
        data = (1, 2, 3)
        self.track.remove(data) # Check error-free processing of missing data
        self.track[5].add(data)
        self.track.remove(data)
        self.assertSetEqual(self.track[5], set())

    def test_nextEmpty(self):
        self.assertEqual(self.track.nextEmpty(5, 1), 5)
        self.track[5].add(5)
        self.assertEqual(self.track.nextEmpty(5, 1), 6)
        self.assertEqual(self.track.nextEmpty(5, -1), 4)
        self.track[0].add(6)
        self.assertEqual(self.track.nextEmpty(0, -1), -1)

    def test_aggregate(self):
        self.track[6].add(7)
        self.track[4].add(3)
        self.assertSetEqual(self.track.aggregate(range(4, 7)), {7, 3})

class TestSim(unittest.TestCase):
    # Simply run a small simulation to check that everything works
    def test_simplerun(self):
        L_track = 100
        N_particles = 10

        sim = karo.Simulation(L=L_track)

        class GummyBear(karo.particles.Walker): pass
        for i in range(N_particles):
            sim.load(GummyBear(speed=1))

        sim.collider.register(GummyBear, karo.particles.Particle, karo.collisionrules.reflect)
        sim.run(5)

        class Cleaner(karo.particles.Walker): pass
        Cleaner.steppingrule = karo.steppingrules.pushy_hard
        sim.collider.register(Cleaner, karo.particles.Walker, karo.collisionrules.kickOff)
        sim.load(Cleaner(position=0, direction=1, speed=5))
        sim.run(20)

        self.assertEqual(len(sim.nextUpdates), 3) # Only Cleaner and the two TrackEnds
        for particle in sim.track.aggregate(range(len(sim.track))):
            sim.unload(particle)
        self.assertEqual(len(sim.nextUpdates), 6) # Have three additional Events
        sim.run(0)
        self.assertEqual(len(sim.nextUpdates), 0)

        karo.showSim(sim.reporter.resample(1.7).out, dict()) # Rendering is suppressed

        ########## short check of TimeBasedReporter

        sim = karo.Simulation(L=L_track, dt=1)
        for _ in range(N_particles):
            sim.load(GummyBear(speed=1))
        sim.collider.register([GummyBear, karo.particles.Walker], [karo.particles.Walker], [karo.collisionrules.reflect, karo.collisionrules.kickOff])
        sim.run(5)

    def test_example(self):
        # check that the example script runs
        example = "../examples/DNAparticles.py"
        subprocess.run(["python", example])

    def test_rules(self):
        """
        Run a simulation with particles for all rules we have
        """
        steps = [
                karo.steppingrules.careful,
                karo.steppingrules.transparent,
                karo.steppingrules.pushy_soft,
                karo.steppingrules.pushy_hard,
                karo.steppingrules.pushy_train,
                ]
        collisions = [
                karo.collisionrules.reflect,
                karo.collisionrules.kickOff,
                karo.collisionrules.burnOff,
                karo.collisionrules.fallOff,
                ]

        types = []
        for steprule in steps:
            class dummy(karo.particles.Walker):
                steppingrule = steprule
            types.append(dummy)

        for coll in collisions:
            sim = karo.Simulation(100)
            for typ in types:
                sim.load(typ(speed=1))
            sim.collider.register(karo.particles.Walker, karo.particles.Walker, coll)
            sim.run(100)

if __name__ == '__main__':
    unittest.main(module=__file__[:-3])
