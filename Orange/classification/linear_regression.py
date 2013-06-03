import numpy as np
import scipy.sparse as sp
from scipy.optimize import fmin_l_bfgs_b

from Orange import classification


class LinearRegressionLearner(classification.Fitter):
    def __init__(self, lambda_, **fmin_args):
        self.lambda_ = lambda_
        self.fmin_args = fmin_args

    def cost_grad(self, theta, X, y):
        t = X.dot(theta) - y

        cost = t.dot(t)
        cost += self.lambda_ * theta.dot(theta)
        cost /= 2.0 * X.shape[0]

        grad = X.T.dot(t)
        grad += self.lambda_ * theta
        grad /= X.shape[0]

        return cost, grad

    def fit(self, X, Y, W):
        if Y.shape[1] > 1:
            raise ValueError('Linear regression does not support '
                             'multi-target classification')

        if np.isnan(np.sum(X)) or np.isnan(np.sum(Y)):
            raise ValueError('Linear regression does not support '
                             'unknown values')

        theta = np.zeros(X.shape[1])
        theta, cost, ret = fmin_l_bfgs_b(self.cost_grad, theta,
                                         args=(X, Y.ravel()), **self.fmin_args)

        return LinearRegressionClassifier(theta)


class LinearRegressionClassifier(classification.Model):
    def __init__(self, theta):
        self.theta = theta

    def predict(self, X):
        return X.dot(self.theta)


if __name__ == '__main__':
    import Orange.data
    from sklearn.cross_validation import KFold

    def numerical_grad(f, params, e=1e-4):
        grad = np.zeros_like(params)
        perturb = np.zeros_like(params)
        for i in range(params.size):
            perturb[i] = e
            j1 = f(params - perturb)
            j2 = f(params + perturb)
            grad[i] = (j2 - j1) / (2.0 * e)
            perturb[i] = 0
        return grad

    d = Orange.data.Table('housing')
    d.shuffle()

    m = LinearRegressionLearner(lambda_=1.0)
    print(m(d)(d[0]))

#    # gradient check
#    m = LinearRegressionLearner(lambda_=1.0)
#    theta = np.random.randn(d.X.shape[1])
#
#    ga = m.cost_grad(theta, d.X, d.Y.ravel())[1]
#    gm = numerical_grad(lambda t: m.cost_grad(t, d.X, d.Y.ravel())[0], theta)
#
#    print(ga)
#    print(gm)
#
#    for lambda_ in (0.01, 0.03, 0.1, 0.3, 1, 3):
#        m = LinearRegressionLearner(lambda_=lambda_)
#        scores = []
#        for tr_ind, te_ind in KFold(d.X.shape[0]):
#            s = np.mean((m(d[tr_ind])(d[te_ind]) - d[te_ind].Y.ravel())**2)
#            scores.append(s)
#        print('{:5.2f} {}'.format(lambda_, np.mean(scores)))
#
#    m = LinearRegressionLearner(lambda_=0)
#    print('test data', np.mean((m(d)(d) - d.Y.ravel())**2))
#    print('majority', np.mean((np.mean(d.Y.ravel()) - d.Y.ravel())**2))
