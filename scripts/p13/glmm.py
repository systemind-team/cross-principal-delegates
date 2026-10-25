"""Random-intercept logistic regression by maximum likelihood (the central-claim test's model).

    y_j ~ Bernoulli(expit(eta_j)),  eta_j = x_j . theta + sigma * z_{g(j)},  z_g ~ N(0, 1) per cluster g

The marginal likelihood of a cluster, the integral over z_g, is evaluated by adaptive Gauss-Hermite
quadrature (AGHQ): for each cluster the integrand is centred at its mode and scaled by its curvature, then
`nodes` Gauss-Hermite points are used. The gradient uses Fisher's identity (the posterior expectation of
the complete-data score under the same quadrature), so objective and gradient come from one set of nodes.

Only numpy and scipy are used. `fit` returns the maximum, `lrt` the likelihood-ratio test of one
coefficient against zero, and `profile_ci` the profile-likelihood interval for one coefficient.
"""
import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import expit, log_expit
from scipy.stats import chi2

GH_X, GH_W = np.polynomial.hermite.hermgauss(20)


class Data:
    """Design matrix X (n x p), outcome y (n,), cluster index g (n,) with values 0..G-1."""

    def __init__(self, X, y, g, names=None):
        self.X = np.asarray(X, float)
        self.y = np.asarray(y, float)
        g = np.asarray(g)
        _, self.g = np.unique(g, return_inverse=True)
        self.G = int(self.g.max()) + 1
        self.names = list(names) if names is not None else [f"x{k}" for k in range(self.X.shape[1])]
        order = np.argsort(self.g, kind="stable")
        self.X, self.y, self.g = self.X[order], self.y[order], self.g[order]
        self.starts = np.searchsorted(self.g, np.arange(self.G))


def _cluster_sum(v, d):
    """Sum the rows of v (n x ...) within clusters."""
    return np.add.reduceat(v, d.starts, axis=0)


def _h(z, eta0, sigma, d):
    """h_g(z) per cluster: the log integrand in z (log-likelihood of the cluster's rows minus z^2 / 2)."""
    eta = eta0 + sigma * z[d.g]
    return _cluster_sum(d.y * log_expit(eta) + (1 - d.y) * log_expit(-eta), d) - 0.5 * z ** 2


def _modes(eta0, sigma, d, iters=100):
    """Mode and curvature of h_g(z) = sum_j log p(y_j | eta0_j + sigma z) - z^2 / 2, per cluster.
    Damped Newton: h_g is concave, but a full Newton step can overshoot and oscillate for a cluster whose
    outcomes are all 0 or all 1 when sigma is large, so each cluster's step is halved until h_g rises
    (Armijo condition). Fixed 2026-10-05; see PREREGISTRATION section 8."""
    z = np.zeros(d.G)
    hz = _h(z, eta0, sigma, d)
    for _ in range(iters):
        p = expit(eta0 + sigma * z[d.g])
        grad = sigma * _cluster_sum(d.y - p, d) - z
        hess = -(sigma ** 2) * _cluster_sum(p * (1 - p), d) - 1.0
        step = -grad / hess                       # ascent direction, since hess < 0
        if np.max(np.abs(step)) < 1e-10:
            break
        t = np.ones(d.G)
        slack = 1e-10 * (1.0 + np.abs(hz))      # rounding in h, so that a converged cluster is not backtracked
        for _ in range(60):
            znew = z + t * step
            hnew = _h(znew, eta0, sigma, d)
            bad = hnew < hz + 1e-4 * t * grad * step - slack
            if not bad.any():
                break
            t = np.where(bad, 0.5 * t, t)
        z, hz = znew, hnew
    p = expit(eta0 + sigma * z[d.g])
    curv = (sigma ** 2) * _cluster_sum(p * (1 - p), d) + 1.0
    return z, 1.0 / np.sqrt(curv)


def loglik_grad(theta, log_sigma, d, need_grad=True):
    """AGHQ log marginal likelihood and its gradient in (theta, log_sigma)."""
    sigma = float(np.exp(log_sigma))
    eta0 = d.X @ theta
    zhat, s = _modes(eta0, sigma, d)
    nodes = zhat[:, None] + np.sqrt(2.0) * s[:, None] * GH_X[None, :]          # G x K
    zj = nodes[d.g]                                                              # n x K
    eta = eta0[:, None] + sigma * zj
    ll_obs = d.y[:, None] * log_expit(eta) + (1 - d.y[:, None]) * log_expit(-eta)
    h = _cluster_sum(ll_obs, d) - 0.5 * nodes ** 2                               # G x K
    logw = np.log(GH_W)[None, :] + GH_X[None, :] ** 2 + h
    m = logw.max(axis=1, keepdims=True)
    lse = m[:, 0] + np.log(np.exp(logw - m).sum(axis=1))
    ll = float(np.sum(lse + np.log(np.sqrt(2.0) * s) - 0.5 * np.log(2 * np.pi)))
    if not need_grad:
        return ll, None
    post = np.exp(logw - lse[:, None])                                           # G x K, rows sum to 1
    resid = d.y[:, None] - expit(eta)                                            # n x K
    w = post[d.g]                                                                # n x K
    g_theta = d.X.T @ np.sum(w * resid, axis=1)
    g_ls = sigma * float(np.sum(w * resid * zj))
    return ll, np.concatenate([g_theta, [g_ls]])


def fit(d, fixed=None, start=None, maxiter=500):
    """Maximise the likelihood. `fixed` maps coefficient index -> value held fixed (an offset)."""
    fixed = fixed or {}
    p = d.X.shape[1]
    free = [k for k in range(p) if k not in fixed]
    x0 = np.zeros(len(free) + 1)
    if start is not None:
        x0[:-1] = np.asarray(start["theta"])[free]
        x0[-1] = start["log_sigma"]

    def full(v):
        th = np.zeros(p)
        th[free] = v[:-1]
        for k, val in fixed.items():
            th[k] = val
        return th, v[-1]

    def obj(v):
        th, ls = full(v)
        ll, gr = loglik_grad(th, ls, d)
        g = np.concatenate([gr[:-1][free], gr[-1:]])
        return -ll, -g

    res = minimize(obj, x0, jac=True, method="L-BFGS-B",
                   bounds=[(-30, 30)] * len(free) + [(np.log(1e-3), np.log(20))],
                   options={"maxiter": maxiter, "gtol": 1e-7, "ftol": 1e-12})
    th, ls = full(res.x)
    return {"theta": th, "log_sigma": float(ls), "sigma": float(np.exp(ls)), "loglik": -float(res.fun),
            "converged": bool(res.success), "message": str(res.message), "nit": int(res.nit)}


def refit_if_below(d, f1, f0):
    """The full model nests the null, so a full maximum below the null's is a failed fit: refit the full model
    from the null's estimate and keep the better (added 2026-10-05; PREREGISTRATION section 8)."""
    if f1["loglik"] < f0["loglik"] - 1e-6:
        g = fit(d, start=f0)
        return (g if g["loglik"] > f1["loglik"] else f1), True
    return f1, False


def lrt(d, k, full_fit=None):
    """Likelihood-ratio test of coefficient k = 0. Returns statistic and chi-square(1) p."""
    f1 = full_fit or fit(d)
    f0 = fit(d, fixed={k: 0.0}, start=f1)
    f1, refit = refit_if_below(d, f1, f0)
    stat = max(0.0, 2 * (f1["loglik"] - f0["loglik"]))
    return {"stat": stat, "p": float(chi2.sf(stat, 1)), "full": f1, "null": f0, "refit": refit}


def profile_ci(d, k, full_fit=None, level=0.95, span=12.0):
    """Profile-likelihood interval for coefficient k. Steps outward from the estimate with warm starts,
    keeps the better of two starts at each point, and solves for the crossing by Brent's method on the
    verified bracket (linear interpolation if the profile is not monotone there). A side with no crossing
    within `span` of the estimate is returned as +/- inf (one-sided interval)."""
    f1 = full_fit or fit(d)
    crit = chi2.ppf(level, 1) / 2
    bhat = f1["theta"][k]
    cache = {}

    def prof(b, start):
        key = round(float(b), 10)
        if key not in cache:
            a = fit(d, fixed={k: b}, start=start)
            c = fit(d, fixed={k: b}, start=f1)
            cache[key] = a if a["loglik"] >= c["loglik"] else c
        return cache[key]

    def dev(b, start=None):
        return (f1["loglik"] - prof(b, start or f1)["loglik"]) - crit

    out = []
    for direction in (-1, 1):
        step, prev, prev_fit = 0.25, bhat, f1
        found = None
        while abs(prev - bhat) < span:
            b = prev + direction * step
            fb = prof(b, prev_fit)
            if (f1["loglik"] - fb["loglik"]) - crit > 0:
                lo, hi = sorted((prev, b))
                flo, fhi = dev(lo), dev(hi)
                if flo < 0 < fhi or fhi < 0 < flo:
                    found = brentq(dev, lo, hi, xtol=1e-4)
                else:
                    dp, db = dev(prev), dev(b)
                    found = prev + (b - prev) * (-dp) / (db - dp) if db != dp else b
                break
            prev, prev_fit, step = b, fb, step * 1.6
        out.append(found if found is not None else direction * np.inf)
    return out[0], out[1]
