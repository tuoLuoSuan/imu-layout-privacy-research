"""Causal-budget contracts including native callback availability."""
import importlib.util,unittest,tempfile,math,csv,io,json,zipfile
from pathlib import Path
import numpy as np
from analysis.phone_ronin.adapter import make_windows

AVAILABLE=importlib.util.find_spec('analysis.phone_ronin.prefix') is not None
if AVAILABLE:
    from analysis.phone_ronin.prefix import (eligible_window_mask,evaluate_prefix as evaluate_prefix_api,
        prefix_inputs,write_prefix_results,load_arrival_session,path_end)
else:
    # Reproduce the published exploratory center cut until the new API exists.
    def eligible_window_mask(timing,budget):return timing[:,2]<=budget

def signals(end=4.):
    times=np.arange(int(end*100)+1)/100
    a=[(float(t),.1*math.sin(t*8),0,9.80665) for t in times]
    g=[(float(t),0,0,.02*math.sin(t)) for t in times]
    availability=(times+.006).tolist()
    return a,g,availability,availability.copy()

def predictor(windows):
    return np.column_stack((windows[:,3,:].mean(axis=1),windows[:,5,:].mean(axis=1)*.1))

def evaluate_prefix(*args,**kwargs):
    # Synthetic fixture has an explicitly known four-second recorded support.
    kwargs.setdefault('support_end_s',4.)
    return evaluate_prefix_api(*args,**kwargs)

class BudgetBoundary(unittest.TestCase):
    def test_published_04535_second_peek_is_refused(self):
        timing=np.array([[20.953473855,21.953473855,21.453473855],
            [21.453473855,22.453473855,21.953473855]])
        mask=eligible_window_mask(timing,22.)
        np.testing.assert_array_equal(mask,[True,False])

    def test_new_prefix_api_exists(self):
        self.assertTrue(AVAILABLE,'Arrival-aware native prefix API is missing')

@unittest.skipUnless(AVAILABLE,'prefix API not implemented')
class PrefixContracts(unittest.TestCase):
    def test_direct_api_refuses_budget_beyond_native_support(self):
        a,g,aa,ga=signals()
        def forbidden(w):raise AssertionError('Unsupported budget reached network')
        result=evaluate_prefix(a,g,aa,ga,60.,forbidden)
        self.assertEqual(result['summary']['status'],'outside_recorded_session')
        self.assertIsNone(path_end(a,g,aa,ga,60.,forbidden,support_end_s=4.))

    def test_explicit_recorded_support_overrides_appended_rows(self):
        a,g,aa,ga=signals(70.)
        r=evaluate_prefix(a,g,aa,ga,60.,predictor,support_end_s=4.)
        self.assertEqual(r['summary']['status'],'outside_recorded_session')
        self.assertIsNone(path_end(a,g,aa,ga,60.,predictor,support_end_s=4.))

    def test_excluded_late_row_and_bridged_gap_are_disclosed(self):
        a,g,aa,ga=signals();aa[150]=10.
        r=evaluate_prefix(a,g,aa,ga,3.009,predictor)
        self.assertEqual(r['summary']['excluded_late_rows'],{'accelerometer':1,'gyroscope':0})
        self.assertAlmostEqual(r['summary']['max_effective_gap_s'],.02)
        self.assertTrue(r['summary']['resampling_interpolation_used'])

    def test_long_late_gap_returns_no_estimate_without_network(self):
        a,g,aa,ga=signals()
        for i in range(120,241):aa[i]=ga[i]=10.
        def forbidden(w):raise AssertionError('Unsupported gap reached network')
        r=evaluate_prefix(a,g,aa,ga,3.509,forbidden)
        self.assertEqual(r['summary']['status'],'input_gap_exceeds_limit')
        self.assertEqual(r['summary']['excluded_late_rows']['accelerometer'],121)
        self.assertGreater(r['summary']['max_effective_gap_s'],1.)
        self.assertIsNone(r['summary']['path_end_m_model'])

    def test_native_arrival_times_use_integer_nanosecond_differences(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'native.zip';origin=100_000_000_000
            metadata={'units':{'accelerometer':'m/s^2 including gravity','gyroscope':'rad/s'},'written':[3,3]}
            payload={}
            for name,shift in [('accelerometer.csv',0),('gyroscope.csv',1_000_000)]:
                text=io.StringIO();w=csv.writer(text);w.writerow(['sequence','sensor_timestamp_ns','received_elapsed_realtime_ns','x','y','z'])
                for i in range(3):
                    event=origin+shift+i*10_000_000
                    w.writerow([i+1,event,event+6_000_000,0,0,9.80665 if name.startswith('accel') else 0])
                payload[name]=text.getvalue()
            with zipfile.ZipFile(p,'x') as z:
                z.writestr('metadata.json',json.dumps(metadata))
                for name,text in payload.items():z.writestr(name,text)
            a,g,aa,ga,source=load_arrival_session(p)
            self.assertEqual(a[0][0],0.);self.assertEqual(g[0][0],.001)
            self.assertEqual(aa[0],.006);self.assertEqual(ga[0],.007)
            self.assertEqual(source['event_origin_ns'],origin)

    def test_future_changes_and_appends_cannot_change_features_or_result(self):
        a,g,aa,ga=signals();one=evaluate_prefix(a,g,aa,ga,2.2,predictor)
        changed_a=[r if av<=2.2 else (r[0],700.,-600.,500.) for r,av in zip(a,aa)]
        changed_g=[r if av<=2.2 else (r[0],80.,-70.,60.) for r,av in zip(g,ga)]
        changed_a.append((5.,100,200,300));changed_g.append((5.,7,8,9))
        two=evaluate_prefix(changed_a,changed_g,aa+[5.1],ga+[5.1],2.2,predictor)
        self.assertEqual(one['summary'],two['summary'])
        np.testing.assert_array_equal(one['velocities'],two['velocities'])
        np.testing.assert_array_equal(one['positions'],two['positions'])

    def test_event_before_budget_but_arriving_after_is_excluded(self):
        a,g,aa,ga=signals()
        for i in range(199,len(aa)):aa[i]=ga[i]=max(aa[i],2.2)
        past_a,past_g,info=prefix_inputs(a,g,aa,ga,2.)
        self.assertEqual(len(past_a),199);self.assertEqual(len(past_g),199)
        self.assertLessEqual(info['last_raw_arrival_s'],2.)
        self.assertLessEqual(past_a[-1][0],1.98)

    def test_window_target_end_and_sample_span_are_distinct(self):
        a,g,aa,ga=signals();r=evaluate_prefix(a,g,aa,ga,2.,predictor)
        s=r['summary'];self.assertAlmostEqual(s['input_sample_span_s'],.995)
        self.assertAlmostEqual(s['target_interval_s'],1.)
        self.assertAlmostEqual(s['last_target_end_s']-s['last_input_grid_sample_s'],.005)
        self.assertLessEqual(s['last_target_end_s'],2.)
        self.assertLessEqual(s['last_raw_arrival_s'],2.)

    def test_short_prefix_returns_unknown_without_calling_network(self):
        a,g,aa,ga=signals()
        def forbidden(x):raise AssertionError('Network must not run for short prefix')
        r=evaluate_prefix(a,g,aa,ga,.5,forbidden)
        self.assertEqual(r['summary']['status'],'insufficient_model_context')
        self.assertIsNone(r['summary']['path_end_m_model'])

    def test_bad_budget_or_missing_availability_is_refused(self):
        a,g,aa,ga=signals()
        for value in [-1,0,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):evaluate_prefix(a,g,aa,ga,value,predictor)
        with self.assertRaises(ValueError):prefix_inputs(a,g,aa[:-1],ga,2.)

    def test_invalid_predictions_are_not_saved_as_a_path(self):
        a,g,aa,ga=signals()
        with self.assertRaises(ValueError):evaluate_prefix(a,g,aa,ga,2.,lambda w:np.full((len(w),2),np.nan))

    def test_distinct_budgets_recompute_native_prefixes(self):
        a,g,aa,ga=signals();one=evaluate_prefix(a,g,aa,ga,2.,predictor);two=evaluate_prefix(a,g,aa,ga,3.,predictor)
        self.assertLess(one['summary']['eligible_accel_rows'],two['summary']['eligible_accel_rows'])
        self.assertLess(one['summary']['prediction_count'],two['summary']['prediction_count'])

    def test_output_is_fresh_and_path_guarded(self):
        a,g,aa,ga=signals();r=evaluate_prefix(a,g,aa,ga,2.,predictor)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'fresh';write_prefix_results(out,{},[r],allowed_root=root)
            before={str(f.relative_to(out)):f.read_bytes() for f in out.rglob('*') if f.is_file()}
            with self.assertRaises(FileExistsError):write_prefix_results(out,{},[r],allowed_root=root)
            self.assertEqual(before,{str(f.relative_to(out)):f.read_bytes() for f in out.rglob('*') if f.is_file()})
            with self.assertRaises(ValueError):write_prefix_results(root.parent/'escape',{},[r],allowed_root=root)

if __name__=='__main__':unittest.main()
