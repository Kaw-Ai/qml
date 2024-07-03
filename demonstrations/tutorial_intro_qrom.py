r"""Intro to QROM
=============================================================

Managing data is a crucial task on any computer, and quantum computers are no exception. Efficient data management is vital in quantum machine learning, search algorithms, and state preparation.
In this demonstration, we will introduce the concept of a Quantum Read-Only Memory (QROM), a data structure designed to load classical data on a quantum computer.
You will also see how easy it is to use this operator in PennyLane through the :class:`~.pennylane.QROM` template.

QROM
-----

The QROM is an operator that allows us to load classical data into a quantum computer. Data is represented as a collection of bitstrings (list of 0s and 1s) that we denote by :math:`b_1, b_2, \ldots, b_N`. The QROM operator is then defined as:

.. math::

    \text{QROM}|i\rangle|0\rangle = |i\rangle|b_i\rangle,

where :math:`|b_i\rangle` is the bitstring associated with the index :math:`i`.

For example, suppose our data consists of four bit-strings, each with three bits: :math:`[011, 101, 111, 100]`. Then, the index register will consist of two
qubits (:math:`2 = \log_2 4`) and the target register of three qubits (length of the bit-strings). In this case, the QROM operator acts as:

.. math::
     \begin{align}
     \text{QROM}|00\rangle|000\rangle &= |00\rangle|011\rangle \\
     \text{QROM}|01\rangle|000\rangle &= |01\rangle|101\rangle \\
     \text{QROM}|10\rangle|000\rangle &= |10\rangle|111\rangle \\
     \text{QROM}|11\rangle|000\rangle &= |11\rangle|100\rangle
     \end{align}

We will now explain three different implementations of a QROM: Select, SelectSwap, and an extension of SelectSwap.

Select
~~~~~~~

More generally, Select is an operator that prepares quantum states associated with indices. It is defined as:

.. math::

    \text{Sel}|i\rangle|0\rangle = |i\rangle U_i|0\rangle =|i\rangle|\phi_i\rangle,

where :math:`|\phi_i\rangle` is the i-th state we want to encode generated by a known-gate :math:`U_i`.
Since the bitstrings are encoded in computational basis states, we can view QROM as a special case of a Select operator.
The gates :math:`U_i` would simply be :math:`X` gates that determine whether each bit is a :math:`0` or a :math:`1`.
We use :class:`~.pennylane.BasisEmbedding` as a useful template where given the bitstrings, it places the :math:`X` gates
in the right position. Let's use a longer string for the following example:

"""

import pennylane as qml
from functools import partial

bitstrings = ["01", "11", "11", "00", "01", "11", "11", "00"]

control_wires = [0,1,2]
target_wires = [3,4]

Ui = [qml.BasisEmbedding(int(bitstring, 2), target_wires) for bitstring in bitstrings]

dev = qml.device("default.qubit", shots = 1)

# This line is included for drawing purposes only.
@partial(qml.devices.preprocess.decompose,
         stopping_condition = lambda obj: False,
         max_expansion=1)

@qml.qnode(dev)
def circuit(index):
    qml.BasisEmbedding(index, wires=control_wires)
    qml.Select(Ui, control=control_wires)
    return qml.sample(wires=target_wires)

##############################################################################
# Once we have defined the circuit, we can check that the outputs are as expected.
# We will also draw the circuit for the particular case in which we want to know the output of index :math:`3`.
# Note that in this case we generate in the control qubits the state :math:`|011\rangle`, representation of the
# number three in binary.

import matplotlib.pyplot as plt

qml.draw_mpl(circuit, style = "pennylane")(3)
plt.show()

for i in range(8):
    print(f"The bitstring stored in index {i} is: {circuit(i)}")


##############################################################################
# Nice, you can see that the outputs match the elements of our initial data list: :math:`[01, 11, 11, 00, 01, 11, 11, 00]`.
#
# Although the algorithm works correctly, the number of multicontrol gates is high.
# The decomposition of these gates is expensive and there are numerous works that attempt to simplify this.
# We highlight the work [#unary]_ which introduces an efficient technique using measurements in the middle
# of the circuit. Another clever approach was introduced in [#selectSwap]_ , with a smart structure known as SelectSwap, which we describe below.
#
# SelectSwap
# ~~~~~~~~~~
# The goal of the SelectSwap construction is to trade depth for width. That is, using multiple auxiliary qubits,
# we reduce the circuit depth required to build the QROM. The main idea is to organize the data in two dimensions,
# with each bitstring labelled by a column index :math:`c` and a row index :math:`r`.
# The control qubits of the Select block determine the column :math:`c`, while the
# control qubits of the swap block are used to specify the row index :math:`r`.
#
# .. figure:: ../_static/demonstration_assets/qrom/select_swap.jpeg
#    :align: center
#    :width: 70%
#    :target: javascript:void(0)
#
# Let's look at an example by assuming we want to load in the target wires the bitstring with
# the index :math:`5`.
# For it, we put as input in the control wires the state :math:`|101\rangle` (5 in binary), where the first two bits refer to the
# index :math:`c = |10\rangle` and the last one to the index :math:`r = |1\rangle`.  After applying the Select block, we
# obtain :math:`|101\rangle|b_4\rangle|b_5\rangle`, loading the column :math:`c`.
# Since the third
# control qubit (i.e., :math:`r`) is a :math:`|1\rangle`, it will activate the swap block, generating the state :math:`|101\rangle|b_5\rangle|b_4\rangle`
# loading the bitstring :math:`b_5` in the target register.
#
# Note that with more auxiliary qubits we could make larger groupings of bitstrings reducing the workload of the
# Select operator. Below we show an example with two columns and four rows:
#
# .. figure:: ../_static/demonstration_assets/qrom/select_swap_4.jpeg
#    :align: center
#    :width: 70%
#    :target: javascript:void(0)
#
# Using the same example, we have that :math:`c = |1\rangle` and :math:`r = |01\rangle`. In this case, the columns are
# determined by a single index but we need two indexes for the rows. We invite you to check that :math:`b_5` is actually
# loaded in the target wires.
#
#
# Reusable qubits
# ~~~~~~~~~~~~~~~~~
#
# The above approach has a drawback. The work wires have been altered, i.e., after applying the operator they have not
# been returned to state :math:`|0\rangle`. This can cause unwanted behaviors, so we will present the technique shown
# in [#cleanQROM]_ to solve this.
#
# .. figure:: ../_static/demonstration_assets/qrom/clean_version_2.jpeg
#    :align: center
#    :width: 90%
#    :target: javascript:void(0)
#
# To see how this circuit works, let's suppose we want to load the bitstring :math:`b_{cr}`, in the target wires.
# We can summarize the idea in a few simple steps:
#
# 1. **We start by generating the uniform superposition on the r-th register**. To do this, we put the Hadamard in the target wires and moved it to the :math:`r` -row with the swap block.
#
# .. math::
#       |c\rangle |r\rangle |0\rangle \dots |+\rangle_r \dots |0\rangle
#
# 2. **We apply the Select block.** Note that in the :math:`r`-th position, the Select has no effect since this state is not modified by :math:`X` gates.
#
# .. math::
#       |c\rangle |r\rangle |b_{c0}\rangle \dots |+\rangle_r \dots |b_{cR}\rangle
#
#
# 3. **We apply the Hadamard's in r-th register.** The two swap blocks and the Hadamard gate in target wires achieve this.
#
# .. math::
#       |c\rangle |r\rangle |b_{c0}\rangle \dots |0\rangle_r \dots |b_{cR}\rangle
#
# 4. **We apply Select again to the state.** Note that loading the bitstring twice in the same register leaves the state as :math:`|0\rangle`. (:math:`X^2 = \mathbb{I}`)
#
# .. math::
#       |c\rangle |r\rangle |0\rangle \dots |b_{cr}\rangle_r \dots |0\rangle
#
# That's it! With a last swap we have managed to load the bitstring of column :math:`c` and row :math:`r` in the target wires.
#
# QROM in PennyLane
# -----------------
# Coding a QROM circuit from scratch can be painful, but with the help of PennyLane you can do it in just one line.
# We are going to encode longer bitstrings and we will use enough work wires to group four bitstrings per column:

bitstrings = ["01", "11", "11", "10", "01", "11", "11", "00",
              "01", "11", "11", "11", "01", "00", "11", "00"]

control_wires = [0, 1, 2, 3]
target_wires = [4, 5]
work_wires = [6, 7, 8, 9, 10, 11]

# This function is included for drawing purposes only.
def my_stop(obj):
  if obj.name in ["CSWAP", "PauliX", "Hadamard"]:
    return True
  return False

@partial(qml.devices.preprocess.decompose, stopping_condition = my_stop, max_expansion=2)
@qml.qnode(qml.device("default.qubit", shots = 1))
def circuit(index):

    qml.BasisEmbedding(index, wires=control_wires)

    qml.QROM(bitstrings, control_wires, target_wires, work_wires, clean = False)

    return qml.sample(wires = target_wires)

qml.draw_mpl(circuit, style = "pennylane")(5)

print(f"The bitstring stored in index {5} is: {circuit(5)}")


##############################################################################
# Indeed, the bitstring with index :math:`5` is :math:`|11\rangle` . In this case we have used the state :math:`|0101\rangle` as input index, but you could send any other index
# or even a superposition of them.
#
# If we want to use the approach that cleans the work wires, we could set the ``clean`` attribute of QROM to ``True``.
# Let's see how the circuit looks like:

@partial(qml.devices.preprocess.decompose, stopping_condition = my_stop, max_expansion=2)
@qml.qnode(qml.device("default.qubit", shots = 1))
def circuit(index):

    qml.BasisEmbedding(index, wires=control_wires)

    qml.QROM(bitstrings, control_wires, target_wires, work_wires, clean = True)

    return qml.sample(wires = target_wires)

qml.draw_mpl(circuit, style = "pennylane")(5)
plt.show()

print(f"The bitstring stored in index {5} is: {circuit(5)}")

##############################################################################
# Beautiful! The circuit is more complex, but the work wires are clean.
# As a curiosity, this template works with work wires that are not initialized to zero.
#
#
#
# Conclusion
# ----------
#
# By implementing various versions of the QROM operator, such as Select and SelectSwap, we optimize quantum circuits
# for enhanced performance and scalability. Numerous studies demonstrate the efficacy of these methods in improving
# state preparation [#StatePrep]_ techniques by reducing the number of required gates, which we recommend you explore.
# As the availability of qubits increases, the relevance of these methods will grow making this operator an
# indispensable tool for developing new algorithms and an interesting field for further study.
#
# References
# ----------
#
# .. [#selectSwap]
#
#       Guang Hao Low, Vadym Kliuchnikov, and Luke Schaeffer,
#       "Trading T-gates for dirty qubits in state preparation and unitary synthesis",
#       `arXiv:1812.00954 <https://arxiv.org/abs/1812.00954>`__, 2018
#
# .. [#cleanQROM]
#
#       Dominic W. Berry, Craig Gidney, Mario Motta, Jarrod R. McClean, and Ryan Babbush,
#       "Qubitization of Arbitrary Basis Quantum Chemistry Leveraging Sparsity and Low Rank Factorization",
#       `Quantum 3, 208 <http://dx.doi.org/10.22331/q-2019-12-02-208>`__, 2019
#
# .. [#StatePrep]
#
#       Lov Grover and Terry Rudolph,
#       "Creating superpositions that correspond to efficiently integrable probability distributions",
#       `arXiv:quant-ph/0208112 <https://arxiv.org/abs/quant-ph/0208112>`__, 2002
#
# .. [#unary]
#
#       Guang Hao Low, Vadym Kliuchnikov, and Luke Schaeffer,
#       "Trading T-gates for dirty qubits in state preparation and unitary synthesis",
#       `arXiv:1812.00954 <https://arxiv.org/abs/1812.00954>`__, 2018
#
# About the author
# ----------------
