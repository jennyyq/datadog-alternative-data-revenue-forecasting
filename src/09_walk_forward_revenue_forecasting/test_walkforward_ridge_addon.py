"""Additional synthetic sanity tests; original 10 tests stay unchanged."""
import numpy as np
import walkforward_ridge_addon as R

def test_zero_coefficients_large_penalty_revert_to_train_mean():
    rng=np.random.default_rng(0)
    X=rng.normal(size=(15,2)); y=rng.normal(size=15)*5+20
    pred=R.ridge_predict(X,y,np.array([2.,-1.]),alpha=1e12)
    assert abs(pred-y.mean())<1e-8

def test_no_future_influence():
    rng=np.random.default_rng(1)
    X=rng.normal(size=(12,2)); y=rng.normal(size=12)
    v=R.ridge_predict(X[:8],y[:8],X[8])
    X[11,:]=999;y[11]=999
    assert np.isclose(v,R.ridge_predict(X[:8],y[:8],X[8]))

def test_constant_feature_is_safe():
    X=np.column_stack([np.ones(10),np.arange(10.)]);y=np.arange(10.)
    assert np.isfinite(R.ridge_predict(X,y,np.array([1.,10.])))

if __name__=='__main__':
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    for t in tests:t();print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} Ridge synthetic tests passed.')
