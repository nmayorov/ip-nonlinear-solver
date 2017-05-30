"""
Equality-constrained quadratic programming solvers.
"""

from __future__ import division, print_function, absolute_import
from scipy.sparse import linalg, bmat, csc_matrix
from scipy.sparse.linalg import LinearOperator
from sksparse.cholmod import cholesky_AAt
import numpy as np

__all__ = [
    'eqp_kktfact',
    'projections',
    'projected_cg'
]


# For comparison with the projected CG
def eqp_kktfact(G, c, A, b):
    """
    Solve equality-constrained quadratic programming (EQP) problem
    ``min 1/2 x.T G x + x.t c``  subject to ``A x = b``
    using direct factorization of the KKT system.

    Parameters
    ----------
    G, A : sparse matrix
        Hessian and Jacobian matrix of the EQP problem.
    c, b : ndarray
        Unidimensional arrays.

    Returns
    -------
    x : ndarray
        Solution of the KKT problem.
    lagrange_multipliers : ndarray
        Lagrange multipliers of the KKT problem.
    """

    n = len(c)  # Number of parameters
    m = len(b)  # Number of constraints

    # Karush-Kuhn-Tucker matrix of coeficients.
    # Defined as in Nocedal/Wright "Numerical
    # Optimization" p.452 in Eq. (16.4)
    kkt_matrix = csc_matrix(bmat([[G, A.T], [A, None]]))

    # Vector of coeficients.
    kkt_vec = np.hstack([-c, b])

    # TODO: Use a symmetric indefinite factorization
    #       to solve the system twice as fast (because
    #       of the symmetry)
    lu = linalg.splu(kkt_matrix)
    kkt_sol = lu.solve(kkt_vec)

    x = kkt_sol[:n]
    lagrange_multipliers = -kkt_sol[n:n+m]

    return x, lagrange_multipliers


def projections(A):
    """
    Return three linear operators related with a given matrix A.

    Parameters
    ----------
    A : sparse matrix
        Matrix ``A`` used in the projection

    Returns
    -------
    Z : LinearOperator
        Null-space operator. For a given vector ``x``,
        the null space operator is equivalent to apply
        a projection matrix ``P = I - A.T inv(A A.T) A``
        to the vector. It can be shown that this is
        equivalent to project ``x`` into the null space
        of A.
    LS : LinearOperator
        Least-Square operator. For a given vector ``x``,
        the least-square operator is equivalent to apply a
        pseudoinverse matrix ``pinv(A.T) = inv(A A.T) A``
        to the vector. It can be shown that this vector
        ``pinv(A.T) x`` is the least_square solution to
        ``A.T y = x``.
    Y : LinearOperator
        Row-space operator. For a given vector ``x``,
        the row-space operator is equivalent to apply a
        projection matrix ``Q = A.T inv(A A.T)``
        to the vector.  It can be shown that this
        vector ``y = Q x``  the minimum norm solution
        of ``A y = x``

    Notes
    -----
    The operators will be computed using the so-called
    normal equation approach explained in Nocedal/Wright
    "Numerical Optimization" p.462.
    """

    m, n = np.shape(A)

    factor = cholesky_AAt(A)

    # z = x - A.T inv(A A.T) A x
    def null_space(x):
        return x - A.T.dot(factor(A.dot(x)))

    # z = inv(A A.T) A x
    def least_squares(x):
        return factor(A.dot(x))

    # z = A.T inv(A A.T) x
    def row_space(x):
        return A.T.dot(factor(x))

    Z = LinearOperator((n, n), null_space)
    LS = LinearOperator((m, n), least_squares)
    Y = LinearOperator((n, m), row_space)

    return Z, LS, Y


def projected_cg(G, c, Z, Y, b, tol=None):
    """
    Solve equality-constrained quadratic programming (EQP) problem
    ``min 1/2 x.T G x + x.t c``  subject to ``A x = b``
    using projected cg method.

    Parameters
    ----------
    G : LinearOperator, sparse matrix, ndarray
        Operator for computing ``G v``.
    c : ndarray
        Unidimensional array.
    Z : LinearOperator, sparse matrix, ndarray
        Operator for projecting ``x`` into the null space of A.
    Y : LinearOperator,  sparse matrix, ndarray
        Operator that, for a given a vector ``b``, compute a solution of
        of ``A x = b``.
    b : ndarray
        Unidimensional array.
    tol : float
        Tolerance used to interrupt the algorithm

    Returns
    -------
    x : ndarray
        Solution of the KKT problem

    Notes
    -----
    Algorithm 16.2 on p.461 in Nocedal and Wright
    "Numerical Optimization".
    """

    n = len(c)  # Number of parameters
    m = len(b)  # Number of constraints

    # Initial Values
    x = Y.dot(b)
    r = G.dot(x) + c
    g = Z.dot(r)
    d = -g

    # Values for the first iteration
    G_d = G.dot(d)
    rt_g = r.dot(g)

    # Set default tolerance
    if tol is None:
        tol = max(0.01*np.sqrt(rt_g), 1e-8)

    # Check if the problem is not satisfied already
    if rt_g < tol:
        return x

    for i in range(n-m):

        dt_G_d = G_d.dot(d)

        alpha = rt_g/dt_G_d
        x = x + alpha*d
        r_next = r + alpha*G_d
        g_next = Z.dot(r_next)

        rt_g_next = r_next.dot(g_next)

        # Stop Criteria
        if rt_g_next < tol:
            return x

        beta = rt_g_next/rt_g
        d = - g_next + beta*d

        g = g_next
        r = r_next
        G_d = G.dot(d)
        rt_g = rt_g_next

    return x