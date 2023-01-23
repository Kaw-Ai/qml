r"""
Testing for symmetry with quantum computers
===========================================

.. meta::
    :property="og:description": Test if a system possesses discrete symmetries
    :property="og:image": demonstrations/testing_symmetry/thumbnail_tutorial_testing_symmetry.jpg

.. related::

    tutorial_geometric_qml Intro to geometric quantum machine learning

*Author: David Wakeham. Posted: 24 January 2023.*

Introduction
------------

Symmetries are transformations that leave something looking the same.
They are all-important in quantum mechanics, encoding crucial
information about both the static and dynamic properties of systems, for
instance, numbers that are conserved or the form our Hilbert space can
take. Symmetries need not be exact, since a system can look
approximately, rather than exactly, the same after a transformation. It
therefore makes sense to have an algorithm to determine if a Hamiltonian
has an approximate symmetry.

.. figure:: ../demonstrations/testing_symmetry/symm2.png
   :alt: symm
   :align: center
   :width: 40%

In this demo, we’ll implement the elegant algorithm of `LaBorde and
Wilde (2022) <https://arxiv.org/pdf/2203.10017.pdf>`__ for testing the
symmetries of a Hamiltonian. We’ll be able to determine whether a system
has a finite group of symmetries :math:`G`, and if not, by how much the
symmetry is violated.

Background
--------------

We will encode symmetries into a `finite group
<https://en.wikipedia.org/wiki/Finite_group>`__. This is an
algebraic structure consisting of transformations :math:`g`, which act
on the Hilbert space :math:`\mathcal{H}` of our system in the form of
unitary operators :math:`U(g)` for :math:`g \in G`. More formally,
given any two elements :math:`g_1, g_2\in G`, there is a *product* :math:`g_1 \circ g_2 \in G`, and such that:

* **multiplication is associative**, :math:`g_1 \circ (g_2 \circ g_3) = (g_1 \circ g_2) \circ g_3` for all :math:`g_1, g_2, g_3 \in G`;
* **there is a boring transformation** :math:`e` that does nothing, :math:`g \circ e = e \circ g = e` for all :math:`g \in G`;
* **transformations can be undone**, with some :math:`g^{-1} \in G` such that :math:`g \circ g^{-1} = g^{-1} \circ g = e` for all :math:`g \in G`.

It is sensible to ask that the unitary operators preserve the structure of the group:

.. math::


   U(g_1)U(g_2) = U(g_1 \circ g_2).

For more on groups and how to represent them with matrices, see our `demo on geometric learning <https://pennylane.ai/qml/demos/tutorial_geometric_qml.html>`__.
For the Hamiltonian to respect the symmetries encoded in the group :math:`G` it means that it commutes with the matrices,

.. math::


   [U(g),\hat{H}] = 0

for all :math:`g \in G`.
Since the Hamiltonian generates time evolution, this means that if we
apply a group transformation now or we apply it later, the effect is the
same. Thus, we seek an algorithm which checks if these commutators are
zero.

Averaging over symmetries
-----------------------------

To verify that the Hamiltonian is symmetric with respect to :math:`G`, it
seems like we will need to check each element
:math:`g \in G` separately. There is a clever way to avoid this and boil
it all down to a single number. For now, we’ll content ourselves with
looking at the *average* over the group:

.. math:: \frac{1}{|G|}\sum_{g\in G}[U(g),\hat{H}] = 0. 

To make things concrete, let’s consider the `cyclic group <https://en.wikipedia.org/wiki/Cyclic_group>`__
:math:`G = \mathbb{Z}_4`, which we can think of as rotations of the square. If we place a qubit
on each corner, this group will naturally act on four qubits.

.. figure:: ../demonstrations/testing_symmetry/square.png
   :alt: square
   :align: center
   :width: 30%

It is generated by a single rotation, which we’ll call :math:`c`. We’ll
consider three Hamiltonians: one which is exactly symmetric with respect
to :math:`G` (called :math:`\hat{H}_\text{symm}`), one which is near symmetric
(called :math:`\hat{H}_\text{nsym}`), and one which is asymmetric
(called :math:`\hat{H}_\text{asym}`). We'll define them by

.. math:: \begin{align*}
   \hat{H}_\text{symm} & = X_0 + X_1 + X_2 + X_3\\
   \hat{H}_\text{nsym} & = X_0 + 1.1 \cdot X_1 + 0.9 \cdot X_2 + X_3 \\
   \hat{H}_\text{asym} & = X_0 + 2\cdot X_1 + 3\cdot X_2.
   \end{align*}

Let’s see how this looks in PennyLane. We’ll create a register
``system`` with four wires, one for each qubit. The generator :math:`c`
acts as a permutation:

.. math:: \vert x_0 x_1 x_2 x_3\rangle \overset{c}{\mapsto} \vert x_3 x_0 x_1 x_2\rangle

for basis states :math:`\vert x_0 x_1 x_2 x_3\rangle` and extends by linearity.
The simplest way to do this is by using
:class:`qml.Permute <pennylane.Permute>`.
We can convert this into a matrix by using
:class:`qml.matrix() <pennylane.matrix>`.
We can obtain any other element :math:`g\in G` by simply iterating
:math:`c` the appropriate number of times.

"""

import pennylane as qml
from pennylane import numpy as np

# Create wires for the system
system = range(4)

# The generator of the group
c = qml.Permute([3, 0, 1, 2], wires=system)
c_mat = qml.matrix(c)


######################################################################
# To create the Hamiltonians, we use
# :class:`qml.Hamiltonian <pennylane.Hamiltonian>`:
#

# Create Hamiltonians
obs = [qml.PauliX(system[0]), qml.PauliX(system[1]), qml.PauliX(system[2]), qml.PauliX(system[3])]
coeffs1, coeffs2, coeffs3 = [1, 1, 1, 1], [1, 1.1, 0.9, 1], [1, 2, 3, 0]
Hsymm, Hnsym, Hasym = (
    qml.Hamiltonian(coeffs1, obs),
    qml.Hamiltonian(coeffs2, obs),
    qml.Hamiltonian(coeffs3, obs),
)


######################################################################
# To arrive at the algorithm for testing this average symmetry property,
# we start with a trick called the `Choi-Jamiołkowski
# isomorphism <https://en.wikipedia.org/wiki/Choi%E2%80%93Jamio%C5%82kowski_isomorphism>`__
# for thinking of time evolution as a state instead of an operator.
# This state is called the *dual* of the operator. It’s
# easy to describe how to construct this state in words: make a copy :math:`\mathcal{H}_\text{copy}`
# of the system :math:`\mathcal{H}`, create a maximally entangled state,
# and time evolve the state on :math:`\mathcal{H}`. In fact, this trick works to
# give a dual state :math:`\vert\Phi^U\rangle` for any operator :math:`U`, as below:
#
# .. figure:: ../demonstrations/testing_symmetry/choi.png
#    :alt: choi
#    :align: center
#    :width: 40%
#
# We've pictured entanglement by joining the wires corresponding to the system and the copy.
# For time evolution, we’ll call the dual state
# :math:`\vert\Phi_t\rangle`, and formally define it:
#
# .. math::
#
#
#    \vert\Phi_t\rangle = \frac{1}{\sqrt{d}}\sum_{i=1}^d e^{-it\hat{H}}\vert i\rangle \otimes \vert i_\text{copy}\rangle.
#
# You can `show mathematically <https://arxiv.org/pdf/2203.10017.pdf>`__ that the average symmetry condition is equivalent to
#
# .. math::
#
#
#    \Pi_G\vert\Phi_t\rangle = \vert\Phi_t\rangle,
#
# where :math:`\Pi_G` is an operator defined by
#
# .. math::
#
#
#    \Pi_G  = \frac{1}{|G|}\sum_{g\in G} U(g) \otimes \overline{U(g)}.
#
# In fact, it turns out that :math:`\Pi_G^2 = \Pi_G`, and hence it is a
# *projector*, with an associated measurement, asking: is the state
# symmetric on average? The statement math`:\Pi_G\vert\Psi_t\rangle =\vert\Psi_t\rangle` is a mathematical way of
# saying “yes”. So, our goal now is to write a circuit
# which (a) prepares the state :math:`\vert\Phi_t\rangle`, and (b) performs the
# measurement :math:`\Pi_G`. Part (a) is simpler. In general, we can just
# use a “cascade” of Hadamards and CNOTs, similar to the usual circuit for
# generating a Bell state on two qubits, as pictured below:
#
# .. figure:: ../demonstrations/testing_symmetry/bells.png
#    :alt: bells
#    :align: center
#    :width: 50%
#
# Let’s implement this for our four-qubit system in PennyLane:
#

# Create copy of the system
copy = range(4, 8)

# Prepare entangled state on system and copy
def prep_entangle():
    for wire in system:
        qml.Hadamard(wire)
        qml.CNOT(wires=[wire, wire + 4])


######################################################################
# We then need to implement time evolution on the system. In applications,
# the system’s evolution could be a “black box” we can query, or something
# given to us analytically. In general, we can approximate time evolution
# with
# :class:`qml.ApproxTimeEvolution <pennylane.ApproxTimeEvolution>`.
# However, since our Hamiltonians consist of terms that *commute*, we will
# be able to evolve exactly using
# :class:`qml.CommutingEvolution <pennylane.CommutingEvolution>`.
# We will reiterate this below.
# That's it for part (a)!

# Use Choi-Jamiołkowski isomorphism
def choi_state(hamiltonian, time):
    prep_entangle()
    qml.CommutingEvolution(hamiltonian, time)

######################################################################
# Controlled symmetries
# -------------------------
#
# Part (b) is more interesting. The simplest approach is to use an auxiliary register :math:`\mathcal{H}_G` which
# encodes :math:`G`, with basis elements :math:`\vert g\rangle` labelled
# by group elements :math:`g \in G`. This needs :math:`\log \vert G\vert`
# qubits, which (along with any Hamiltonian simulation) will form the main
# resource cost of the algorithm. These will then can group
# transformations to a state
# :math:`\vert\psi\rangle \in \mathcal{H}\otimes \mathcal{H}_\text{copy}`
# in a controlled way via
#
# .. math::
#
#
#    \vert{\psi}\rangle \otimes \vert g\rangle \mapsto (U(g)\otimes \overline{U(g)})\vert{\psi} \rangle \otimes \vert g\rangle_G,
#
# which we’ll call :math:`CU`. We take this controlled gate as a
# primitive. To test average symmetry, we simply place
# :math:`\mathcal{H}_G` in a uniform superposition
#
# .. math::
#
#
#    \vert +\rangle_G = \frac{1}{\sqrt{|G|}}\sum_{g\in G} \vert g\rangle_G
#
# and apply the controlled operator to the state generated in part (a).
# This gives
#
# .. math::
#
#
#    \vert\Phi_t\rangle \otimes \vert +\rangle_G \mapsto \frac{1}{\sqrt{|G|}}\sum_{g\in G}(U(g)\otimes \overline{U(g)})\vert\Phi_t\rangle \otimes \vert g\rangle_G.
#
# This isn’t quite what we want yet, in particular because the system
# :math:`\mathcal{H}` is entangled not only with the copy, but also with
# the register :math:`\mathcal{H}_G`. To fix this, we observe the
# *register*, and see if it’s in the superposition
# :math:`\vert+\rangle_G`. The state, conditioned on this observation, is
#
# .. math::
#
#
#    \begin{align*}
#    {}_G\langle +\vert \frac{1}{\sqrt{|G|}}\sum_{g\in G}(U(g)\otimes \overline{U(g)})\vert\Phi_t\rangle \otimes \vert g\rangle_G & = \frac{1}{|G|}\sum_{g, g'\in G}(U(g)\otimes \overline{U(g)})\vert\Phi_t\rangle \langle g'\vert g\rangle_G \\ & = \Pi_G \vert\Phi_t\rangle,
#    \end{align*}
#
# and hence the probability of observing it is
#
# .. math::
#
#
#    P_+ = \vert \Pi_G \vert\Phi_t\rangle \vert^2 = \langle \Phi_t \vert \Pi_G^\dagger \Pi_G\vert\Phi_t\rangle = \langle \Phi_t \vert \Pi_G\vert\Phi_t\rangle
#
# This is exactly what we want! So, let’s code all this up for our
# example. We’ll need two qubits for our auxiliary register
# :math:`\mathcal{H}_G`. To place it in a uniform superposition, just
# apply a Hadamard gate to each qubit. To measure the
# :math:`\vert+\rangle_G` state at the end, we undo these Hadamards and
# try to measure “:math:`00`”. Finally, it’s straightforward to implement
# the controlled gate :math:`CU` using controlled
# operations (namely :class:`qml.ControlledQubitUnitary<pennylane.ControlledQubitUnitary>`)
# on each qubit:
#
# .. figure:: ../demonstrations/testing_symmetry/cu.png
#    :alt: cu
#    :align: center
#    :width: 50%
#

# Create group register and device
aux = range(8, 10)
dev = qml.device("default.qubit", wires=10)

# Create plus state
def prep_plus():
    qml.Hadamard(wires=aux[0])
    qml.Hadamard(wires=aux[1])

# Implement controlled symmetry operations on system
def CU_sys():
    qml.ControlledQubitUnitary(c_mat @ c_mat, control_wires=[aux[0]], wires=system)
    qml.ControlledQubitUnitary(c_mat, control_wires=[aux[1]], wires=system)


# Implement controlled symmetry operations on copy
def CU_cpy():
    qml.ControlledQubitUnitary(c_mat @ c_mat, control_wires=[aux[0]], wires=copy)
    qml.ControlledQubitUnitary(c_mat, control_wires=[aux[1]], wires=copy)

######################################################################
# Let’s combine everything and actually run our circuit!
#

# Circuit for average symmetry
@qml.qnode(dev)
def avg_symm(hamiltonian, time):

    # Use Choi-Jamiołkowski isomorphism
    choi_state(hamiltonian, time)

    # Apply controlled symmetry operations
    prep_plus()
    CU_sys()
    CU_cpy()

    # Ready register for measurement
    prep_plus()

    return qml.probs(wires=aux)


print("For Hamiltonian Hsymm, the |+> state is observed with probability", avg_symm(Hsymm, 1)[0], ".")
print("For Hamiltonian Hnsym, the |+> state is observed with probability", avg_symm(Hnsym, 1)[0], ".")
print("For Hamiltonian Hasym, the |+> state is observed with probability", avg_symm(Hasym, 1)[0], ".")


######################################################################
# We see that for the symmetric Hamiltonian, we’re *certain* to observe
# :math:`\vert +\rangle_G`. We’re very likely to observe
# :math:`\vert +\rangle_G` for the near-symmetric Hamiltonian, and our
# chances suck for the asymmetric Hamiltonian.
#


######################################################################
# A short time limit
# ----------------------
#
# This circuit leaves a few things to be desired. First, it only measures
# whether our Hamiltonian is symmetric *on average*. What if we want to
# know if it’s symmetric with respect to each element individually? We could run the circuit for each
# element :math:`g\in G`, but perhaps there is a better way. Second, even
# if we could do that, we don’t know what the numbers coming out of the
# circuit mean.
# We can address both questions by considering very short times,
# :math:`t \to 0`. In this case, we can Taylor expand the unitary
# time-evolution operator,
#
# .. math::
#
#
#    e^{-it \hat{H}} = \mathbb{I} - it \hat{H} - \frac{t^2 \hat{H}^2}{2} + O(t^3).
#
# We’ll assume that, if we’re simulating the evolution, the expansion is
# accurate to this order. Also, let :math:`d` be the dimension of our system.
# In this case, it’s `possible to prove <https://arxiv.org/pdf/2203.10017.pdf>`__ that the
# probability :math:`P_+` of observing the :math:`\vert +\rangle_G` state
# is
#
# .. math::
#
#
#    P_+ = \langle \Phi_t \vert \Pi_G \vert \Phi_t\rangle = 1 - \frac{t^2}{2d \vert G\vert}\sum_{g\in G}\vert\vert [U(g), \hat{H}] \vert\vert_2^2 + O(t^3),
#
# where :math:`\vert\vert\cdot\vert\vert_2` represents the usual
# (Pythagorean) :math:`2`-norm. This is a sharp expression relating the
# output of the circuit :math:`P_+` to a quantity measuring of the degree
# of symmetry or lack thereof, the sum of squared commutator norms.
# We’ll call this sum the *asymmetry* :math:`\xi`. Rearranging, we have
#
# .. math::
#
#
#    \xi = \sum_{g\in G}\vert\vert [U(g), \hat{H}] \vert\vert_2^2 = \frac{2d\vert G\vert(1 - P_+)}{t^2} + O(t).
#
# Let’s see how this works in our example. Since :math:`d` is the
# dimension of the system, in our four-qubit case, :math:`d=2^4 = 16`,
# while :math:`\vert G\vert = 4`.
#

# Define asymmetry circuit
def asymm(hamiltonian, time):
    d, G = 16, 4
    P_plus = avg_symm(hamiltonian, time)[0]
    xi = 2 * d * (1 - P_plus) / (time ** 2)
    return xi


print("The asymmetry for Hsymm is", asymm(Hsymm, 1e-4), ".")
print("The asymmetry for Hnsym is", asymm(Hnsym, 1e-4), ".")
print("The asymmetry for Hasym is", asymm(Hasym, 1e-4), ".")


######################################################################
# Our symmetric Hamiltonian :math:`\hat{H}_\text{symm}` has a near-zero asymmetry as
# expected. The near-symmetric
# Hamiltonian :math:`\hat{H}_\text{nsym}` has an asymmetry much larger than
# :math:`O(t)`; evidently, :math:`\xi` is a more intelligible
# measure of symmetry than :math:`P_+`. Finally, the Hamiltonian
# :math:`\hat{H}_\text{asym}` has a huge error; it is not even approximately
# symmetric.
#


######################################################################
# Concluding remarks
# ----------------------
#
# Symmetries are physically important in quantum mechanics. Most systems
# of interest are large and complex, and even with an explicit description
# of a Hamiltonian, symmetries can be hard to determine by hand. Testing
# for symmetry when we have access to Hamiltonian evolution (either
# physically or by simulation) is thus a natural target for quantum
# computing.
#
# Here, we’ve described a simple algorithm to check if a system with
# Hamiltonian :math:`\hat{H}` is approximately symmetric with respect to a
# finite group :math:`G`. More precisely, for short times, applying
# controlled symmetry operations to the state dual to Hamiltonian
# evolution gives the asymmetry
#
# .. math::
#
#
#    \xi = \sum_{g\in G} \vert\vert [U(g), H]\vert\vert^2_2.
#
# This vanishes just in case the system possesses the symmetry, and
# otherwise tells us by how much it is violated. The main overhead is the
# size of the register encoding the group, which scales logarithmically
# with :math:`\vert G\vert`.
# So, it's expensive in memory for big groups, but quick to run!
# Regardless of the details, this algorithm suggests routes for further exploring
# the rich landscape of symmetry with quantum computers.


######################################################################
# References
# --------------
#
# 1. LaBorde, M. L and Wilde, M.M. `Quantum Algorithms for Testing
#    Hamiltonian Symmetry <https://arxiv.org/pdf/2203.10017.pdf>`__
#    (2022).
#

##############################################################################
# About the author
# ----------------
# .. include:: ../_static/authors/david_wakeham.txt
