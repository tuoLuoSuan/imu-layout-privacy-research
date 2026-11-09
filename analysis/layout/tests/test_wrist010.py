import unittest
import numpy as np
import json,subprocess,sys,tempfile
from pathlib import Path


class Wrist010Tests(unittest.TestCase):
    def test_large_synthetic_set_cannot_swamp_real_positive_examples(self):
        from analysis.layout.wrist010 import balanced_weights
        domains=np.array(['real','real']+['sim']*20);labels=np.array([0,1]+[0]*10+[1]*10)
        w=balanced_weights(domains,labels)
        for domain in ['real','sim']:
            for label in [0,1]:self.assertAlmostEqual(w[(domains==domain)&(labels==label)].sum(),.25)
        with self.assertRaises(ValueError):balanced_weights(['real','sim'],[0,1])

    def test_partial_transition_windows_are_not_given_confident_action_labels(self):
        from analysis.layout.wrist010 import window_label
        t=np.arange(0,4,.1);labels=np.array(['cabinet']*20+['other']*20)
        self.assertEqual(window_label(t,labels,0,1.5),1)
        self.assertIsNone(window_label(t,labels,1,3))
        self.assertEqual(window_label(t,labels,2,3.5),0)

    def test_domain_ensemble_does_not_average_away_a_supported_cabinet_event(self):
        from analysis.layout.wrist010 import DomainEnsemble
        class Expert:
            def __init__(self,p):self.p=p
            def predict_proba(self,x):return np.tile([1-self.p,self.p],(len(x),1))
        model=DomainEnsemble(Expert(.8),Expert(.05))
        np.testing.assert_array_equal(model.predict(np.zeros((2,3))),[1,1])
        np.testing.assert_allclose(model.predict_proba(np.zeros((1,3))),[[.2,.8]])

    def test_saved_ensemble_loads_in_a_fresh_python_process(self):
        import joblib
        from sklearn.dummy import DummyClassifier
        from analysis.layout.wrist010 import DomainEnsemble
        a=DummyClassifier(strategy='prior').fit(np.zeros((10,2)),[0]*2+[1]*8)
        b=DummyClassifier(strategy='prior').fit(np.zeros((10,2)),[0]*9+[1])
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'model.joblib';joblib.dump(DomainEnsemble(a,b),f)
            code="import joblib,json,numpy as np,sys;print(json.dumps(joblib.load(sys.argv[1]).predict(np.zeros((2,2))).tolist()))"
            value=subprocess.check_output([sys.executable,'-c',code,str(f)],text=True)
        self.assertEqual(json.loads(value),[1,1])


if __name__=='__main__':unittest.main()
