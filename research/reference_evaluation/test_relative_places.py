import unittest
import numpy as np
import relative_places as c


LABELS=np.array([0,1,2,0,2,1,0])
POINTS=np.array([[0,0],[1,0],[2,0],[0,0],[2,0],[1,0],[0,0]],float)


class RelationTests(unittest.TestCase):
    def test_perfect_group_ordering(self):
        result=c.evaluate(c.score_positions(POINTS),LABELS)
        self.assertEqual(result['pair_auc'],1.)
        self.assertEqual(result['pair_average_precision'],1.)
        self.assertEqual(result['same_pairs'],5)
        self.assertEqual(result['different_pairs'],16)

    def test_all_ties_are_not_order_broken(self):
        result=c.evaluate(c.score_positions(np.zeros((7,2))),LABELS)
        self.assertEqual(result['pair_auc'],.5)
        self.assertAlmostEqual(result['pair_average_precision'],5/21)

    def test_frame_and_scale_invariance(self):
        theta=.819;rotation=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
        base=c.score_positions(POINTS)
        for scale in [1e-3,1,1e3]:
            q=scale*POINTS@rotation.T+np.array([31.,-27.])
            other=c.score_positions(q)
            np.testing.assert_allclose(base['pair_scores'],other['pair_scores'],atol=1e-10)
            self.assertEqual(c.evaluate(base,LABELS)['pair_auc'],c.evaluate(other,LABELS)['pair_auc'])

    def test_perfect_nearest_prior_revisits(self):
        result=c.evaluate(c.score_positions(POINTS),LABELS)
        self.assertEqual(result['revisit_queries'],4)
        self.assertEqual(result['nearest_prior_fractional_correct'],1.)

    def test_history_retrieval_ignores_future(self):
        before=c.score_positions(POINTS)
        q=POINTS.copy();q[4:]=[999.,1000.]
        after=c.score_positions(q)
        self.assertEqual(before['nearest_prior_ties'][:4],after['nearest_prior_ties'][:4])

    def test_huge_future_cannot_create_history_ties(self):
        before=c.score_positions(POINTS)
        q=POINTS.copy();q[4:]=[1e15,2e15]
        after=c.score_positions(q)
        self.assertEqual(before['nearest_prior_ties'][:4],after['nearest_prior_ties'][:4])

    def test_label_names_cannot_change_scores(self):
        a=c.evaluate(c.score_positions(POINTS),LABELS)
        b=c.evaluate(c.score_positions(POINTS),np.array(['chair','cabinet','other','chair','other','cabinet','chair']))
        self.assertEqual(a,b)

    def test_average_precision_uses_entire_tie_group(self):
        result=c.average_precision(np.array([2.,1.,1.,0.]),np.array([True,True,False,False]))
        self.assertAlmostEqual(result,5/6)

    def test_evaluator_cannot_silently_truncate_reference(self):
        with self.assertRaises(ValueError):c.evaluate(c.score_positions(POINTS),LABELS[:-1])

    def test_unlabeled_partitions_count(self):
        partitions=c.partitions_322()
        self.assertEqual(len(partitions),105)
        self.assertEqual(len({tuple(c.same_pair_labels(p)) for p in partitions}),105)

    def test_scores_do_not_receive_or_return_site_labels(self):
        result=c.score_positions(POINTS)
        self.assertNotIn('labels',result)
        self.assertIsNone(result['predicted_site_count'])

    def test_bad_coordinates_rejected(self):
        q=POINTS.copy();q[0,0]=np.nan
        with self.assertRaises(ValueError):c.score_positions(q)

    def test_pair_auc_matches_direct_definition(self):
        scores=np.array([0.,0.,1.,3.]);labels=np.array([True,False,True,False])
        expected=np.mean([.5*(a==b)+(a>b) for a in scores[labels] for b in scores[~labels]])
        self.assertEqual(c.auc(scores,labels),expected)


if __name__=='__main__':unittest.main()
