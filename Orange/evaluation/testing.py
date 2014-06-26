import numpy as np

from sklearn import cross_validation

from Orange.data import Domain, Table


class Results:
    """
    Class for storing predicted in model testing.

    .. attribute:: data

        Data used for testing (optional; can be `None`). When data is stored,
        this is typically not a copy but a reference.

    .. attribute:: row_indices

        Indices of rows in :obj:`data` that were used in testing, stored as
        a numpy vector of length `nrows`. Values of `actual[i]`, `predicted[i]`
        and `probabilities[i]` refer to the target value of instance
        `data[row_indices[i]]`.

    .. attribute:: nrows

        The number of test instances (including duplicates).

    .. attribute:: models

        A list of induced models (optional; can be `None`).

    .. attribute:: actual

        Actual values of target variable; a numpy vector of length `nrows` and
        of the same type as `data` (or `np.float32` if the type of data cannot
        be determined).

    .. attribute:: predicted

        Predicted values of target variable; a numpy array of shape
        (number-of-methods, `nrows`) and of the same type as `data` (or
        `np.float32` if the type of data cannot be determined).

    .. attribute:: probabilities

        Predicted probabilities (for discrete target variables); a numpy array
        of shape (number-of-methods, `nrows`, number-of-classes) of type
        `np.float32`.

    .. attribute:: folds

        A list of indices (or slice objects) corresponding to rows of each
        fold; `None` if not applicable.
    """

    # noinspection PyBroadException
    # noinspection PyNoneFunctionAssignment
    def __init__(self, data=None, nmethods=0, nrows=None, nclasses=None,
                 store_data=False):
        """
        Construct an instance with default values: `None` for :obj:`data` and
        :obj:`models`.

        If the number of rows and/or the number of classes is not given, it is
        inferred from :obj:`data`, if provided. The data type for
        :obj:`actual` and :obj:`predicted` is determined from the data; if the
        latter cannot be find, `np.float32` is used.

        Attribute :obj:`actual` and :obj:`row_indices` are constructed as empty
        (uninitialized) arrays of the appropriate size, if the number of rows
        is known. Attribute :obj:`predicted` is constructed if the number of
        rows and of methods is given; :obj:`probabilities` also requires
        knowing the number of classes.

        :param data: Data or domain; the data is not stored
        :type data: Orange.data.Table or Orange.data.Domain
        :param nmethods: The number of methods that will be tested
        :type nmethods: int
        :param nrows: The number of test instances (including duplicates)
        :type nrows: int
        """
        self.data = data if store_data else None
        self.models = None
        self.folds = None
        dtype = np.float32
        if data:
            domain = data if isinstance(data, Domain) else data.domain
            if nclasses is None:
                nclasses = len(domain.class_var.values)
            if nrows is None:
                nrows = len(data)
            try:
                dtype = data.Y.dtype
            except AttributeError:
                pass
        if nrows is not None:
            self.actual = np.empty(nrows, dtype=dtype)
            self.row_indices = np.empty(nrows, dtype=np.int32)
            if nmethods is not None:
                self.predicted = np.empty((nmethods, nrows), dtype=dtype)
                if nclasses is not None:
                    self.probabilities = \
                        np.empty((nmethods, nrows, nclasses), dtype=np.float32)

    def get_fold(self, fold):
        results = Results()
        results.data = self.data
        results.models = self.models[fold]
        results.actual = self.actual[self.folds[fold]]
        results.predicted = self.predicted[self.folds[fold]]
        results.probabilities = self.probabilities[self.folds[fold]]
        results.row_indices = self.row_indices[self.folds[fold]]


class Testing:
    """
    Abstract base class for various sampling procedures like cross-validation,
    leave one out or bootstrap. Derived classes define a `__call__` operator
    that executes the testing procedure and returns an instance of
    :obj:`Results`.

    .. attribute:: store_data

        A flag that tells whether to store the data used for test.

    .. attribute:: store_models

        A flag that tells whether to store the constructed models
    """

    def __new__(cls, data=None, fitters=None, **kwargs):
        """
        Construct an instance and store the values of keyword arguments
        `store_data` and `store_models`, if given. If `data` and
        `learners` are given, the constructor also calls the testing
        procedure. For instance, CrossValidation(data, learners) will return
        an instance of `Results` with results of cross validating `learners` on
        `data`.

        :param data: Data instances used for testing procedures
        :type data: Orange.data.Storage
        :param learners: A list of learning algorithms to be tested
        :type fitters: list of Orange.classification.Fitter
        :param store_data: A flag that tells whether to store the data;
            this argument can be given only as keyword argument
        :type store_data: bool
        :param store_models: A flag that tells whether to store the models;
            this argument can be given only as keyword argument
        :type store_models: bool
        """
        self = super().__new__(cls)
        self.store_data = kwargs.pop('store_data', False)
        self.store_models = kwargs.pop('store_models', False)

        if fitters is not None:
            if data is None:
                raise TypeError("{} is given fitters, but no data".
                                format(cls.__name__))
            self.__init__(**kwargs)
            return self(data, fitters)
        return self

    def __call__(self, data, fitters):
        raise TypeError("{}.__call__ is not implemented".
                        format(type(self).__name__))


class CrossValidation(Testing):
    """
    K-fold cross validation.

    If the constructor is given the data and a list of learning algorithms, it
    runs cross validation and returns an instance of `Results` containing the
    predicted values and probabilities.

    .. attribute:: k

        The number of folds.

    .. attribute:: random_state

    """
    def __init__(self, k=10, random_state=0):
        self.k = k
        self.random_state = random_state

    def __call__(self, data, fitters):
        n = len(data)
        indices = cross_validation.KFold(
            n, self.k, shuffle=True, random_state=self.random_state
        )
        results = Results(data, len(fitters), store_data=self.store_data)

        results.folds = []
        if self.store_models:
            results.models = []
        ptr = 0
        for train, test in indices:
            train_data, test_data = data[train], data[test]
            fold_slice = slice(ptr, ptr + len(test))
            results.folds.append(fold_slice)
            results.row_indices[fold_slice] = test
            results.actual[fold_slice] = test_data.Y.flatten()
            if self.store_models:
                fold_models = []
                results.models.append(fold_models)
            for i, fitter in enumerate(fitters):
                model = fitter(train_data)
                if self.store_models:
                    fold_models.append(model)
                values, probs = model(test_data, model.ValueProbs)
                results.predicted[i][fold_slice] = values
                results.probabilities[i][fold_slice, :] = probs
            ptr += len(test)
        return results


class LeaveOneOut(Testing):
    """Leave-one-out testing
    """
    def __call__(self, data, fitters):
        results = Results(data, len(fitters), store_data=self.store_data)

        domain = data.domain
        X = data.X.copy()
        Y = data.Y.copy()
        metas = data.metas.copy()

        teX, trX = X[:1], X[1:]
        teY, trY = Y[:1], Y[1:]
        te_metas, tr_metas = metas[:1], metas[1:]
        if data.has_weights():
            W = data.W.copy()
            teW, trW = W[:1], W[1:]
        else:
            W = teW = trW = None

        results.row_indices = np.arange(len(data))
        if self.store_models:
            results.models = []
        results.actual = Y.flatten()
        for test_idx in results.row_indices:
            X[[0, test_idx]] = X[[test_idx, 0]]
            Y[[0, test_idx]] = Y[[test_idx, 0]]
            metas[[0, test_idx]] = metas[[test_idx, 0]]
            if W:
                W[[0, test_idx]] = W[[test_idx, 0]]
            test_data = Table.from_numpy(domain, teX, teY, te_metas, teW)
            train_data = Table.from_numpy(domain, trX, trY, tr_metas, trW)
            if self.store_models:
                fold_models = []
                results.models.append(fold_models)
            for i, fitter in enumerate(fitters):
                model = fitter(train_data)
                if self.store_models:
                    fold_models.append(model)
                values, probs = model(test_data, model.ValueProbs)
                results.predicted[i][test_idx] = values
                results.probabilities[i][test_idx, :] = probs
        return results


class TestOnTrainingData(Testing):
    """Trains and test on the same data
    """
    def __call__(self, data, fitters):
        results = Results(data, len(fitters), store_data=self.store_data)
        results.row_indices = np.arange(len(data))
        if self.store_models:
            models = []
            results.models = [models]
        results.actual = data.Y.flatten()
        for i, fitter in enumerate(fitters):
            model = fitter(data)
            if self.store_models:
                models.append(model)
            values, probs = model(data, model.ValueProbs)
            results.predicted[i] = values
            results.probabilities[i] = probs
        return results


class Bootstrap(Testing):
    def __init__(self, n_resamples=10, p=0.75, random_state=0):
        self.n_resamples = n_resamples
        self.p = p
        self.random_state = random_state

    def __call__(self, data, fitters):
        indices = cross_validation.Bootstrap(
            len(data), n_iter=self.n_resamples, train_size=self.p,
            random_state=self.random_state
        )

        results = Results(data, len(fitters), store_data=self.store_data)

        results.folds = []
        if self.store_models:
            results.models = []

        row_indices = []
        actual = []
        predicted = [[] for _ in fitters]
        probabilities = [[] for _ in fitters]
        fold_start = 0
        for train, test in indices:
            train_data, test_data = data[train], data[test]
            results.folds.append(slice(fold_start, fold_start + len(test)))
            row_indices.append(test)
            actual.append(test_data.Y.flatten())
            if self.store_models:
                fold_models = []
                results.models.append(fold_models)

            for i, fitter in enumerate(fitters):
                model = fitter(train_data)
                if self.store_models:
                    fold_models.append(model)
                values, probs = model(test_data, model.ValueProbs)
                predicted[i].append(values)
                probabilities[i].append(probs)

            fold_start += len(test)

        row_indices = np.hstack(row_indices)
        actual = np.hstack(actual)
        predicted = np.array([np.hstack(pred) for pred in predicted])
        probabilities = np.array([np.vstack(prob) for prob in probabilities])
        nrows = len(actual)
        nmodels = len(predicted)

        results.nrows = len(actual)
        results.row_indices = row_indices
        results.actual = actual
        results.predicted = predicted.reshape(nmodels, nrows)
        results.probabilities = probabilities
        return results


class TestOnTestData(object):
    """
    Test on a separate test data set.
    """
    def __new__(cls, train_data=None, test_data=None, fitters=None,
                store_data=False, store_models=False, **kwargs):
        self = super().__new__(cls)
        self.store_data = store_data
        self.store_models = store_models

        if train_data is None and test_data is None and fitters is not None:
            return self
        elif train_data is not None and test_data is not None and \
                fitters is not None:
            self.__init__(**kwargs)
            return self(train_data, test_data, fitters)
        else:
            raise TypeError("Expected 3 positional arguments")

    def __call__(self, train_data, test_data, fitters):
        results = Results(test_data, len(fitters), store_data=self.store_data)
        models = []
        if self.store_models:
            results.models = [models]

        results.row_indices = np.arange(len(test_data))
        results.actual = test_data.Y.flatten()

        for i, fitter in enumerate(fitters):
            model = fitter(train_data)
            values, probs = model(test_data, model.ValueProbs)
            results.predicted[i] = values
            results.probabilities[i][:, :] = probs
            models.append(model)

        results.nrows = len(test_data)
        results.folds = [slice(0, len(test_data))]
        return results
