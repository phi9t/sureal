import math
import unittest
import torch
from pipeline.detector_loss import detector_loss


class DetectorLossTests(unittest.TestCase):
    def test_hand_computed_positive_background_and_ignore(self):
        logits=torch.zeros(1,3,1,dtype=torch.float64,requires_grad=True)
        boxes=torch.zeros(1,3,7,dtype=torch.float64,requires_grad=True)
        target=torch.zeros_like(boxes);target[0,0,0]=1
        direction=torch.zeros(1,3,2,dtype=torch.float64,requires_grad=True)
        result=detector_loss(logits,boxes,direction,torch.tensor([[1,0,-1]]),target,torch.zeros(1,3,dtype=torch.int64))
        self.assertAlmostEqual(float(result['classification']),math.log(2)/4,places=12)
        self.assertAlmostEqual(float(result['localization']),17/18,places=12)
        self.assertAlmostEqual(float(result['direction']),math.log(2),places=12)
        result['total'].backward()
        self.assertEqual(float(logits.grad[0,2,0]),0.)
        for value in [logits.grad,boxes.grad,direction.grad]:self.assertTrue(torch.isfinite(value).all())

    def test_empty_foreground_has_only_background_classification(self):
        logits=torch.zeros(1,2,1,dtype=torch.float64,requires_grad=True)
        boxes=torch.zeros(1,2,7,dtype=torch.float64,requires_grad=True)
        direction=torch.zeros(1,2,2,dtype=torch.float64,requires_grad=True)
        result=detector_loss(logits,boxes,direction,torch.zeros(1,2,dtype=torch.int64),torch.zeros_like(boxes),torch.zeros(1,2,dtype=torch.int64))
        self.assertAlmostEqual(float(result['total'].detach()),3*math.log(2)/8,places=12)
        self.assertEqual(float(result['localization'].detach()),0)
        self.assertEqual(float(result['direction'].detach()),0)
        result['total'].backward()
        self.assertTrue(torch.isfinite(logits.grad).all())

    def test_yaw_pi_ambiguity_is_left_for_direction_head(self):
        boxes=torch.zeros(1,1,7,dtype=torch.float64);boxes[0,0,6]=math.pi
        result=detector_loss(torch.zeros(1,1,1,dtype=torch.float64),boxes,torch.zeros(1,1,2,dtype=torch.float64),torch.ones(1,1,dtype=torch.int64),torch.zeros_like(boxes),torch.zeros(1,1,dtype=torch.int64))
        self.assertAlmostEqual(float(result['localization']),0,places=12)


if __name__=='__main__':unittest.main()
