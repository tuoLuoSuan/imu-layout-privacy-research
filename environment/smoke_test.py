"""Environment-only check. Iris example data; no IMU/HAR or layout experiment."""
import json
import platform
import sys
import numpy as np
import pandas as pd
import scipy
import sklearn
import matplotlib
matplotlib.use('Agg')
import xgboost as xgb
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

data=load_iris()
x_train,x_test,y_train,_=train_test_split(data.data,data.target,test_size=.2,random_state=7,stratify=data.target)
model=xgb.XGBClassifier(n_estimators=4,max_depth=2,n_jobs=2,tree_method='hist',device='cpu',random_state=7)
model.fit(x_train,y_train)
p=model.predict_proba(x_test)
assert p.shape==(30,3) and np.isfinite(p).all()
assert np.allclose(p.sum(axis=1),1,atol=1e-5)
print(json.dumps({'kind':'environment_smoke_test_not_research_result','status':'passed','platform':platform.platform(),'python':sys.version.split()[0],'xgboost':xgb.__version__,'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__,'device':'cpu','example_data':'bundled_iris','imu_training':False,'layout_training':False},ensure_ascii=False,indent=2))
