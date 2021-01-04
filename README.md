karo: a rule-agnostic library for 1d simulations
================================================

The goal of this project was to provide a framework for simulation of particles
living on a 1d track. These could be walking, sitting still (serving as
boundaries), hopping at irregular time steps, or pretty much whatever you can
come up with. The central feat of this library is exactly that last point, that
we don't need to assume anything about the actual behavior of the particles,
but just provide a framework for the simulation, and a library of basic
particle types that might be useful.

The general idea for the particle library is to use inheritance to add features
to a particle. For example, there is a base class for particles with a finite
life time, and one for random walkers. If you want a random walker with a
finite lifetime, simply create a new type that inherits from both. A small note
here: generally it turns out to be useful to differentiate between "types that
add functionality" such as most of those in the provided library, and "types
that identify particles with given functionality". The latter will often not
add any implementation themselves, but just serve to identify a type of
particle in the simulation and specify its behavior through inheritance and
rules (more on rules below). An example of such an "identifying type" is the
`TrackEnd`, which serves to mark the end of the track. For more examples, see
the `examples` folder.

The whole point of this library is to let the user specify rules for the
behavior of the particles. It is therefore equally reasonable to talk about a
rule-agnostic (because the library itself doesn't care which rules you end up
wanting to put in) or a rule-based (because they are the central concept)
approach. Rules specify actions to take in specific situations, for example
when two particles collide, or when a particle wants to take a step. The
submodules `collisionrules.py` and `steppingrules.py` provide some frequently
used rules for these two cases.

For more info on the library, see the module docstring of `framework`.

For installation with pip:
```sh
$ pip install git+https://github.com/SGrosse-Holz/karo
```
